# Architecture

Planning Pulse NSW follows a straightforward extract → load → transform → analyze pipeline.

## Pipeline overview

```mermaid
flowchart LR
    A[NSW Planning Portal<br/>Online DA API] -->|extract| B[(DuckDB<br/>raw layer)]
    B -->|dbt| C[dbt staging models]
    C -->|dbt| D[dbt marts]
    D --> E[Analysis / dashboard]
```

## Stages

### 1. NSW Planning Portal Online DA API

Source of truth for development-application records. See the source dataset page: https://www.data.nsw.gov.au/data/dataset/online-da-data-api

Council participation became mandatory in July 2021; earlier data reflects voluntary adoption only and should be treated as incomplete.

### 2. DuckDB raw layer

Raw API responses are landed into DuckDB tables with minimal transformation, preserving the source shape and field names as closely as practical. This layer is the single point of contact between extraction scripts and the rest of the pipeline.

### 3. dbt staging models

Staging models (`dbt_planning_pulse/models/staging`) clean and standardize the raw layer: consistent types, naming conventions, and light normalization. Staging models map one-to-one to raw sources and do not aggregate.

### 4. dbt marts

Mart models (`dbt_planning_pulse/models/marts`) join and aggregate staging models into analysis-ready tables, for example application volumes and decision timelines by council, development category, and time period.

### 5. Analysis / dashboard

Marts are queried directly (e.g. via DuckDB, notebooks, or a lightweight dashboard) to explore the data. Any presentation of results should carry forward the data caveats noted in the [README](../README.md#data-caveats), particularly around pre-July-2021 coverage and the non-causal, non-evaluative framing of the analysis.

## Design notes

- DuckDB is used as a single-file, dependency-light analytical database suitable for a local, reproducible portfolio project.
- dbt provides model layering, testing, and documentation without requiring a full warehouse deployment.
- No CI/CD or scheduling is configured in this iteration; the pipeline is intended to be run manually during development.
