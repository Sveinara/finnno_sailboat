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
            equipment TEXT,
            title TEXT,
            description TEXT,
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
        
        -- Sikre at description-kolonnen finnes og er TEXT
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='sailboat' AND table_name='staging_item_details'
                AND column_name='description'
            ) THEN
                ALTER TABLE sailboat.staging_item_details ADD COLUMN description TEXT;
            ELSIF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='sailboat' AND table_name='staging_item_details'
                AND column_name='description'
                AND data_type NOT IN ('text','character varying')
            ) THEN
                ALTER TABLE sailboat.staging_item_details
                    ALTER COLUMN description TYPE TEXT USING description::text;
            END IF;
        END $$;

        -- Sikre at equipment-kolonnen finnes og er TEXT
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='sailboat' AND table_name='staging_item_details'
                AND column_name='equipment'
            ) THEN
                ALTER TABLE sailboat.staging_item_details ADD COLUMN equipment TEXT;
            ELSIF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='sailboat' AND table_name='staging_item_details'
                AND column_name='equipment'
                AND data_type NOT IN ('text','character varying')
            ) THEN
                ALTER TABLE sailboat.staging_item_details
                    ALTER COLUMN equipment TYPE TEXT USING equipment::text;
            END IF;
        END $$;

        -- ads (master)
        CREATE TABLE IF NOT EXISTS sailboat.ads (
            ad_id BIGINT PRIMARY KEY,
            ad_url TEXT NOT NULL,
            title TEXT,
            description TEXT,
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
            equipment TEXT,
            latest_price INTEGER,
            first_seen_at TIMESTAMPTZ,
            last_seen_at TIMESTAMPTZ,
            last_scraped_at TIMESTAMPTZ,
            last_edited_at TIMESTAMPTZ,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            has_embeddings BOOLEAN DEFAULT FALSE,
            semantic_processed_at TIMESTAMPTZ,
            source_raw JSONB
        );

        -- Sikre at description-kolonnen finnes og er TEXT i ads
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='sailboat' AND table_name='ads'
                AND column_name='description'
            ) THEN
                ALTER TABLE sailboat.ads ADD COLUMN description TEXT;
            ELSIF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='sailboat' AND table_name='ads'
                AND column_name='description'
                AND data_type NOT IN ('text','character varying')
            ) THEN
                ALTER TABLE sailboat.ads
                    ALTER COLUMN description TYPE TEXT USING description::text;
            END IF;
        END $$;

        -- Sikre at equipment-kolonnen finnes og er TEXT i ads
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='sailboat' AND table_name='ads'
                AND column_name='equipment'
            ) THEN
                ALTER TABLE sailboat.ads ADD COLUMN equipment TEXT;
            ELSIF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='sailboat' AND table_name='ads'
                AND column_name='equipment'
                AND data_type NOT IN ('text','character varying')
            ) THEN
                ALTER TABLE sailboat.ads
                    ALTER COLUMN equipment TYPE TEXT USING equipment::text;
            END IF;
        END $$;

        -- Legg til has_embeddings kolonne i ads hvis den ikke finnes
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='sailboat' AND table_name='ads'
                AND column_name='has_embeddings'
            ) THEN
                ALTER TABLE sailboat.ads ADD COLUMN has_embeddings BOOLEAN DEFAULT FALSE;
            END IF;
        END $$;

        -- Legg til semantic_processed_at kolonne i ads hvis den ikke finnes
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='sailboat' AND table_name='ads'
                AND column_name='semantic_processed_at'
            ) THEN
                ALTER TABLE sailboat.ads ADD COLUMN semantic_processed_at TIMESTAMPTZ;
            END IF;
        END $$;

        -- price_history
        CREATE TABLE IF NOT EXISTS sailboat.price_history (
            ad_id BIGINT NOT NULL REFERENCES sailboat.ads(ad_id) ON DELETE CASCADE,
            price INTEGER NOT NULL,
            changed_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (ad_id, changed_at)
        );

        -- ========== PGVECTOR SETUP ==========
        -- Enable pgvector extension
        CREATE EXTENSION IF NOT EXISTS vector;

        -- Description and equipment chunks with embeddings
        CREATE TABLE IF NOT EXISTS sailboat.text_chunks (
            chunk_id SERIAL PRIMARY KEY,
            ad_id BIGINT NOT NULL REFERENCES sailboat.ads(ad_id) ON DELETE CASCADE,
            chunk_source TEXT NOT NULL, -- 'description' eller 'equipment'
            chunk_text TEXT NOT NULL,
            chunk_order INTEGER NOT NULL, -- Order within the source text
            chunk_length INTEGER NOT NULL,
            overlap_words INTEGER DEFAULT 0,
            embedding vector(384), -- Sentence-Transformers all-MiniLM-L6-v2 dimensjon
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(ad_id, chunk_source, chunk_order)
        );

        -- Index for fast similarity search
        CREATE INDEX IF NOT EXISTS idx_text_chunks_embedding
        ON sailboat.text_chunks USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);

        -- Index for ad lookup
        CREATE INDEX IF NOT EXISTS idx_text_chunks_ad_id
        ON sailboat.text_chunks (ad_id);

        -- Semantic scoring for different aspects
        CREATE TABLE IF NOT EXISTS sailboat.semantic_scores (
            score_id SERIAL PRIMARY KEY,
            ad_id BIGINT NOT NULL REFERENCES sailboat.ads(ad_id) ON DELETE CASCADE,
            aspect TEXT NOT NULL, -- 'sails', 'motor', 'condition', 'equipment'
            raw_score DOUBLE PRECISION NOT NULL, -- 0.0-1.0 semantic confidence
            normalized_score DOUBLE PRECISION, -- Normalized against entire dataset
            supporting_chunks INTEGER[], -- Array of chunk_ids that contributed
            score_method TEXT NOT NULL, -- 'embedding_similarity', 'llm_classification'
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(ad_id, aspect)
        );

        -- Index for aspect scoring lookup
        CREATE INDEX IF NOT EXISTS idx_semantic_scores_aspect 
        ON sailboat.semantic_scores (aspect, normalized_score DESC);

        -- Search queries and results cache
        CREATE TABLE IF NOT EXISTS sailboat.search_cache (
            query_hash TEXT PRIMARY KEY,
            query_text TEXT NOT NULL,
            result_ad_ids BIGINT[],
            similarity_scores DOUBLE PRECISION[],
            search_method TEXT NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '1 hour',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        """
        pg.run(sql)

    init_schema()


sailboat_db_init() 
