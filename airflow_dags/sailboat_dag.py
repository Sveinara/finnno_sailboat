import sys
import os
from datetime import datetime
from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.operators.bash import BashOperator
import logging
# ✅ Import direkte fra scraper-mappen som er på PYTHONPATH
from scrape_boats import get_boat_ads_data

@dag(
    dag_id='sailboat_dag', # Endret navnet for å markere at det er en ny versjon
    start_date=datetime(2023, 10, 26),
    schedule='0 7,18 * * *', # Kjører 07:00 og 18:00
    catchup=False,
    tags=['finn', 'scraping', 'sailboat'],
    doc_md="""
    ### Finn.no Sailboat Scraper DAG 
    Henter ALLE seilbåtannonser fra Finn.no ved å følge paginering.
    - **Random Delay**: Venter et tilfeldig antall sekunder (0-2 timer).
    - **Extract**: Kjører Python-funksjon for å scrape data over flere sider.
    - **Load**: Laster data inn i en staging-tabell i Postgres.
    """
)
def sailboat_dag():

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

    @task(task_id="extract_all_boat_ads")
    def extract_data():
        """
        Kaller scraper-scriptet for å hente annonsedata.
        Dette er E-steget (Extract).
        """
        # VIKTIG: Bruker den nye, korrekte URL-en fra scriptet ditt!
        FINN_URL = "https://www.finn.no/mobility/search/boat?class=2188&sales_form=120"
        
        # Vi kaller funksjonen kun med den obligatoriske input-en.
        # max_pages og output_path bruker default-verdiene.
        ads = get_boat_ads_data(url=FINN_URL)
        
        if not ads:
            raise ValueError("Ingen annonser funnet, stopper kjøringen.")
        return ads

    @task(task_id="load_to_staging")
    def load_data(ads: list[dict]):
        """
        Lagrer kun: ad_id, ad_url, price, specs_text, scraped_at
        i databasen 'postgres', schema 'sailboat', tabell 'staging_ads'.
        """
        pg_hook = PostgresHook(postgres_conn_id='postgres_finn_db')
        
        # Sørg for at schema og tabell finnes (fully-qualified) og legg til manglende kolonner/indeks
        sql_create = """
        CREATE SCHEMA IF NOT EXISTS sailboat;
        -- Minimal table to ensure it exists
        CREATE TABLE IF NOT EXISTS sailboat.staging_ads (
            ad_id TEXT NOT NULL
        );
        -- Add expected columns if missing
        ALTER TABLE sailboat.staging_ads
            ADD COLUMN IF NOT EXISTS ad_url TEXT,
            ADD COLUMN IF NOT EXISTS price INTEGER,
            ADD COLUMN IF NOT EXISTS specs_text TEXT,
            ADD COLUMN IF NOT EXISTS scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
        -- Ensure a uniqueness constraint for upsert behavior
        CREATE UNIQUE INDEX IF NOT EXISTS idx_staging_ads_adid_scraped_at
            ON sailboat.staging_ads (ad_id, scraped_at);
        """
        pg_hook.run(sql_create)
        
        sql_insert = """
        INSERT INTO sailboat.staging_ads (
            ad_id, ad_url, price, specs_text, scraped_at
        ) VALUES (
            %(ad_id)s, %(ad_url)s, %(price)s, %(specs_text)s, %(scraped_at)s
        ) ON CONFLICT (ad_id, scraped_at) DO NOTHING;
        """
        
        inserted_count = 0
        for ad in ads:
            result = pg_hook.run(sql_insert, parameters=ad, handler=lambda cursor: cursor.rowcount)
            if result > 0:
                inserted_count += 1
        logging.info(f"Forsøkte å laste {len(ads)} annonser. {inserted_count} nye rader ble satt inn i sailboat.staging_ads.")

    # Definerer rekkefølgen på oppgavene
    extracted_ads = extract_data()
    load_data(extracted_ads)

    # Sett avhengigheten
    random_delay >> extracted_ads

# Instansierer DAGen
sailboat_dag()