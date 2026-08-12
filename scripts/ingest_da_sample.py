"""Fetch a small, conservative sample from the NSW Online DA Data API,
preserve the raw response under data/raw/, and load it into a local
DuckDB raw table.

This is an ingestion-only step: no cleaning, typing, or modelling happens
here (that is dbt's job in a later iteration). Rerunning this script
REPLACES the contents of the raw_development_applications table with the
latest fetched sample; it does not append. Raw response files saved under
data/raw/ are timestamped and accumulate across runs, so past downloads
are never overwritten.

Access to the NSW Online DA Data API is broker-mediated: there is no public
self-service endpoint or API key signup. Request access by emailing
data.broker@environment.nsw.gov.au and referencing the "Online DA Data API"
dataset (https://www.data.nsw.gov.au/data/dataset/online-da-data-api).
See docs/data_source.md for details.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb
import requests
from dotenv import load_dotenv

RAW_TABLE_NAME = "raw_development_applications"
DEFAULT_RECORD_LIMIT = 50
DEFAULT_LODGEMENT_WINDOW_DAYS = 7
REQUEST_TIMEOUT_SECONDS = 30

BROKER_CONTACT_MESSAGE = """
The NSW Online DA Data API is not a public self-service API: no endpoint URL
or API key is published anywhere in the official documentation. Access is
issued directly by the NSW Data Broker.

To get access:
  1. Email data.broker@environment.nsw.gov.au
  2. Reference the "Online DA Data API" dataset:
     https://www.data.nsw.gov.au/data/dataset/online-da-data-api
  3. Once you receive an endpoint URL and API key, copy .env.example to .env
     and fill in DA_API_URL and DA_API_KEY.

See docs/data_source.md for more detail. No network request has been made.
""".strip()


@dataclass
class Config:
    api_url: str
    api_key: str
    auth_header: str
    council_name: str | None
    lodgement_date_from: str
    lodgement_date_to: str
    record_limit: int
    raw_data_dir: Path
    duckdb_path: Path


def load_config() -> Config:
    load_dotenv()

    api_url = os.environ.get("DA_API_URL", "").strip()
    api_key = os.environ.get("DA_API_KEY", "").strip()

    if not api_url or not api_key:
        print("ERROR: DA_API_URL and/or DA_API_KEY are not set.\n")
        print(BROKER_CONTACT_MESSAGE)
        sys.exit(1)

    today = date.today()
    default_from = today - timedelta(days=DEFAULT_LODGEMENT_WINDOW_DAYS)

    return Config(
        api_url=api_url,
        api_key=api_key,
        auth_header=os.environ.get("DA_API_AUTH_HEADER", "Authorization").strip() or "Authorization",
        council_name=os.environ.get("DA_COUNCIL_NAME", "").strip() or None,
        lodgement_date_from=os.environ.get("DA_LODGEMENT_DATE_FROM", "").strip() or default_from.isoformat(),
        lodgement_date_to=os.environ.get("DA_LODGEMENT_DATE_TO", "").strip() or today.isoformat(),
        record_limit=int(os.environ.get("DA_RECORD_LIMIT", DEFAULT_RECORD_LIMIT)),
        raw_data_dir=Path(os.environ.get("RAW_DATA_DIR", "data/raw")),
        duckdb_path=Path(os.environ.get("DUCKDB_PATH", "data/planning_pulse.duckdb")),
    )


def build_filters(config: Config) -> dict:
    filters: dict = {
        "LodgementDateFrom": config.lodgement_date_from,
        "LodgementDateTo": config.lodgement_date_to,
    }
    if config.council_name:
        filters["CouncilName"] = [config.council_name]
    return filters


def fetch_sample(config: Config, filters: dict) -> requests.Response:
    print(f"[2/4] Requesting sample from the NSW Online DA Data API ({config.api_url})...")
    print(f"      Filters: {json.dumps(filters)}")

    headers = {
        config.auth_header: config.api_key,
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            config.api_url,
            headers=headers,
            json={"filters": filters},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Could not connect to {config.api_url}.")
        print("Check DA_API_URL and your network connection.")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print(f"ERROR: Request to {config.api_url} timed out after {REQUEST_TIMEOUT_SECONDS}s.")
        sys.exit(1)

    if response.status_code in (401, 403):
        print(f"ERROR: Authentication failed (HTTP {response.status_code}).")
        print(f"Check that DA_API_KEY and DA_API_AUTH_HEADER ('{config.auth_header}') are correct.")
        print("Access is issued by the NSW Data Broker: data.broker@environment.nsw.gov.au")
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

    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in ("data", "results", "records", "Applications", "applications"):
            value = payload.get(key)
            if isinstance(value, list):
                return value

    print("ERROR: Could not find a list of records in the API response.")
    print("The response JSON shape isn't documented in the DA Open APIs data dictionary;")
    print(f"top-level type was {type(payload).__name__}", end="")
    if isinstance(payload, dict):
        print(f" with keys: {list(payload.keys())}")
    else:
        print()
    print(f"Inspect the saved raw response at {raw_path} and adjust parse_records() accordingly.")
    sys.exit(1)


def load_into_duckdb(records: list[dict], config: Config) -> Path:
    limited = records[: config.record_limit]
    if len(records) > config.record_limit:
        print(f"      Fetched {len(records)} records; keeping first {config.record_limit} (DA_RECORD_LIMIT).")

    config.raw_data_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    loaded_path = config.raw_data_dir / f"da_sample_{timestamp}_loaded.json"
    loaded_path.write_text(json.dumps(limited, indent=2), encoding="utf-8")

    config.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[4/4] Loading {len(limited)} records into DuckDB ({config.duckdb_path}, table {RAW_TABLE_NAME})...")
    print(f"      This REPLACES any existing contents of {RAW_TABLE_NAME} (safe to rerun).")

    con = duckdb.connect(str(config.duckdb_path))
    try:
        if limited:
            con.execute(
                f"CREATE OR REPLACE TABLE {RAW_TABLE_NAME} AS SELECT * FROM read_json_auto(?)",
                [str(loaded_path)],
            )
        else:
            print("      No records returned for the given filters; leaving any existing table untouched.")
    finally:
        con.close()

    return loaded_path


def main() -> None:
    print("[1/4] Loading configuration from environment...")
    config = load_config()
    filters = build_filters(config)

    response = fetch_sample(config, filters)
    raw_path = save_raw_response(response, config.raw_data_dir)
    records = parse_records(raw_path)
    load_into_duckdb(records, config)

    print("Done.")


if __name__ == "__main__":
    main()
