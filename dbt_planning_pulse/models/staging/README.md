# Staging models

This directory is currently configuration only (`sources.yml`) — no staging
models exist yet, because no real extract had been loaded to build and test
them against at the time this project was scaffolded. See
[`docs/data_source.md`](../../../docs/data_source.md) for the API's request/response
shape.

## What staging models will do, once a real extract is loaded

Staging models will sit directly on top of the `raw.raw_development_applications`
source declared in `sources.yml`, one staging model per source table, and will:

- Select from the source and rename columns to consistent, documented names
  (the raw column names are whatever the NSW Online DA Data API happens to
  return, inferred by DuckDB's `read_json_auto()`).
- Cast fields to appropriate types — dates (e.g. lodgement, determination),
  numbers (e.g. cost of development), and flags (e.g. the API's `Y`/`N`
  strings) — based on the field types confirmed against a real extract.
- Apply light, non-lossy normalization only (e.g. trimming whitespace,
  standardizing casing of enumerated values such as council name or
  application status) — no joins, aggregation, or business logic.
- Map one-to-one with the source table: one staging model in, one clean
  table out, preserving grain and row count.

Aggregation and cross-table joins belong in `models/marts/`, not here.

## Why nothing is built yet

Building staging models against invented sample data would risk encoding
assumptions about column names or types that don't match the real API
response. Per this project's approach, staging models are built only after
a real sample has been ingested via `scripts/ingest_da_sample.py` and its
actual schema has been inspected.
