import sys
import os
from datetime import datetime
from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
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
    dag_id='sailboat_search_crawl_quick',
    start_date=datetime(2023, 10, 26),
    schedule=None,  # Kun manuell kjøring
    catchup=False,
    tags=['finn', 'scraping', 'sailboat', 'crawl', 'quick', 'testing'],
    doc_md="""
    ### Sailboat Search Crawl (Quick)
    - **RASK VERSJON** - ingen tilfeldig delay
    - Hent resultatsider (search) umiddelbart
    - Last inn i `sailboat.staging_ads`
    - Publiser dataset-oppdatering
    - Perfekt for testing og debugging
    """
)
def sailboat_search_crawl_quick():

    @task(task_id="extract_all_boat_ads")
    def extract_data():
        FINN_URL = "https://www.finn.no/mobility/search/boat?class=2188&sales_form=120"
        logging.info("QUICK RUN - starter umiddelbart uten delay")
        ads = get_boat_ads_data(url=FINN_URL)
        if not ads:
            raise ValueError("Ingen annonser funnet, stopper kjøringen.")
        logging.info(f"QUICK RUN - fant {len(ads)} annonser")
        return ads

    @task(task_id="load_to_staging", outlets=[STAGING_DATASET])
    def load_data(ads) -> int:
        pg_hook = PostgresHook(postgres_conn_id='postgres_finn_db')
        sql_insert = """
        INSERT INTO sailboat.staging_ads (
            ad_id, ad_url, price, specs_text, scraped_at
        ) VALUES (
            CAST(%(ad_id)s AS BIGINT), %(ad_url)s, %(price)s, %(specs_text)s, %(scraped_at)s
        ) ON CONFLICT (ad_id, scraped_at) DO NOTHING;
        """
        inserted_count = 0
        for ad in ads:
            result = pg_hook.run(sql_insert, parameters=ad, handler=lambda cursor: getattr(cursor, 'rowcount', 0))
            if isinstance(result, int) and result > 0:
                inserted_count += result
        logging.info(f"QUICK RUN - lastet {len(ads)} annonser. {inserted_count} nye rader i staging_ads.")
        return inserted_count

    extracted_ads = extract_data()
    loaded = load_data(extracted_ads)

    # Ingen delay-task i quick versjon
    extracted_ads >> loaded


sailboat_search_crawl_quick() 