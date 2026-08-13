"""Export safe, aggregated dashboard data from the local DuckDB marts into
small tracked CSV files under dashboard_data/.

This script only reads already-aggregated mart tables (no addresses,
coordinates, application numbers, or lot/plan details are present in
those tables to begin with) and writes deterministic, ordered CSVs so
that reruns produce clean, reviewable diffs. Rerunning this script always
overwrites the three CSVs from whatever is currently in the local DuckDB;
committing the result is a deliberate, reviewed step, not automatic.

SNAPSHOT_RECORD_LIMIT and APPLICATION_LAST_UPDATED_FROM describe how the
*currently loaded* local snapshot was fetched (see scripts/ingest_da_sample.py
DA_PAGE_COUNT / DA_SAMPLE_SIZE / DA_APPLICATION_LAST_UPDATED_FROM). They are
recorded here, not derived from the data, so update the environment
variables below if you reload the database with different settings before
re-running this export.
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
from dotenv import load_dotenv

DUCKDB_PATH = Path(os.environ.get("DUCKDB_PATH", "data/planning_pulse.duckdb"))
OUTPUT_DIR = Path("dashboard_data")

SNAPSHOT_RECORD_LIMIT = 5000
APPLICATION_LAST_UPDATED_FROM = "2025-01-01"


def main() -> None:
    load_dotenv()

    snapshot_record_limit = int(os.environ.get("DASHBOARD_SNAPSHOT_RECORD_LIMIT", SNAPSHOT_RECORD_LIMIT))
    application_last_updated_from = os.environ.get(
        "DASHBOARD_APPLICATION_LAST_UPDATED_FROM", APPLICATION_LAST_UPDATED_FROM
    )

    if not DUCKDB_PATH.exists():
        print(f"ERROR: {DUCKDB_PATH} not found. Run `make ingest` and `make build` first.")
        raise SystemExit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)

    try:
        council_path = OUTPUT_DIR / "council_activity.csv"
        con.execute(
            f"""
            COPY (
                SELECT council_name, application_status, application_type,
                       application_count, total_development_cost,
                       average_development_cost, latest_source_updated_at
                FROM main.mart_application_activity_by_council
                ORDER BY council_name, application_status, application_type
            ) TO '{council_path}' (HEADER, DELIMITER ',')
            """
        )
        council_rows = con.execute("SELECT count(*) FROM main.mart_application_activity_by_council").fetchone()[0]
        print(f"[1/3] Wrote {council_rows} rows to {council_path}")

        category_path = OUTPUT_DIR / "category_activity.csv"
        con.execute(
            f"""
            COPY (
                SELECT council_name, development_type, application_status,
                       application_count, total_development_cost,
                       average_development_cost, latest_source_updated_at
                FROM main.mart_application_activity_by_category
                ORDER BY council_name, development_type, application_status
            ) TO '{category_path}' (HEADER, DELIMITER ',')
            """
        )
        category_rows = con.execute("SELECT count(*) FROM main.mart_application_activity_by_category").fetchone()[0]
        print(f"[2/3] Wrote {category_rows} rows to {category_path}")

        metadata_path = OUTPUT_DIR / "snapshot_metadata.csv"
        con.execute(
            f"""
            COPY (
                SELECT
                    now()                                  AS export_generated_at,
                    {snapshot_record_limit}                AS snapshot_record_limit,
                    '{application_last_updated_from}'      AS application_last_updated_from,
                    count(*)                                AS total_applications,
                    count(DISTINCT council_name)            AS distinct_councils,
                    min(date_last_updated)                  AS date_last_updated_min,
                    max(date_last_updated)                  AS date_last_updated_max
                FROM main.stg_development_applications
            ) TO '{metadata_path}' (HEADER, DELIMITER ',')
            """
        )
        print(f"[3/3] Wrote 1 row to {metadata_path}")
    finally:
        con.close()

    print("Done. Review the CSVs under dashboard_data/ before committing.")


if __name__ == "__main__":
    main()
