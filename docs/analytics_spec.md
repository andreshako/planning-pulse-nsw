# Analytics specification

This document is the rulebook for what Planning Pulse NSW measures, how, and
with what caveats. It is written **before** any real extract has been
inspected, so every measure, dimension, and field name below is explicitly
marked provisional. Nothing here should be treated as a confirmed data
contract until checked against real data — see
[First extract checklist](#first-extract-checklist).

## Purpose

Planning Pulse NSW describes patterns in publicly available NSW development
application (DA) data: how many applications are lodged, and how long they
take to reach a recorded decision, broken down by time, council, and
development category. It is descriptive reporting, not an evaluation of
council performance, process quality, or planning outcomes. See
[Interpretation limits](#interpretation-limits).

## Unit of analysis

**One development application record**, as returned by the NSW Online DA
Data API, is intended to be one row of analysis.

This is provisional pending verification: it assumes the API returns one
record per application (not, for example, one row per status change or per
address on a multi-address application). Confirm this against the raw
schema and sample values from the first real extract before relying on it.

## Proposed measures (provisional until source fields are verified)

All of the following depend on field names and types that have not yet been
confirmed against a real API response (see
[`docs/data_source.md`](data_source.md) for the documented-but-unverified
field list). Do not treat any of these as final until the
[First extract checklist](#first-extract-checklist) has been completed.

- **Application volume** — count of application records, by dimension and
  time period.
- **Lodgement date** — the date an application was recorded as lodged.
- **Decision date** — the date an application reached a recorded
  determination.
- **Outcome / status** — the recorded application status or determination
  outcome.
- **Calendar-day decision timeline** — see precise definition below.

### Decision-timeline definition

```
decision_timeline_days = recorded_decision_date − recorded_lodgement_date
```

- Expressed in **calendar days** (not business days).
- A record is **excluded from the metric** if it has a missing lodgement
  date, a missing decision date, or a negative timeline (decision date
  before lodgement date).
- Excluded records are **not silently dropped**: their counts are reported
  separately (e.g. "N records excluded: missing lodgement date", "N records
  excluded: missing decision date", "N records excluded: negative
  timeline"), so data completeness stays visible alongside the metric.
- This definition measures time between two *recorded* dates in the portal.
  It does not measure elapsed working time, time under active assessment,
  or any other process-aware duration — see
  [Interpretation limits](#interpretation-limits).

## Proposed dimensions (provisional)

- **Time period** — derived from lodgement date (e.g. month, quarter, year),
  once its type and format are confirmed.
- **Council / local government area** — as recorded on the application.
- **Application category / type** — as recorded on the application (the
  data dictionary describes both a `DevelopmentCategory`-style field and an
  `ApplicationType`-style field; which one — or both — is analytically
  useful should be confirmed against real values).
- **Application status / outcome** — as recorded on the application.

## Data-quality validation checklist (run after the first extract)

Run all of the following against the first real extract before building any
staging model or metric on top of it. Record the results in
[`docs/data_source.md`](data_source.md) or a follow-up note.

1. **Record grain / duplicates** — confirm one row per application as
   expected under [Unit of analysis](#unit-of-analysis); check for exact
   duplicate rows and for repeated application identifiers.
2. **Required-field null rates** — for each field the proposed measures and
   dimensions depend on (lodgement date, decision date, status, council,
   category), measure the proportion of nulls or blanks.
3. **Date parsing** — confirm date fields parse cleanly and consistently
   into an unambiguous format; check for mixed formats or unparseable
   values.
4. **Date ordering** — check how many records have a decision date earlier
   than their lodgement date, and how many have a decision date but no
   lodgement date or vice versa.
5. **Category consistency** — list distinct values for category/type
   fields; check for near-duplicates (casing, whitespace, synonyms) against
   the documented enumerations.
6. **Status consistency** — list distinct values for the status/outcome
   field; check for near-duplicates and confirm coverage against the
   documented enumerations.
7. **Scope / coverage checks** — confirm which councils and date ranges are
   actually present in the extract, and cross-check against the July 2021
   mandatory-adoption caveat (see below).

## Interpretation limits

- This project does not measure the full planning process. It reports what
  is recorded in the NSW Planning Portal at two points in time (lodgement
  and decision); it does not capture pre-lodgement activity, informal
  negotiation, or post-decision appeals and modifications.
- **No causal claims.** Differences in volume or timeline across councils,
  categories, or periods may reflect differences in application mix, data
  entry practices, or portal coverage, not differences in efficiency or
  effort.
- **No council performance ranking.** Timelines and volumes are not used to
  rank or compare council performance.
- **No claims about reasons for delay.** The data does not record why a
  given application took as long as it did; this project does not infer or
  assert causes.
- **NSW Planning Portal coverage caveats.** Council participation in the
  portal became mandatory only from **1 July 2021**. Data from before that
  date reflects voluntary council adoption and is likely incomplete.
  Comparisons spanning that boundary should be avoided or explicitly
  caveated in any output.

## First extract checklist

When live API credentials arrive:

1. Run the ingestion script (`python scripts/ingest_da_sample.py`) to fetch
   a real sample into `data/raw/` and `raw_development_applications`.
2. Inspect the raw schema and sample values directly (e.g. via DuckDB) —
   actual column names, types, and a sample of distinct values for
   category/status/council fields.
3. Update [`docs/data_source.md`](data_source.md) and
   [`dbt_planning_pulse/models/staging/sources.yml`](../dbt_planning_pulse/models/staging/sources.yml)
   with verified column definitions, replacing the "not yet verified" notes.
4. Run the [data-quality validation checklist](#data-quality-validation-checklist-run-after-the-first-extract)
   above and record the results.
5. Only then, build staging models and dbt tests on top of the confirmed
   schema — not before.
