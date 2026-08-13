-- Singular test: fails if any row in mart_application_activity_by_category
-- has a non-positive application_count. A passing test returns zero rows.

select
    council_name,
    development_type,
    application_status,
    application_count
from {{ ref('mart_application_activity_by_category') }}
where application_count <= 0
