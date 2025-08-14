import sys
import os
from datetime import datetime
from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.datasets import Dataset

# Sørg for at prosjektroten er på sys.path ved Airflow-import
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

DB_READY_DATASET = Dataset("db://sailboat/schema_ready")


@dag(
    dag_id='sailboat_db_init',
    start_date=datetime(2023, 10, 26),
    schedule=None,
    catchup=False,
    tags=['db', 'schema', 'bootstrap', 'sailboat'],
    doc_md="""
    ### Sailboat DB Init
    - Oppretter `sailboat`-skjema og alle nødvendige tabeller
    - Idempotent: trygt å kjøre flere ganger
    - Publiserer dataset `db://sailboat/schema_ready`
    """
)
def sailboat_db_init():

    @task(task_id="init_schema", outlets=[DB_READY_DATASET])
    def init_schema() -> None:
        pg = PostgresHook(postgres_conn_id='postgres_finn_db')
        sql = """
        CREATE SCHEMA IF NOT EXISTS sailboat;

        -- staging_ads
        CREATE TABLE IF NOT EXISTS sailboat.staging_ads (
            ad_id BIGINT NOT NULL,
            ad_url TEXT,
            price INTEGER,
            specs_text TEXT,
            scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (ad_id, scraped_at)
        );
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='sailboat' AND table_name='staging_ads'
                AND column_name='ad_id' AND data_type IN ('text','character varying')
            ) THEN
                ALTER TABLE sailboat.staging_ads
                    ALTER COLUMN ad_id TYPE BIGINT USING NULLIF(ad_id, '')::bigint;
            END IF;
        END $$;

        -- staging_item_details
        CREATE TABLE IF NOT EXISTS sailboat.staging_item_details (
            ad_id BIGINT NOT NULL,
            scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            source_json JSONB,
            title TEXT,
            year INTEGER,
            make TEXT,
            model TEXT,
            material TEXT,
            weight_kg INTEGER,
            width_cm INTEGER,
            depth_cm INTEGER,
            sleepers INTEGER,
            seats INTEGER,
            engine_make TEXT,
            engine_type TEXT,
            engine_effect_hp INTEGER,
            boat_max_speed_knots INTEGER,
            registration_number TEXT,
            municipality TEXT,
            county TEXT,
            postal_code TEXT,
            lat DOUBLE PRECISION,
            lng DOUBLE PRECISION,
            PRIMARY KEY (ad_id, scraped_at)
        );

        -- ads (master)
        CREATE TABLE IF NOT EXISTS sailboat.ads (
            ad_id BIGINT PRIMARY KEY,
            ad_url TEXT NOT NULL,
            title TEXT,
            year INTEGER,
            make TEXT,
            model TEXT,
            material TEXT,
            weight_kg INTEGER,
            width_cm INTEGER,
            depth_cm INTEGER,
            sleepers INTEGER,
            seats INTEGER,
            engine_make TEXT,
            engine_type TEXT,
            engine_effect_hp INTEGER,
            boat_max_speed_knots INTEGER,
            registration_number TEXT,
            municipality TEXT,
            county TEXT,
            postal_code TEXT,
            lat DOUBLE PRECISION,
            lng DOUBLE PRECISION,
            latest_price INTEGER,
            first_seen_at TIMESTAMPTZ,
            last_seen_at TIMESTAMPTZ,
            last_scraped_at TIMESTAMPTZ,
            last_edited_at TIMESTAMPTZ,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            source_raw JSONB
        );

        -- price_history
        CREATE TABLE IF NOT EXISTS sailboat.price_history (
            ad_id BIGINT NOT NULL REFERENCES sailboat.ads(ad_id) ON DELETE CASCADE,
            price INTEGER NOT NULL,
            changed_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (ad_id, changed_at)
        );
        """
        pg.run(sql)

    init_schema()


sailboat_db_init() 