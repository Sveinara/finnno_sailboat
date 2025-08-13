from datetime import datetime
from airflow.decorators import dag

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
    return

sailboat_dag()