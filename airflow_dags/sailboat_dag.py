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
	dag_id='sailboat_dag_legacy_combined',
	start_date=datetime(2023, 10, 26),
	schedule=None,  # deaktivert – se nye dag'er
	catchup=False,
	tags=['deprecated', 'sailboat'],
	doc_md="""
	Denne kombinert-DAG-en er deaktivert.
	Bruk:
	- sailboat_search_crawl (crawl til staging)
	- sailboat_item_etl (item-ETL og master)
	"""
)
def sailboat_dag():
	pass

sailboat_dag()