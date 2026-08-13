{{
  config(
    materialized='view'
  )
}}

-- One row per application_number + development_type. Based on the same
-- 100-record sample as stg_development_applications (fetched on demand,
-- filtered by ApplicationLastUpdatedFrom = 2025-01-01). A single
-- application can have multiple development categories, so
-- application_number is not unique at this grain.

select
    PlanningPortalApplicationNumber            as application_number,
    unnest(DevelopmentType).DevelopmentType    as development_type

from {{ source('raw', 'raw_development_applications') }}
