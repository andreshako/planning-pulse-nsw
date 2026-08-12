{{
  config(
    materialized='view'
  )
}}

-- One row per development application, based on the current small,
-- unfiltered API sample (single page, no filters, ~50 records) ingested
-- via scripts/ingest_da_sample.py. Column presence and null rates have
-- only been verified against this sample, not the full dataset.

select
    PlanningPortalApplicationNumber            as application_number,
    Council.CouncilName                        as council_name,
    ApplicationStatus                          as application_status,
    ApplicationType                            as application_type,
    CostOfDevelopment                          as development_cost,
    NumberOfNewDwellings                       as number_of_new_dwellings,
    NumberOfStoreys                            as number_of_storeys,
    cast(DateLastUpdated as timestamp)         as date_last_updated

from {{ source('raw', 'raw_development_applications') }}
