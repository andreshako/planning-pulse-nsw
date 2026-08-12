"""Fetch a small, conservative sample from the NSW Online DA Data API,
preserve the raw response under data/raw/, and load it into a local
DuckDB raw table.

This is an ingestion-only step: no cleaning, typing, or modelling happens
here (that is dbt's job in a later iteration). Rerunning this script
REPLACES the contents of the raw_development_applications table with the
latest fetched sample; it does not append. Raw response files saved under
data/raw/ are timestamped and accumulate across runs, so past downloads
are never overwritten.

The NSW Online DA Data API is public: no credentials, API key, or UAT
environment are required. See docs/data_source.md for the verified
request/response shape and attribution requirements (CC BY).
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import requests
from dotenv import load_dotenv

API_URL = "https://api.apps1.nsw.gov.au/eplanning/data/v0/OnlineDA"
RAW_TABLE_NAME = "raw_development_applications"
DEFAULT_SAMPLE_SIZE = 50
MAX_SAMPLE_SIZE = 100
REQUEST_TIMEOUT_SECONDS = 30


@dataclass
class Config:
    sample_size: int
    application_last_updated_from: str | None
    raw_data_dir: Path
    duckdb_path: Path


def load_config() -> Config:
    load_dotenv()

    requested_size = int(os.environ.get("DA_SAMPLE_SIZE", DEFAULT_SAMPLE_SIZE))
    sample_size = max(1, min(requested_size, MAX_SAMPLE_SIZE))

    return Config(
        sample_size=sample_size,
        application_last_updated_from=os.environ.get("DA_APPLICATION_LAST_UPDATED_FROM", "").strip() or None,
        raw_data_dir=Path(os.environ.get("RAW_DATA_DIR", "data/raw")),
        duckdb_path=Path(os.environ.get("DUCKDB_PATH", "data/planning_pulse.duckdb")),
    )


def fetch_sample(config: Config) -> requests.Response:
    filters: dict = {}
    if config.application_last_updated_from:
        filters["ApplicationLastUpdatedFrom"] = config.application_last_updated_from

    headers = {
        "PageSize": str(config.sample_size),
        "PageNumber": "1",
        "filters": json.dumps({"filters": filters}),
    }

    print(f"[2/4] GET {API_URL}")
    print(f"      Headers: {headers}")

    try:
        response = requests.get(
            API_URL,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Could not connect to {API_URL}.")
        print("Check your network connection.")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print(f"ERROR: Request to {API_URL} timed out after {REQUEST_TIMEOUT_SECONDS}s.")
        sys.exit(1)

    if not response.ok:
        print(f"ERROR: API request failed (HTTP {response.status_code}).")
        print(f"Response body (truncated): {response.text[:500]}")
        sys.exit(1)

    return response


def save_raw_response(response: requests.Response, raw_data_dir: Path) -> Path:
    raw_data_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = raw_data_dir / f"da_sample_{timestamp}_raw.json"

    raw_path.write_text(response.text, encoding="utf-8")
    print(f"[3/4] Saved raw API response to {raw_path}")
    return raw_path


def parse_records(raw_path: Path) -> list[dict]:
    try:
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"ERROR: Response saved at {raw_path} was not valid JSON.")
        print("The API may have returned an HTML error page. Inspect the saved file.")
        sys.exit(1)

    if not isinstance(payload, dict) or not isinstance(payload.get("Application"), list):
        print("ERROR: Expected a JSON object with an 'Application' list.")
        if isinstance(payload, dict):
            print(f"Top-level keys: {list(payload.keys())}")
        print(f"Inspect the saved raw response at {raw_path}.")
        sys.exit(1)

    return payload["Application"]


def load_into_duckdb(records: list[dict], config: Config) -> None:
    config.raw_data_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    loaded_path = config.raw_data_dir / f"da_sample_{timestamp}_loaded.json"
    loaded_path.write_text(json.dumps(records, indent=2), encoding="utf-8")

    config.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[4/4] Loading {len(records)} records into DuckDB ({config.duckdb_path}, table {RAW_TABLE_NAME})...")
    print(f"      This REPLACES any existing contents of {RAW_TABLE_NAME} (safe to rerun).")

    con = duckdb.connect(str(config.duckdb_path))
    try:
        if records:
            con.execute(
                f"CREATE OR REPLACE TABLE {RAW_TABLE_NAME} AS SELECT * FROM read_json_auto(?)",
                [str(loaded_path)],
            )
        else:
            print("      No records returned; leaving any existing table untouched.")
    finally:
        con.close()


def main() -> None:
    print("[1/4] Loading configuration from environment...")
    config = load_config()

    response = fetch_sample(config)
    raw_path = save_raw_response(response, config.raw_data_dir)
    records = parse_records(raw_path)
    load_into_duckdb(records, config)

    print("Done.")


if __name__ == "__main__":
    main()
