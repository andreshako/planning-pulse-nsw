{{
  config(
    materialized='table'
  )
}}

-- One row per council_name + development_type + application_status,
-- based on the local 100-record sample (fetched on demand, filtered by
-- ApplicationLastUpdatedFrom = 2025-01-01). Not representative of all
-- NSW planning activity and must not be used to rank councils.
--
-- (application_number, development_type) is unique in
-- stg_development_application_categories, so an application contributes
-- at most one row per development_type group here — cost figures are
-- not double-counted within a group, even though the same application
-- can appear in multiple development_type groups.

select
    applications.council_name,
    categories.development_type,
    applications.application_status,
    count(distinct applications.application_number)   as application_count,
    sum(applications.development_cost)                 as total_development_cost,
    avg(applications.development_cost)                 as average_development_cost,
    max(applications.date_last_updated)                 as latest_source_updated_at

from {{ ref('stg_development_application_categories') }} as categories

inner join {{ ref('stg_development_applications') }} as applications
    on categories.application_number = applications.application_number

group by 1, 2, 3
