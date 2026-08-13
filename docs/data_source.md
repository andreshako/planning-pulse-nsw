# Data source: NSW Online DA Data API

## What it is

The Online DA Data API is published by the NSW Department of Planning, Housing and
Infrastructure (formerly Planning, Industry and Environment). It provides a feed of
development-application (DA) records lodged on the NSW Planning Portal, with data
available from **10 December 2018** and updated daily.

- Dataset page: https://www.data.nsw.gov.au/data/dataset/online-da-data-api
- API overview: https://www.planningportal.nsw.gov.au/insights-and-demography/apis-online-digital-services/online-development-application-service-api-v2
- Data dictionary: "DA Open APIs" v2.0 (NSW Dept. of Planning, Industry and Environment), linked as a resource from the dataset page above.

## Access method

The API is **public**: no credentials, API key, UAT environment, or usage
limits are required. Requests go directly to the production endpoint below.

- **Method**: `GET`
- **Endpoint**: `https://api.apps1.nsw.gov.au/eplanning/data/v0/OnlineDA`
- **Request headers**: `PageSize`, `PageNumber`, and `filters`.
  - `filters` is a JSON-encoded string. For no filters: `{"filters": {}}`.

Example (no filters, first page, 50 records):

```
GET https://api.apps1.nsw.gov.au/eplanning/data/v0/OnlineDA
Headers:
  PageSize: 50
  PageNumber: 1
  filters: {"filters": {}}
```

Documented filter fields (nested inside the `filters` object) include
`CouncilName`, `ApplicationType`, `DevelopmentCategory`, `ApplicationStatus`,
`CostOfDevelopmentFrom`/`To`, several date-range filters (lodgement,
submission, determination, last-updated), and application numbers. This
project does not use any filters yet (`{"filters": {}}`) and relies on a
client-side sample-size cap instead — see `scripts/ingest_da_sample.py`.

## Response shape

The response is a JSON object:

```json
{
  "PageSize": 50,
  "PageNumber": 1,
  "TotalPages": ...,
  "TotalCount": ...,
  "Application": [ { ... }, { ... } ]
}
```

`Application` is the list of DA records for the requested page. This
project loads that list directly into DuckDB, so the raw table's columns
and types are inferred from whatever the API returns, not declared up
front — see `dbt_planning_pulse/models/staging/sources.yml`.

## Pagination note

By default, the script requests a single page (default 50 records, capped
at 100). Optionally, setting `DA_PAGE_COUNT` (see `.env.example`) fetches
that many consecutive pages of 100 records each via `PageNumber`, up to a
hard cap of 50 pages (5,000 records) — enough for a stronger local
analysis snapshot without ever pulling the full API history. The script
stops early if the API's `TotalPages` reports fewer pages are available,
and stops immediately (without touching the DuckDB table) if any page
request fails.

## Coverage caveat

> NSW Government has mandated all councils to use the Planning Portal from
> **1 July 2021**; some cases may be missing prior to that date.

Data from before July 2021 reflects voluntary council adoption only and should
be treated as incomplete. Any comparison spanning that boundary, or any claim
about council performance, processing speed, or equity, should be avoided or
heavily caveated — coverage differences, not real-world differences, may
explain apparent patterns.

## Running the ingestion script

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/ingest_da_sample.py
```

No `.env` file is required. `.env.example` documents optional local
overrides (sample size, storage paths) — copy it to `.env` only if you want
to change the defaults.

The script:

- By default, requests a single page of recent DA records (default 50,
  capped at 100), optionally filtered by `DA_APPLICATION_LAST_UPDATED_FROM`.
- Optionally, with `DA_PAGE_COUNT` set above 1, fetches that many
  consecutive pages of 100 records each (capped at 50 pages / 5,000
  records), stopping immediately without modifying existing data if any
  page fails.
- Saves the raw API response(s), untouched, under `data/raw/` with
  timestamped filenames — one file per page in snapshot mode.
- Loads the combined `Application` list into a local DuckDB database at
  `data/planning_pulse.duckdb`, table `raw_development_applications`.
- **Replaces** the contents of that table on every run (it does not append).
  Raw response files under `data/raw/` are timestamped and are never
  overwritten, so past downloads remain available even though the DuckDB
  table only ever holds the latest run's sample.

This script performs ingestion only — no cleaning, typing, or modelling.
That happens in dbt staging/mart models in a later iteration.

## Attribution

Data sourced from the NSW Online DA Data API, published by the NSW
Department of Planning, Housing and Infrastructure / NSW Planning Portal
(https://www.data.nsw.gov.au/data/dataset/online-da-data-api), licensed
under [Creative Commons Attribution (CC BY)](https://creativecommons.org/licenses/by/4.0/).
