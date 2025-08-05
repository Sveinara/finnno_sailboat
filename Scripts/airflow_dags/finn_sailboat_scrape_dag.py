import sys
import logging
from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook

# Legg til scraper-mappen i Python-banen slik at Airflow finner den
sys.path.append('/full/sti/til/ditt/prosjekt/finnno_sailboat/scraper')

# Importer din egen funksjon fra scraper-filen
from scrape_boats import get_boat_ads_data

@dag(
    dag_id='finn_boat_scraper',
    start_date=datetime(2023, 10, 26),
    schedule_interval=timedelta(hours=4),  # Kjører hver 4. time
    catchup=False,
    tags=['finn', 'scraping', 'boats'],
    doc_md="""
    ### Finn.no Boat Scraper DAG
    Dette er en DAG som henter båtannonser fra Finn.no.
    - **Extract**: Kjører en Python-funksjon for å scrape data.
    - **Load**: Tar dataene og laster dem inn i en staging-tabell i Postgres.
    """
)
def finn_boat_scraper_dag():
    """
    ### DAG for å hente båtannonser

    Orkestrerer henting og lasting av data fra Finn.no.
    """

    @task(task_id="extract_boat_ads")
    def extract_data():
        """
        Kaller scraper-scriptet for å hente annonsedata.
        Dette er E-steget (Extract).
        """
        FINN_URL = "https://www.finn.no/boat/sailboat/search.html?sort=RELEVANCE"
        ads = get_boat_ads_data(url=FINN_URL)
        if not ads:
            raise ValueError("Ingen annonser funnet, stopper kjøringen.")
        return ads

    @task(task_id="load_to_staging")
    def load_data(ads: list[dict]):
        """
        Tar imot en liste med annonser og laster dem inn i
        staging_ads-tabellen i Postgres.
        Dette er L-steget (Load).
        """
        # Bruker Airflow Connection vi lagde tidligere
        pg_hook = PostgresHook(postgres_conn_id='postgres_finn_db')
        
        # Bruker en smart "UPSERT" for å sette inn nye rader.
        # Hvis en rad med samme ad_id og scraped_at allerede finnes,
        # gjør den ingenting (ON CONFLICT DO NOTHING).
        sql_insert = """
            INSERT INTO staging_ads (
                ad_id, title, price, location, year, length,
                image_url, ad_url, updated_text, scraped_at
            ) VALUES (
                %(ad_id)s, %(title)s, %(price)s, %(location)s, %(year)s, %(length)s,
                %(image_url)s, %(ad_url)s, %(updated_text)s, %(scraped_at)s
            ) ON CONFLICT (ad_id, scraped_at) DO NOTHING;
        """
        
        for ad in ads:
            pg_hook.run(sql_insert, parameters=ad)
            
        logging.info(f"Lastet {len(ads)} annonser inn i staging_ads.")

    # Definerer rekkefølgen på oppgavene
    extracted_ads = extract_data()
    load_data(extracted_ads)

# Instansierer DAGen så Airflow kan plukke den opp
finn_boat_scraper_dag()