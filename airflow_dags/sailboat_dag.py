import sys
import os
from datetime import datetime
from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.operators.bash import BashOperator
import logging
import json

# Sørg for at prosjektroten og scraper-mappen er på sys.path ved Airflow-import
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
SCRAPER_DIR = os.path.join(PROJECT_ROOT, 'scraper')
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)
if SCRAPER_DIR not in sys.path:
    sys.path.append(SCRAPER_DIR)

# ✅ Import fra scraper-pakken
from scraper.scrape_boats import get_boat_ads_data
from scraper.parse_item import fetch_and_parse_item

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
    - **Item**: Beregner kandidater, henter item-detaljer, oppdaterer master og pris-historikk.
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

        CREATE TABLE IF NOT EXISTS sailboat.ads (
          ad_id TEXT PRIMARY KEY,
          ad_url TEXT,
          title TEXT,
          year INT,
          make TEXT,
          model TEXT,
          material TEXT,
          weight_kg INT,
          width_cm INT,
          depth_cm INT,
          sleepers INT,
          seats INT,
          engine_make TEXT,
          engine_type TEXT,
          engine_effect_hp INT,
          boat_max_speed_knots INT,
          registration_number TEXT,
          municipality TEXT,
          county TEXT,
          postal_code TEXT,
          lat DOUBLE PRECISION,
          lng DOUBLE PRECISION,
          latest_price INT,
          first_seen_at TIMESTAMPTZ,
          last_seen_at TIMESTAMPTZ,
          last_scraped_at TIMESTAMPTZ,
          last_edited_at TIMESTAMPTZ,
          active BOOLEAN DEFAULT TRUE,
          source_raw JSONB
        );

        CREATE TABLE IF NOT EXISTS sailboat.price_history (
          ad_id TEXT NOT NULL,
          price INT NOT NULL,
          changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS sailboat.staging_item_details (
          ad_id TEXT NOT NULL,
          scraped_at TIMESTAMPTZ NOT NULL,
          source_json JSONB,
          title TEXT,
          year INT,
          make TEXT,
          model TEXT,
          material TEXT,
          weight_kg INT,
          width_cm INT,
          depth_cm INT,
          sleepers INT,
          seats INT,
          engine_make TEXT,
          engine_type TEXT,
          engine_effect_hp INT,
          boat_max_speed_knots INT,
          registration_number TEXT,
          municipality TEXT,
          county TEXT,
          postal_code TEXT,
          lat DOUBLE PRECISION,
          lng DOUBLE PRECISION
        );
        """
        pg_hook.run(sql_create)

    @task(task_id="extract_all_boat_ads")
    def extract_data():
        """
        Kaller scraper-scriptet for å hente annonsedata.
        Dette er E-steget (Extract).
        """
        FINN_URL = "https://www.finn.no/mobility/search/boat?class=2188&sales_form=120"
        ads = get_boat_ads_data(url=FINN_URL)
        if not ads:
            raise ValueError("Ingen annonser funnet, stopper kjøringen.")
        return ads

    @task(task_id="load_to_staging")
    def load_data(ads) -> int:
        """
        Lagrer kun: ad_id, ad_url, price, specs_text, scraped_at
        i databasen 'postgres', schema 'sailboat', tabell 'staging_ads'.
        Returnerer antall innsatte rader.
        """
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

        CREATE TABLE IF NOT EXISTS sailboat.ads (
          ad_id TEXT PRIMARY KEY,
          ad_url TEXT,
          title TEXT,
          year INT,
          make TEXT,
          model TEXT,
          material TEXT,
          weight_kg INT,
          width_cm INT,
          depth_cm INT,
          sleepers INT,
          seats INT,
          engine_make TEXT,
          engine_type TEXT,
          engine_effect_hp INT,
          boat_max_speed_knots INT,
          registration_number TEXT,
          municipality TEXT,
          county TEXT,
          postal_code TEXT,
          lat DOUBLE PRECISION,
          lng DOUBLE PRECISION,
          latest_price INT,
          first_seen_at TIMESTAMPTZ,
          last_seen_at TIMESTAMPTZ,
          last_scraped_at TIMESTAMPTZ,
          last_edited_at TIMESTAMPTZ,
          active BOOLEAN DEFAULT TRUE,
          source_raw JSONB
        );

        CREATE TABLE IF NOT EXISTS sailboat.price_history (
          ad_id TEXT NOT NULL,
          price INT NOT NULL,
          changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS sailboat.staging_item_details (
          ad_id TEXT NOT NULL,
          scraped_at TIMESTAMPTZ NOT NULL,
          source_json JSONB,
          title TEXT,
          year INT,
          make TEXT,
          model TEXT,
          material TEXT,
          weight_kg INT,
          width_cm INT,
          depth_cm INT,
          sleepers INT,
          seats INT,
          engine_make TEXT,
          engine_type TEXT,
          engine_effect_hp INT,
          boat_max_speed_knots INT,
          registration_number TEXT,
          municipality TEXT,
          county TEXT,
          postal_code TEXT,
          lat DOUBLE PRECISION,
          lng DOUBLE PRECISION
        );
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
            result = pg_hook.run(sql_insert, parameters=ad, handler=lambda cursor: getattr(cursor, 'rowcount', 0))
            if isinstance(result, int) and result > 0:
                inserted_count += result
        logging.info(f"Forsøkte å laste {len(ads)} annonser. {inserted_count} nye rader ble satt inn i sailboat.staging_ads.")
        return inserted_count

    @task(task_id="compute_crawl_candidates")
    def compute_crawl_candidates():
        pg = PostgresHook(postgres_conn_id='postgres_finn_db')
        sql = """
        WITH latest AS (
          SELECT DISTINCT ON (ad_id) ad_id, ad_url, price, scraped_at
          FROM sailboat.staging_ads
          ORDER BY ad_id, scraped_at DESC
        ),
        new_ads AS (
          SELECT l.ad_id
          FROM latest l
          LEFT JOIN sailboat.ads a ON a.ad_id = l.ad_id
          WHERE a.ad_id IS NULL
        ),
        price_changed AS (
          SELECT l.ad_id
          FROM latest l
          JOIN sailboat.ads a ON a.ad_id = l.ad_id
          WHERE COALESCE(a.latest_price, -1) <> COALESCE(l.price, -1)
        ),
        stale_refresh AS (
          SELECT a.ad_id
          FROM sailboat.ads a
          WHERE a.active = TRUE
            AND (a.last_scraped_at IS NULL OR a.last_scraped_at < NOW() - INTERVAL '24 hours')
        ),
        random_sample AS (
          SELECT a.ad_id
          FROM sailboat.ads a
          WHERE a.active = TRUE AND random() < 0.05
        )
        SELECT DISTINCT ad_id
        FROM (
          SELECT ad_id FROM new_ads
          UNION ALL
          SELECT ad_id FROM price_changed
          UNION ALL
          SELECT ad_id FROM stale_refresh
          UNION ALL
          SELECT ad_id FROM random_sample
        ) q;
        """
        rows = pg.get_records(sql)
        ad_ids = [r[0] for r in rows]
        logging.info(f"Crawl candidates: {len(ad_ids)}")
        return ad_ids

    @task(task_id="fetch_item_details")
    def fetch_item_details(ad_ids) -> int:
        pg = PostgresHook(postgres_conn_id='postgres_finn_db')
        if not ad_ids:
            logging.info("Ingen kandidater denne runden")
            return 0
        sql_latest = """
        WITH latest AS (
          SELECT DISTINCT ON (ad_id) ad_id, ad_url
          FROM sailboat.staging_ads
          ORDER BY ad_id, scraped_at DESC
        )
        SELECT ad_id, ad_url FROM latest WHERE ad_id = ANY(%s);
        """
        rows = pg.get_records(sql_latest, parameters=(ad_ids,))
        count = 0
        for ad_id, ad_url in rows:
            res = fetch_and_parse_item(ad_url)
            if not res:
                continue
            normalized, source_pack = res
            normalized['ad_id'] = normalized.get('ad_id') or ad_id
            pg.run(
                """
                INSERT INTO sailboat.staging_item_details (
                  ad_id, scraped_at, source_json, title, year, make, model, material, weight_kg,
                  width_cm, depth_cm, sleepers, seats, engine_make, engine_type, engine_effect_hp,
                  boat_max_speed_knots, registration_number, municipality, county, postal_code, lat, lng
                ) VALUES (
                  %(ad_id)s, %(scraped_at)s, %(source_json)s, %(title)s, %(year)s, %(make)s, %(model)s, %(material)s, %(weight_kg)s,
                  %(width_cm)s, %(depth_cm)s, %(sleepers)s, %(seats)s, %(engine_make)s, %(engine_type)s, %(engine_effect_hp)s,
                  %(boat_max_speed_knots)s, %(registration_number)s, %(municipality)s, %(county)s, %(postal_code)s, %(lat)s, %(lng)s
                );
                """,
                parameters={
                    'ad_id': normalized.get('ad_id'),
                    'scraped_at': normalized.get('scraped_at'),
                    'source_json': json.dumps(source_pack, ensure_ascii=False),
                    'title': normalized.get('title'),
                    'year': normalized.get('year'),
                    'make': normalized.get('make'),
                    'model': normalized.get('model'),
                    'material': normalized.get('material'),
                    'weight_kg': normalized.get('weight_kg'),
                    'width_cm': normalized.get('width_cm'),
                    'depth_cm': normalized.get('depth_cm'),
                    'sleepers': normalized.get('sleepers'),
                    'seats': normalized.get('seats'),
                    'engine_make': normalized.get('engine_make'),
                    'engine_type': normalized.get('engine_type'),
                    'engine_effect_hp': normalized.get('engine_effect_hp'),
                    'boat_max_speed_knots': normalized.get('boat_max_speed_knots'),
                    'registration_number': normalized.get('registration_number'),
                    'municipality': normalized.get('municipality'),
                    'county': normalized.get('county'),
                    'postal_code': normalized.get('postal_code'),
                    'lat': normalized.get('lat'),
                    'lng': normalized.get('lng'),
                }
            )
            count += 1
        logging.info(f"Item-detaljer hentet for {count} annonser")
        return count

    @task(task_id="upsert_master_and_prices")
    def upsert_master_and_prices() -> bool:
        pg = PostgresHook(postgres_conn_id='postgres_finn_db')
        sql = """
        WITH latest AS (
          SELECT DISTINCT ON (ad_id) ad_id, ad_url, price, scraped_at
          FROM sailboat.staging_ads
          ORDER BY ad_id, scraped_at DESC
        ),
        details AS (
          SELECT DISTINCT ON (ad_id) *
          FROM sailboat.staging_item_details
          ORDER BY ad_id, scraped_at DESC
        ),
        upserted AS (
          INSERT INTO sailboat.ads (
            ad_id, ad_url, title, year, make, model, material, weight_kg, width_cm, depth_cm,
            sleepers, seats, engine_make, engine_type, engine_effect_hp, boat_max_speed_knots,
            registration_number, municipality, county, postal_code, lat, lng,
            latest_price, first_seen_at, last_seen_at, last_scraped_at, last_edited_at, active, source_raw
          )
          SELECT 
            COALESCE(d.ad_id, l.ad_id) AS ad_id,
            l.ad_url,
            d.title, d.year, d.make, d.model, d.material, d.weight_kg, d.width_cm, d.depth_cm,
            d.sleepers, d.seats, d.engine_make, d.engine_type, d.engine_effect_hp, d.boat_max_speed_knots,
            d.registration_number, d.municipality, d.county, d.postal_code, d.lat, d.lng,
            l.price AS latest_price,
            l.scraped_at AS first_seen_at,
            l.scraped_at AS last_seen_at,
            l.scraped_at AS last_scraped_at,
            NULL::timestamptz AS last_edited_at,
            TRUE AS active,
            d.source_json
          FROM latest l
          LEFT JOIN details d ON d.ad_id = l.ad_id
          ON CONFLICT (ad_id) DO UPDATE SET
            ad_url = EXCLUDED.ad_url,
            title = COALESCE(EXCLUDED.title, sailboat.ads.title),
            year = COALESCE(EXCLUDED.year, sailboat.ads.year),
            make = COALESCE(EXCLUDED.make, sailboat.ads.make),
            model = COALESCE(EXCLUDED.model, sailboat.ads.model),
            material = COALESCE(EXCLUDED.material, sailboat.ads.material),
            weight_kg = COALESCE(EXCLUDED.weight_kg, sailboat.ads.weight_kg),
            width_cm = COALESCE(EXCLUDED.width_cm, sailboat.ads.width_cm),
            depth_cm = COALESCE(EXCLUDED.depth_cm, sailboat.ads.depth_cm),
            sleepers = COALESCE(EXCLUDED.sleepers, sailboat.ads.sleepers),
            seats = COALESCE(EXCLUDED.seats, sailboat.ads.seats),
            engine_make = COALESCE(EXCLUDED.engine_make, sailboat.ads.engine_make),
            engine_type = COALESCE(EXCLUDED.engine_type, sailboat.ads.engine_type),
            engine_effect_hp = COALESCE(EXCLUDED.engine_effect_hp, sailboat.ads.engine_effect_hp),
            boat_max_speed_knots = COALESCE(EXCLUDED.boat_max_speed_knots, sailboat.ads.boat_max_speed_knots),
            registration_number = COALESCE(EXCLUDED.registration_number, sailboat.ads.registration_number),
            municipality = COALESCE(EXCLUDED.municipality, sailboat.ads.municipality),
            county = COALESCE(EXCLUDED.county, sailboat.ads.county),
            postal_code = COALESCE(EXCLUDED.postal_code, sailboat.ads.postal_code),
            lat = COALESCE(EXCLUDED.lat, sailboat.ads.lat),
            lng = COALESCE(EXCLUDED.lng, sailboat.ads.lng),
            latest_price = EXCLUDED.latest_price,
            last_seen_at = EXCLUDED.last_seen_at,
            last_scraped_at = EXCLUDED.last_scraped_at,
            active = TRUE,
            source_raw = COALESCE(EXCLUDED.source_raw, sailboat.ads.source_raw)
          RETURNING ad_id
        ),
        price_change AS (
          SELECT a.ad_id, a.latest_price AS old_price, l.price AS new_price, l.scraped_at
          FROM sailboat.ads a
          JOIN latest l ON l.ad_id = a.ad_id
          WHERE COALESCE(a.latest_price, -1) <> COALESCE(l.price, -1)
        )
        INSERT INTO sailboat.price_history (ad_id, price, changed_at)
        SELECT ad_id, new_price, scraped_at FROM price_change;
        """
        pg.run(sql)
        logging.info("Master upsert og pris-historikk oppdatert")
        return True

    @task(task_id="mark_inactive")
    def mark_inactive() -> int:
        pg = PostgresHook(postgres_conn_id='postgres_finn_db')
        sql = """
        WITH latest AS (
          SELECT DISTINCT ON (ad_id) ad_id
          FROM sailboat.staging_ads
          ORDER BY ad_id, scraped_at DESC
        )
        UPDATE sailboat.ads a
        SET active = FALSE
        WHERE a.active = TRUE
          AND NOT EXISTS (SELECT 1 FROM latest l WHERE l.ad_id = a.ad_id)
        RETURNING ad_id;
        """
        rows = pg.get_records(sql)
        logging.info(f"Markerte {len(rows)} annonser som inaktive i denne runden")
        return len(rows)

    init_task = init_schema()
    extracted_ads = extract_data()
    loaded = load_data(extracted_ads)
    candidates = compute_crawl_candidates()
    fetched = fetch_item_details(candidates)
    upserted = upsert_master_and_prices()
    marked = mark_inactive()

    init_task >> random_delay
    random_delay >> extracted_ads
    extracted_ads >> loaded >> candidates >> fetched >> upserted >> marked

sailboat_dag()