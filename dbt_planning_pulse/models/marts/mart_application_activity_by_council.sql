{{
  config(
    materialized='table'
  )
}}

-- One row per council_name + application_status + application_type
-- combination, based on the local 100-record sample (fetched on demand,
-- filtered by ApplicationLastUpdatedFrom = 2025-01-01). Not representative
-- of all NSW planning activity and must not be used to rank councils.

select
    council_name,
    application_status,
    application_type,
    count(*)                     as application_count,
    sum(development_cost)        as total_development_cost,
    avg(development_cost)        as average_development_cost,
    max(date_last_updated)       as latest_source_updated_at

from {{ ref('stg_development_applications') }}

group by council_name, application_status, application_type
