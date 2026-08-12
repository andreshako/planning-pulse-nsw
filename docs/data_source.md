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

This is **not** a public self-service API. There is no published base URL, no
online API-key signup, and no Swagger/OpenAPI page. Access is broker-mediated:

1. Email **data.broker@environment.nsw.gov.au**.
2. Reference the "Online DA Data API" dataset (link above).
3. The Data Broker issues an endpoint URL and an API key/token directly to you.

Neither the endpoint URL nor the authentication header name is published in the
official documentation, so this repository does not hard-code either. Once you
receive access details, copy `.env.example` to `.env` and fill in `DA_API_URL`
and `DA_API_KEY` (and `DA_API_AUTH_HEADER`, if the Broker specifies a header
other than `Authorization`). **Never commit `.env`.**

## Request shape (from the data dictionary)

The API accepts a JSON body of the form:

```json
{
  "filters": {
    "CouncilName": ["PENRITH CITY COUNCIL"],
    "LodgementDateFrom": "2021-02-01",
    "LodgementDateTo": "2021-02-28"
  }
}
```

Documented filters include `CouncilName`, `ApplicationType`, `DevelopmentCategory`,
`ApplicationStatus`, `CostOfDevelopmentFrom`/`To`, several date-range filters
(lodgement, submission, determination, last-updated), and application numbers.
The data dictionary does not document a pagination or page-size parameter, so
this project applies a narrow lodgement date window and a client-side record
limit (`DA_RECORD_LIMIT`) to keep samples small — see `scripts/ingest_da_sample.py`.

The HTTP method is not stated explicitly in the dictionary; a JSON-body POST
request is assumed based on the documented payload shape. Confirm this with
the Data Broker when you receive access, and adjust the script if needed.

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

cp .env.example .env
# edit .env with the endpoint URL and API key issued by the Data Broker

python scripts/ingest_da_sample.py
```

The script:

- Reads settings from `.env` (via environment variables).
- Stops with a clear message and makes no network request if `DA_API_URL` or
  `DA_API_KEY` is missing.
- Requests a small sample (default: last 7 days of lodgements, up to
  `DA_RECORD_LIMIT` records, default 50).
- Saves the raw API response, untouched, under `data/raw/` with a timestamped
  filename.
- Loads the (limit-truncated) records into a local DuckDB database at
  `data/planning_pulse.duckdb`, table `raw_development_applications`.
- **Replaces** the contents of that table on every run (it does not append).
  Raw response files under `data/raw/` are timestamped and are never
  overwritten, so past downloads remain available even though the DuckDB
  table only ever holds the latest run's sample.

This script performs ingestion only — no cleaning, typing, or modelling.
That happens in dbt staging/mart models in a later iteration.
