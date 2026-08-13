-- Singular test: fails if (application_number, development_type) is
-- duplicated in stg_development_application_categories. A passing test
-- returns zero rows.

select
    application_number,
    development_type,
    count(*) as duplicate_count
from {{ ref('stg_development_application_categories') }}
group by application_number, development_type
having count(*) > 1
