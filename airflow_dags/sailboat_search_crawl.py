import sys
import os
from datetime import datetime
from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.operators.bash import BashOperator
from airflow.datasets import Dataset
import logging

# Sørg for at prosjektroten og scraper-mappen er på sys.path ved Airflow-import
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
SCRAPER_DIR = os.path.join(PROJECT_ROOT, 'scraper')
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)
if SCRAPER_DIR not in sys.path:
    sys.path.append(SCRAPER_DIR)

from scraper.scrape_boats import get_boat_ads_data  # type: ignore

STAGING_DATASET = Dataset("db://sailboat/staging_ads")


@dag(
    dag_id='sailboat_search_crawl',
    start_date=datetime(2023, 10, 26),
    schedule='0 7,18 * * *',
    catchup=False,
    tags=['finn', 'scraping', 'sailboat', 'crawl'],
    doc_md="""
    ### Sailboat Search Crawl
    - Init schema/tabeller
    - Hent resultatsider (search)
    - Last inn i sailboat.staging_ads
    - Publiser dataset-oppdatering
    """
)
def sailboat_search_crawl():

    random_delay = BashOperator(
        task_id='random_delay',
        bash_command="""
if [ "{{ dag_run.conf.get('skip_delay', '0') }}" = "1" ]; then
  echo 'Skipping delay';
else
  sleep $(( RANDOM % {{ dag_run.conf.get('max_delay', 7200) }} ));
fi
""",
    )

    @task(task_id="init_schema")
    def init_schema() -> None:
        pg_hook = PostgresHook(postgres_conn_id='postgres_finn_db')
        sql_create = """
        CREATE SCHEMA IF NOT EXISTS sailboat;

        CREATE TABLE IF NOT EXISTS sailboat.staging_ads (
            ad_id TEXT NOT NULL
        );
        ALTER TABLE sailboat.staging_ads
            ADD COLUMN IF NOT EXISTS ad_url TEXT,
            ADD COLUMN IF NOT EXISTS price INTEGER,
            ADD COLUMN IF NOT EXISTS specs_text TEXT,
            ADD COLUMN IF NOT EXISTS scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
        CREATE UNIQUE INDEX IF NOT EXISTS idx_staging_ads_adid_scraped_at
            ON sailboat.staging_ads (ad_id, scraped_at);
        """
        pg_hook.run(sql_create)

    @task(task_id="extract_all_boat_ads")
    def extract_data():
        FINN_URL = "https://www.finn.no/mobility/search/boat?class=2188&sales_form=120"
        ads = get_boat_ads_data(url=FINN_URL)
        if not ads:
            raise ValueError("Ingen annonser funnet, stopper kjøringen.")
        return ads

    @task(task_id="load_to_staging", outlets=[STAGING_DATASET])
    def load_data(ads) -> int:
        pg_hook = PostgresHook(postgres_conn_id='postgres_finn_db')
        sql_insert = """
        INSERT INTO sailboat.staging_ads (
            ad_id, ad_url, price, specs_text, scraped_at
        ) VALUES (
            %(ad_id)s, %(ad_url)s, %(price)s, %(specs_text)s, %(scraped_at)s
        ) ON CONFLICT (ad_id, scraped_at) DO NOTHING;
        """
        inserted_count = 0
        for ad in ads:
            result = pg_hook.run(sql_insert, parameters=ad, handler=lambda cursor: getattr(cursor, 'rowcount', 0))
            if isinstance(result, int) and result > 0:
                inserted_count += result
        logging.info(f"Forsøkte å laste {len(ads)} annonser. {inserted_count} nye rader ble satt inn i sailboat.staging_ads.")
        return inserted_count

    init_task = init_schema()
    extracted_ads = extract_data()
    loaded = load_data(extracted_ads)

    init_task >> random_delay
    random_delay >> extracted_ads >> loaded


sailboat_search_crawl() 