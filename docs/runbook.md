# Runbook: local workflow

This is the normal sequence for running Planning Pulse NSW locally, end to end.

## 1. Setup

```bash
make setup
```

Creates `.venv` (if it doesn't already exist) and installs dependencies from
`requirements.txt`.

You also need a local dbt profile, created once:

```bash
cp dbt_planning_pulse/profiles.yml.example dbt_planning_pulse/profiles.yml
```

`dbt_planning_pulse/profiles.yml` is gitignored — each developer keeps their own copy.

## 2. (Optional) configure a sample filter

By default, ingestion fetches an unfiltered sample (up to 100 records, no date filter).
To narrow the sample, copy `.env.example` to `.env` and set:

- `DA_SAMPLE_SIZE` — number of records to fetch (capped at 100).
- `DA_APPLICATION_LAST_UPDATED_FROM` — only fetch applications updated on or after this
  date (`YYYY-MM-DD`).

`.env` is optional and gitignored; the script runs with sensible defaults if it's absent.

## 3. Ingest

```bash
make ingest
```

Fetches the sample from the public NSW Online DA Data API, saves a timestamped raw
JSON copy under `data/raw/`, and replaces the `raw_development_applications` table in
`data/planning_pulse.duckdb`.

## 4. Build and test

```bash
make build
```

Runs `dbt build` (models + tests) against the data just ingested. Fails clearly if
`dbt_planning_pulse/profiles.yml` or `data/planning_pulse.duckdb` doesn't exist yet —
see steps 1 and 3.

## 5. Generate and view docs

```bash
make docs
```

Generates dbt's static documentation site into `dbt_planning_pulse/target/`. Like
`make build`, this reads the DuckDB catalog, so it also requires
`data/planning_pulse.duckdb` to already exist (step 3).

To view the generated docs locally:

```bash
cd dbt_planning_pulse && DBT_PROFILES_DIR=. ../.venv/bin/dbt docs serve
```

This only serves the docs on your machine — it does not deploy or publish anything.

## CI vs local

GitHub Actions (`.github/workflows/dbt-quality-check.yml`) only runs `dbt parse` to
validate project structure (valid YAML, resolvable refs/sources, no syntax errors) —
mirrored locally by `make check`. It never touches the NSW API or real data. Running
the actual models and tests against a fresh sample (steps 3–4 above) is a manual,
local-only step, since the real DuckDB database and raw API sample are gitignored.
