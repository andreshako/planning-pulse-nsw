"""Fetch a sample from the NSW Online DA Data API, preserve the raw
response(s) under data/raw/, and load it into a local DuckDB raw table.

This is an ingestion-only step: no cleaning, typing, or modelling happens
here (that is dbt's job). Rerunning this script REPLACES the contents of
the raw_development_applications table with the latest fetched sample; it
does not append. Raw response files saved under data/raw/ are timestamped
and accumulate across runs, so past downloads are never overwritten.

Two modes, controlled by DA_PAGE_COUNT (see load_config):

- Default (DA_PAGE_COUNT=1): a single page of up to 100 records, sized by
  DA_SAMPLE_SIZE. This is the normal, fast path for local development.
- Snapshot (DA_PAGE_COUNT>1, capped at MAX_PAGE_COUNT): fetches that many
  consecutive pages of 100 records each (PageNumber 1..N), stopping early
  if the API reports fewer pages are available. Each page's raw response
  is preserved individually; the DuckDB table is only replaced after every
  requested page has been fetched successfully. If any page fails, the
  script stops immediately and leaves the existing table untouched.

The NSW Online DA Data API is public: no credentials, API key, or UAT
environment are required. See docs/data_source.md for the verified
request/response shape and attribution requirements (CC BY).
"""

from __future__ import annotations

import json
import os
import sys
import time
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
DEFAULT_PAGE_COUNT = 1
MAX_PAGE_COUNT = 50
SNAPSHOT_PAGE_SIZE = 100
REQUEST_DELAY_SECONDS = 0.3
REQUEST_TIMEOUT_SECONDS = 30


@dataclass
class Config:
    sample_size: int
    page_count: int
    application_last_updated_from: str | None
    raw_data_dir: Path
    duckdb_path: Path


def load_config() -> Config:
    load_dotenv()

    requested_size = int(os.environ.get("DA_SAMPLE_SIZE", DEFAULT_SAMPLE_SIZE))
    sample_size = max(1, min(requested_size, MAX_SAMPLE_SIZE))

    requested_pages = int(os.environ.get("DA_PAGE_COUNT", DEFAULT_PAGE_COUNT))
    page_count = max(1, min(requested_pages, MAX_PAGE_COUNT))

    return Config(
        sample_size=sample_size,
        page_count=page_count,
        application_last_updated_from=os.environ.get("DA_APPLICATION_LAST_UPDATED_FROM", "").strip() or None,
        raw_data_dir=Path(os.environ.get("RAW_DATA_DIR", "data/raw")),
        duckdb_path=Path(os.environ.get("DUCKDB_PATH", "data/planning_pulse.duckdb")),
    )


def build_headers(page_size: int, page_number: int, application_last_updated_from: str | None) -> dict:
    filters: dict = {}
    if application_last_updated_from:
        filters["ApplicationLastUpdatedFrom"] = application_last_updated_from

    return {
        "PageSize": str(page_size),
        "PageNumber": str(page_number),
        "filters": json.dumps({"filters": filters}),
    }


def fetch_page(page_size: int, page_number: int, application_last_updated_from: str | None) -> requests.Response:
    headers = build_headers(page_size, page_number, application_last_updated_from)
    print(f"      GET {API_URL} (PageNumber={page_number}, PageSize={page_size})")

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
        print(f"ERROR: API request failed (HTTP {response.status_code}) on PageNumber={page_number}.")
        print(f"Response body (truncated): {response.text[:500]}")
        print("Stopping. No existing data has been modified.")
        sys.exit(1)

    return response


def parse_page(response: requests.Response, page_number: int) -> tuple[list[dict], int | None, int | None]:
    try:
        payload = json.loads(response.text)
    except json.JSONDecodeError:
        print(f"ERROR: Response for PageNumber={page_number} was not valid JSON.")
        print("The API may have returned an HTML error page. Stopping. No existing data has been modified.")
        sys.exit(1)

    if not isinstance(payload, dict) or not isinstance(payload.get("Application"), list):
        print(f"ERROR: PageNumber={page_number} response did not contain an 'Application' list.")
        if isinstance(payload, dict):
            print(f"Top-level keys: {list(payload.keys())}")
        print("Stopping. No existing data has been modified.")
        sys.exit(1)

    return payload["Application"], payload.get("TotalPages"), payload.get("TotalCount")


def fetch_sample(config: Config) -> requests.Response:
    print(f"[2/4] Fetching a single page (PageSize={config.sample_size})...")
    return fetch_page(config.sample_size, 1, config.application_last_updated_from)


def fetch_snapshot(config: Config) -> list[dict]:
    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    config.raw_data_dir.mkdir(parents=True, exist_ok=True)

    requested_pages = config.page_count
    target_records = requested_pages * SNAPSHOT_PAGE_SIZE
    print(
        f"[2/4] Fetching up to {requested_pages} page(s) of {SNAPSHOT_PAGE_SIZE} records "
        f"each (target up to {target_records} records)..."
    )

    all_records: list[dict] = []
    page_number = 0

    for page_number in range(1, requested_pages + 1):
        response = fetch_page(SNAPSHOT_PAGE_SIZE, page_number, config.application_last_updated_from)

        raw_path = config.raw_data_dir / f"da_snapshot_{run_timestamp}_page{page_number:03d}_raw.json"
        raw_path.write_text(response.text, encoding="utf-8")

        records, total_pages, total_count = parse_page(response, page_number)
        all_records.extend(records)

        progress = f"      [page {page_number}/{requested_pages}] {len(records)} records (total so far: {len(all_records)}"
        progress += f" of {total_count})" if total_count is not None else ")"
        print(progress)

        if total_pages is not None and page_number >= total_pages:
            print(f"      Reached the last available page (TotalPages={total_pages}); stopping early.")
            break

        if page_number < requested_pages:
            time.sleep(REQUEST_DELAY_SECONDS)

    print(
        f"[3/4] Snapshot complete: {len(all_records)} records retrieved from {page_number} page(s). "
        f"Raw pages saved under {config.raw_data_dir}/ (prefix da_snapshot_{run_timestamp}_)."
    )
    return all_records


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

    if config.page_count > 1:
        records = fetch_snapshot(config)
    else:
        response = fetch_sample(config)
        raw_path = save_raw_response(response, config.raw_data_dir)
        records = parse_records(raw_path)

    load_into_duckdb(records, config)

    print("Done.")


if __name__ == "__main__":
    main()
