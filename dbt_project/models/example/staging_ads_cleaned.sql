-- models/example/staging_ads_cleaned.sql

-- This is a simple dbt model that demonstrates a basic transformation.
-- It reads from the raw staging table populated by Airflow and creates a new, cleaned view.

with source_data as (

    -- In a real project, you would define "sailboat.staging_ads" as a dbt source.
    -- For simplicity, we select directly from it here.
    select
        ad_id,
        ad_url,
        price,
        specs_text,
        scraped_at
    from sailboat.staging_ads

)

select
    *,
    -- Example of a simple transformation: extract year from specs_text
    -- This is a very naive extraction and would need to be more robust in production.
    regexp_extract(specs_text, '(\d{4})') as extracted_year
from source_data
where
    -- Example of a simple filter: remove ads without a price
    price is not null
    and ad_id is not null