import sys
import os
from datetime import datetime, timedelta
from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
import logging
import json

# Sørg for at prosjektroten er på sys.path ved Airflow-import
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

@dag(
    dag_id='sailboat_semantic_processing',
    start_date=datetime(2023, 10, 26),
    schedule='0 2 * * *',  # Kjør hver natt kl 02:00
    catchup=False,
    tags=['semantic', 'embeddings', 'sailboat', 'ml'],
    doc_md="""
    ### Sailboat Semantic Processing
    - Prosesser nye annonser for embeddings og semantic scoring
    - Chunk beskrivelser og generer embeddings
    - Score aspekter (seil, motor, tilstand, etc.)
    - Normaliser scores mot hele datasettet
    """
)
def sailboat_semantic_processing():

    @task(task_id="find_unprocessed_ads")
    def find_unprocessed_ads():
        """Finn annonser som trenger semantic processing."""
        pg = PostgresHook(postgres_conn_id='postgres_finn_db')
        
        # Finn annonser med beskrivelse men uten embeddings
        sql = """
        SELECT ad_id, description, equipment
        FROM sailboat.ads
        WHERE active = TRUE
          AND description IS NOT NULL
          AND LENGTH(TRIM(description)) > 50
          AND (has_embeddings = FALSE OR has_embeddings IS NULL)
        ORDER BY ad_id
        LIMIT 100;  -- Prosesser max 100 om gangen
        """

        rows = pg.get_records(sql)
        ads_to_process = [
            {
                'ad_id': row[0],
                'description': row[1],
                'equipment': row[2] or [],
            }
            for row in rows
        ]
        
        logging.info(f"Fant {len(ads_to_process)} annonser som trenger semantic processing")
        return ads_to_process

    @task(task_id="process_embeddings")
    def process_embeddings(ads_to_process) -> int:
        """Generer chunks og embeddings for annonser."""
        if not ads_to_process:
            logging.info("Ingen annonser å prosessere")
            return 0

        try:
            # Import semantic modules
            from semantic.chunker import BoatDescriptionChunker
            from semantic.embedder import create_embedding_service
            
            # Initialize services
            chunker = BoatDescriptionChunker()
            embedding_service = create_embedding_service(method="openai")
            
            logging.info(f"Embedding service ready: {embedding_service.get_info()}")
            
            pg = PostgresHook(postgres_conn_id='postgres_finn_db')
            processed_count = 0
            
            for ad in ads_to_process:
                ad_id = ad['ad_id']
                description = ad['description']
                equipment = ad.get('equipment') or []

                combined = (
                    description
                    if not equipment
                    else description + "\nUtstyr: " + ", ".join(equipment)
                )

                try:
                    # 1. Chunk beskrivelse og utstyr
                    chunks = chunker.chunk_description(combined)
                    if not chunks:
                        logging.warning(f"Ingen chunks generert for annonse {ad_id}")
                        continue

                    logging.info(f"Prosesserer annonse {ad_id}: {len(chunks)} chunks")
                    
                    # 2. Generer embeddings for alle chunks
                    chunk_texts = [chunk.text for chunk in chunks]
                    embeddings = embedding_service.embed_batch(chunk_texts)
                    
                    if len(embeddings) != len(chunks):
                        logging.error(f"Embedding count mismatch for ad {ad_id}: {len(embeddings)} vs {len(chunks)}")
                        continue
                    
                    # 3. Lagre chunks og embeddings i database
                    for chunk, embedding in zip(chunks, embeddings):
                        # Konverter embedding til PostgreSQL array format
                        vector_str = '[' + ','.join(map(str, embedding.vector)) + ']'
                        
                        sql_insert_chunk = """
                        INSERT INTO sailboat.text_chunks (
                            ad_id, chunk_source, chunk_text, chunk_order, chunk_length,
                            overlap_words, embedding, created_at, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s::vector, NOW(), NOW()
                        ) ON CONFLICT (ad_id, chunk_source, chunk_order) DO UPDATE SET
                            chunk_text = EXCLUDED.chunk_text,
                            chunk_length = EXCLUDED.chunk_length,
                            overlap_words = EXCLUDED.overlap_words,
                            embedding = EXCLUDED.embedding,
                            updated_at = NOW();
                        """
                        
                        pg.run(sql_insert_chunk, parameters=(
                            ad_id,
                            'description',
                            chunk.text,
                            chunk.order,
                            chunk.length,
                            chunk.overlap_words,
                            vector_str
                        ))
                    
                    # 4. Marker annonse som prosessert
                    pg.run("""
                        UPDATE sailboat.ads 
                        SET has_embeddings = TRUE, semantic_processed_at = NOW()
                        WHERE ad_id = %s
                    """, parameters=(ad_id,))
                    
                    processed_count += 1
                    logging.info(f"✅ Prosessert annonse {ad_id} med {len(chunks)} chunks")
                    
                except Exception as e:
                    logging.error(f"Feil ved prosessering av annonse {ad_id}: {e}")
                    continue
            
            logging.info(f"Embedding processing fullført: {processed_count}/{len(ads_to_process)} annonser")
            return processed_count
            
        except ImportError as e:
            logging.error(f"Semantic modules ikke tilgjengelig: {e}")
            return 0
        except Exception as e:
            logging.error(f"Embedding processing feilet: {e}")
            return 0

    @task(task_id="process_aspect_scoring")
    def process_aspect_scoring(processed_count: int) -> int:
        """Score aspekter (seil, motor, tilstand) for nye annonser."""
        if processed_count == 0:
            logging.info("Ingen nye annonser å score")
            return 0

        try:
            from semantic.scorer import SemanticScorer, AspectType
            from semantic.embedder import create_embedding_service
            
            # Initialize scorer
            embedding_service = create_embedding_service(method="openai")
            scorer = SemanticScorer(embedding_service)
            
            pg = PostgresHook(postgres_conn_id='postgres_finn_db')
            
            # Finn annonser som har embeddings men mangler aspect scores
            sql_find_unscored = """
            SELECT DISTINCT a.ad_id, a.description
            FROM sailboat.ads a
            LEFT JOIN sailboat.semantic_scores s ON s.ad_id = a.ad_id
            WHERE a.active = TRUE 
              AND a.has_embeddings = TRUE
              AND a.description IS NOT NULL
              AND s.ad_id IS NULL
            LIMIT 50;  -- Prosesser max 50 om gangen
            """
            
            rows = pg.get_records(sql_find_unscored)
            scored_count = 0
            
            for ad_id, description in rows:
                try:
                    # Score alle aspekter
                    scores = scorer.score_description(description)
                    
                    # Lagre scores i database
                    for aspect, score in scores.items():
                        # Konverter supporting chunks til array
                        supporting_chunks = []
                        if score.supporting_chunks:
                            # Finn chunk_ids for supporting chunks
                            chunk_ids_sql = """
                            SELECT chunk_id FROM sailboat.text_chunks
                            WHERE ad_id = %s AND chunk_source = 'description' AND chunk_text = ANY(%s)
                            """
                            chunk_rows = pg.get_records(chunk_ids_sql, (ad_id, score.supporting_chunks))
                            supporting_chunks = [row[0] for row in chunk_rows]
                        
                        sql_insert_score = """
                        INSERT INTO sailboat.semantic_scores (
                            ad_id, aspect, raw_score, supporting_chunks, score_method
                        ) VALUES (
                            %s, %s, %s, %s, %s
                        ) ON CONFLICT (ad_id, aspect) DO UPDATE SET
                            raw_score = EXCLUDED.raw_score,
                            supporting_chunks = EXCLUDED.supporting_chunks,
                            score_method = EXCLUDED.score_method,
                            created_at = NOW();
                        """
                        
                        pg.run(sql_insert_score, parameters=(
                            ad_id,
                            aspect.value,
                            score.raw_score,
                            supporting_chunks,
                            score.method
                        ))
                    
                    scored_count += 1
                    logging.info(f"✅ Scoret annonse {ad_id} på {len(scores)} aspekter")
                    
                except Exception as e:
                    logging.error(f"Feil ved scoring av annonse {ad_id}: {e}")
                    continue
            
            logging.info(f"Aspect scoring fullført: {scored_count} annonser")
            return scored_count
            
        except ImportError as e:
            logging.error(f"Semantic scoring modules ikke tilgjengelig: {e}")
            return 0
        except Exception as e:
            logging.error(f"Aspect scoring feilet: {e}")
            return 0

    @task(task_id="normalize_scores")
    def normalize_scores(scored_count: int) -> bool:
        """Normaliser alle aspect scores mot hele datasettet."""
        try:
            pg = PostgresHook(postgres_conn_id='postgres_finn_db')
            
            # Få alle aspekter
            aspects = ['sails', 'motor', 'condition', 'equipment', 'interior', 'exterior']
            
            for aspect in aspects:
                # Hent alle scores for dette aspektet
                sql_get_scores = """
                SELECT ad_id, raw_score 
                FROM sailboat.semantic_scores 
                WHERE aspect = %s
                ORDER BY raw_score
                """
                
                rows = pg.get_records(sql_get_scores, (aspect,))
                if len(rows) < 2:
                    logging.info(f"For få scores for {aspect}, hopper over normalisering")
                    continue
                
                # Beregn percentiler for hver score
                total_ads = len(rows)
                
                sql_update_normalized = """
                UPDATE sailboat.semantic_scores 
                SET normalized_score = %s
                WHERE ad_id = %s AND aspect = %s
                """
                
                for i, (ad_id, raw_score) in enumerate(rows):
                    # Percentile rank (0.0 til 1.0)
                    percentile = i / (total_ads - 1) if total_ads > 1 else 0.5
                    
                    pg.run(sql_update_normalized, parameters=(percentile, ad_id, aspect))
                
                logging.info(f"✅ Normaliserte {total_ads} scores for {aspect}")
            
            logging.info("Score normalisering fullført")
            return True
            
        except Exception as e:
            logging.error(f"Score normalisering feilet: {e}")
            return False

    @task(task_id="cleanup_old_cache")
    def cleanup_old_cache() -> int:
        """Rydd opp i gammel search cache."""
        try:
            pg = PostgresHook(postgres_conn_id='postgres_finn_db')
            
            # Slett cache entries som er utløpt
            sql_cleanup = """
            DELETE FROM sailboat.search_cache 
            WHERE expires_at < NOW() - INTERVAL '1 day'
            """
            
            result = pg.run(sql_cleanup, handler=lambda cursor: cursor.rowcount)
            deleted_count = result if isinstance(result, int) else 0
            
            logging.info(f"Slettet {deleted_count} gamle cache entries")
            return deleted_count
            
        except Exception as e:
            logging.error(f"Cache cleanup feilet: {e}")
            return 0

    # Task dependencies
    unprocessed_ads = find_unprocessed_ads()
    processed_embeddings = process_embeddings(unprocessed_ads)
    scored_aspects = process_aspect_scoring(processed_embeddings)
    normalized = normalize_scores(scored_aspects)
    cleaned_cache = cleanup_old_cache()

    # Sequential flow for data processing, parallel cleanup
    unprocessed_ads >> processed_embeddings >> scored_aspects >> normalized
    cleaned_cache  # Independent cleanup task


sailboat_semantic_processing() 