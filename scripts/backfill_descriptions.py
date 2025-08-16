#!/usr/bin/env python3
"""
Backfill script for å hente descriptions på eksisterende annonser.
Går gjennom ads-tabellen og henter description for annonser som mangler det.
"""
import sys
import os
import logging
from typing import List, Tuple
import time
import random

# Sørg for at vi kan importere fra prosjektroten
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from scraper.parse_item import fetch_and_parse_item

# Database-import (tilsvarende Airflow)
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("psycopg2 kreves. Installer med: pip install psycopg2-binary")
    sys.exit(1)

# Database connection settings
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,  # Docker PostgreSQL port
    'database': 'postgres',
    'user': 'airflow',
    'password': 'airflow123'
}

def get_db_connection():
    """Opprett database-tilkobling"""
    return psycopg2.connect(**DB_CONFIG)

def get_specific_ads_for_description_update(ad_ids: List[int]) -> List[Tuple[int, str, str]]:
    """Hent spesifikke annonser basert på ad_id liste"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            sql = """
            SELECT ad_id, ad_url, COALESCE(description, '') as current_desc
            FROM sailboat.ads 
            WHERE ad_id = ANY(%s)
            ORDER BY ad_id
            """
            cur.execute(sql, (ad_ids,))
            return cur.fetchall()

def get_all_ads_for_description_update(limit: int = None) -> List[Tuple[int, str, str]]:
    """Hent ALLE annonser for å oppdatere med FULL beskrivelse"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            sql = """
            SELECT ad_id, ad_url, COALESCE(description, '') as current_desc
            FROM sailboat.ads 
            WHERE active = TRUE
            ORDER BY ad_id
            """
            if limit:
                sql += f" LIMIT {limit}"
            
            cur.execute(sql)
            return cur.fetchall()

def update_ad_description(ad_id: int, description: str, source_json: str = None):
    """Oppdater description for en annonse"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            sql = """
            UPDATE sailboat.ads 
            SET description = %s,
                source_raw = COALESCE(%s::jsonb, source_raw)
            WHERE ad_id = %s
            """
            cur.execute(sql, (description, source_json, ad_id))
            conn.commit()

def mark_ad_inactive(ad_id: int, reason: str = None):
    """Marker en annonse som inaktiv"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            sql = """
            UPDATE sailboat.ads 
            SET active = FALSE
            WHERE ad_id = %s AND active = TRUE
            """
            cur.execute(sql, (ad_id,))
            if cur.rowcount > 0:
                logging.info(f"✅ Markerte annonse {ad_id} som inaktiv ({reason})")
                conn.commit()
                return True
            return False

def backfill_full_descriptions(limit: int = None, delay_range: tuple = (1, 3), force_update: bool = True):
    """
    Hent FULLE descriptions for ALLE annonser - oppdaterer også eksisterende korte beskrivelser.
    
    Args:
        limit: Maksimalt antall annonser å behandle (None = alle)
        delay_range: (min, max) sekunder å vente mellom requests
        force_update: Om True, oppdater alle annonser. Om False, hopp over hvis beskrivelse > 500 tegn
    """
    logging.info("Starter FULL backfill av descriptions på ALLE annonser...")
    
    ads_to_process = get_all_ads_for_description_update(limit)
    total_ads = len(ads_to_process)
    
    if total_ads == 0:
        logging.info("Ingen aktive annonser funnet. Ferdig!")
        return
    
    logging.info(f"Fant {total_ads} aktive annonser som skal få FULL description")
    
    success_count = 0
    skip_count = 0
    error_count = 0
    already_long_count = 0
    inactive_count = 0
    
    for i, (ad_id, ad_url, current_desc) in enumerate(ads_to_process, 1):
        current_len = len(current_desc) if current_desc else 0
        
        # Hvis force_update er False og beskrivelsen allerede er lang, hopp over
        if not force_update and current_len > 500:
            logging.info(f"[{i}/{total_ads}] Hopper over {ad_id} - har allerede lang beskrivelse ({current_len} tegn)")
            already_long_count += 1
            continue
            
        logging.info(f"[{i}/{total_ads}] Behandler annonse {ad_id}: {ad_url} (nåværende: {current_len} tegn)")
        
        try:
            # Hent og parse annonsen
            result = fetch_and_parse_item(ad_url)
            
            if not result:
                logging.warning(f"Kunne ikke hente/parse annonse {ad_id}")
                skip_count += 1
                continue
                
            normalized, source_pack = result
            new_description = normalized.get('description')
            
            if not new_description or len(new_description.strip()) < 10:
                logging.warning(f"Ingen ny beskrivelse funnet for annonse {ad_id}")
                skip_count += 1
                continue
                
            new_len = len(new_description.strip())
            
            # Sammenlign lengde - bare oppdater hvis den nye er betydelig lengre eller force_update=True
            if not force_update and current_len > 0 and new_len <= current_len + 50:
                logging.info(f"Hopper over {ad_id} - ny beskrivelse ({new_len}) ikke betydelig lengre enn eksisterende ({current_len})")
                skip_count += 1
                continue
            
            # Oppdater databasen
            import json
            source_json = json.dumps(source_pack, ensure_ascii=False, default=str)
            update_ad_description(ad_id, new_description.strip(), source_json)
            
            success_count += 1
            logging.info(f"✅ Oppdatert {ad_id}: {current_len} → {new_len} tegn (FULL description)")
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Sjekk for 404-feil (annonse slettet/inaktiv)
            if '404' in error_msg or 'not found' in error_msg:
                if mark_ad_inactive(ad_id, "404 Not Found"):
                    inactive_count += 1
                    logging.info(f"🚫 Annonse {ad_id} er slettet fra Finn.no, markert som inaktiv")
                else:
                    logging.warning(f"Annonse {ad_id} returnerte 404 men var allerede inaktiv")
                continue
            
            # Andre feil
            logging.error(f"Feil ved behandling av annonse {ad_id}: {e}")
            error_count += 1
            continue
        
        # Pause mellom requests for å være snill mot Finn
        if i < total_ads:  # Ikke pause etter siste
            delay = random.uniform(*delay_range)
            time.sleep(delay)
    
    logging.info(f"""
    FULL description backfill fullført:
    - Behandlet: {total_ads} annonser
    - Suksess: {success_count}
    - Hoppet over: {skip_count}
    - Allerede lange: {already_long_count}
    - Inaktive: {inactive_count}
    - Feil: {error_count}
    """)

def backfill_specific_ads(ads_to_process: List[Tuple[int, str, str]], delay_range: tuple = (1, 3)):
    """
    Behandle spesifikke annonser - fokuserer på å sjekke 404-status og markere inaktive
    """
    total_ads = len(ads_to_process)
    
    if total_ads == 0:
        logging.info("Ingen annonser å behandle. Ferdig!")
        return
    
    logging.info(f"Behandler {total_ads} spesifikke annonser...")
    
    success_count = 0
    skip_count = 0
    inactive_count = 0
    
    for i, (ad_id, ad_url, current_desc) in enumerate(ads_to_process, 1):
        current_len = len(current_desc) if current_desc else 0
        logging.info(f"[{i}/{total_ads}] Sjekker annonse {ad_id}: {ad_url} (nåværende: {current_len} tegn)")
        
        try:
            # Hent og parse annonsen
            result = fetch_and_parse_item(ad_url)
            
            if not result:
                logging.warning(f"Kunne ikke hente/parse annonse {ad_id}")
                skip_count += 1
                continue
                
            normalized, source_pack = result
            new_description = normalized.get('description')
            
            if new_description and len(new_description.strip()) > 10:
                new_len = len(new_description.strip())
                
                # Oppdater databasen
                import json
                source_json = json.dumps(source_pack, ensure_ascii=False, default=str)
                update_ad_description(ad_id, new_description.strip(), source_json)
                
                success_count += 1
                logging.info(f"✅ Oppdatert {ad_id}: {current_len} → {new_len} tegn")
            else:
                logging.warning(f"Ingen beskrivelse funnet for annonse {ad_id}")
                skip_count += 1
                
        except Exception as e:
            error_msg = str(e).lower()
            
            # Sjekk for 404-feil (annonse slettet/inaktiv)
            if '404' in error_msg or 'not found' in error_msg:
                if mark_ad_inactive(ad_id, "404 Not Found"):
                    inactive_count += 1
                    logging.info(f"🚫 Annonse {ad_id} er slettet fra Finn.no, markert som inaktiv")
                else:
                    logging.warning(f"Annonse {ad_id} returnerte 404 men var allerede inaktiv")
                continue
            
            # Andre feil
            logging.error(f"Feil ved behandling av annonse {ad_id}: {e}")
            skip_count += 1
            continue
        
        # Pause mellom requests
        if i < total_ads:
            delay = random.uniform(*delay_range)
            time.sleep(delay)
    
    logging.info(f"""
    Spesifikke annonser behandlet:
    - Behandlet: {total_ads} annonser
    - Suksess: {success_count}
    - Hoppet over: {skip_count}
    - Inaktive: {inactive_count}
    """)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill FULL descriptions for ALLE annonser")
    parser.add_argument('--limit', type=int, help="Maksimalt antall annonser å behandle")
    parser.add_argument('--min-delay', type=float, default=1.0, help="Minimum pause mellom requests (sekunder)")
    parser.add_argument('--max-delay', type=float, default=3.0, help="Maksimum pause mellom requests (sekunder)")
    parser.add_argument('--verbose', '-v', action='store_true', help="Verbose logging")
    parser.add_argument('--force-all', action='store_true', help="Oppdater ALLE annonser, selv de med lange beskrivelser")
    parser.add_argument('--ad-ids', type=str, help="Kommaseparerte ad_ids å behandle spesifikt")
    
    args = parser.parse_args()
    
    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('backfill_full_descriptions.log')
        ]
    )
    
    try:
        if args.ad_ids:
            # Parse specific ad_ids
            ad_ids = [int(x.strip()) for x in args.ad_ids.split(',')]
            logging.info(f"Behandler spesifikke annonser: {ad_ids}")
            ads_to_process = get_specific_ads_for_description_update(ad_ids)
        else:
            ads_to_process = get_all_ads_for_description_update(args.limit)
        
        # Custom backfill logic for specific ads
        if args.ad_ids:
            backfill_specific_ads(ads_to_process, (args.min_delay, args.max_delay))
        else:
            backfill_full_descriptions(
                limit=args.limit,
                delay_range=(args.min_delay, args.max_delay),
                force_update=args.force_all
            )
    except KeyboardInterrupt:
        logging.info("Avbrutt av bruker")
    except Exception as e:
        logging.error(f"Uventet feil: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 