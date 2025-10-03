import sys
import os
from datetime import datetime
from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.operators.bash import BashOperator
from airflow.datasets import Dataset
import logging
import json
from minio import Minio
from minio.error import S3Error
from io import BytesIO

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

# Minio Connection Details from Environment Variables
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minio")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minio123")
MINIO_BUCKET_NAME = "raw-boat-data"


@dag(
    dag_id='sailboat_search_crawl',
    start_date=datetime(2023, 10, 26),
    schedule='0 7,18 * * *',
    catchup=False,
    tags=['finn', 'scraping', 'sailboat', 'crawl'],
    doc_md="""
    ### Sailboat Search Crawl
    - Hent resultatsider (search)
    - Arkiver rådata til Minio
    - Last inn i `sailboat.staging_ads`
    - Publiser dataset-oppdatering
    """
)
def sailboat_search_crawl():

    random_delay = BashOperator(
        task_id='random_delay',
        bash_command="""
if [ "{{ dag_run.conf.get('skip_delay', '0') }}" = "1" ]; then
  echo 'Hopper over delay (skip_delay=1)';
elif [ "{{ dag_run.conf.get('quick_run', '0') }}" = "1" ]; then
  echo 'Quick run - minimal delay';
  sleep 5;
else
  echo 'Normal delay - venter tilfeldig tid...';
  sleep $(( RANDOM % {{ dag_run.conf.get('max_delay', 7200) }} ));
fi
""",
    )

    @task(task_id="extract_all_boat_ads")
    def extract_data():
        FINN_URL = "https://www.finn.no/mobility/search/boat?class=2188&sales_form=120"
        ads = get_boat_ads_data(url=FINN_URL)
        if not ads:
            raise ValueError("Ingen annonser funnet, stopper kjøringen.")
        return ads

    @task(task_id="archive_and_load_to_staging", outlets=[STAGING_DATASET])
    def archive_and_load_data(ads: list, **kwargs) -> int:
        """
        Archives raw data to Minio and loads it into the Postgres staging table.
        """
        logical_date = kwargs['logical_date']

        # 1. Archive to Minio
        try:
            client = Minio(
                MINIO_ENDPOINT,
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY,
                secure=False # Since we are running in Docker network
            )

            # Make sure bucket exists
            found = client.bucket_exists(MINIO_BUCKET_NAME)
            if not found:
                client.make_bucket(MINIO_BUCKET_NAME)
                logging.info(f"Created bucket {MINIO_BUCKET_NAME}")
            else:
                logging.info(f"Bucket {MINIO_BUCKET_NAME} already exists")

            # Convert ads to JSON bytes
            json_data = json.dumps(ads, default=str, ensure_ascii=False, indent=2).encode('utf-8')
            json_stream = BytesIO(json_data)

            # Create a unique object name
            object_name = f"finn-boats-{logical_date.strftime('%Y-%m-%dT%H-%M-%S')}.json"

            client.put_object(
                MINIO_BUCKET_NAME,
                object_name,
                json_stream,
                length=len(json_data),
                content_type='application/json'
            )
            logging.info(f"Successfully uploaded {object_name} to Minio bucket {MINIO_BUCKET_NAME}.")

        except S3Error as exc:
            logging.error("Error occurred with Minio.", exc_info=True)
            raise

        # 2. Load to Postgres
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
            try:
                # Ensure ad_id is present before casting
                if ad.get('ad_id') is None:
                    logging.warning(f"Skipping ad with missing ad_id: {ad}")
                    continue
                result = pg_hook.run(sql_insert, parameters=ad, handler=lambda cursor: getattr(cursor, 'rowcount', 0))
                if isinstance(result, int) and result > 0:
                    inserted_count += result
            except Exception as e:
                logging.error(f"Failed to insert ad {ad.get('ad_id')}: {e}")

        logging.info(f"Attempted to load {len(ads)} ads. {inserted_count} new rows were inserted into sailboat.staging_ads.")
        return inserted_count


    extracted_ads = extract_data()
    loaded = archive_and_load_data(extracted_ads)

    random_delay >> extracted_ads >> loaded


sailboat_search_crawl()