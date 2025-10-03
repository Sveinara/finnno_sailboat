from __future__ import annotations

import os
from datetime import datetime

from airflow.decorators import dag
from airflow.operators.bash import BashOperator
from airflow.datasets import Dataset

# Define the dataset that this DAG consumes.
# This should match the `outlets` of the upstream DAG.
STAGING_DATASET = Dataset("db://sailboat/staging_ads")

# Define paths to the dbt project and profiles directory within the Airflow container
DBT_PROJECT_DIR = "/opt/airflow/dbt_project"
DBT_PROFILES_DIR = "/opt/airflow/dbt_profiles"


@dag(
    dag_id="dbt_run_sailboat_analysis",
    start_date=datetime(2023, 1, 1),
    schedule=[STAGING_DATASET],  # Triggered by the dataset produced by the crawl DAG
    catchup=False,
    doc_md="""
    ### dbt Transformation DAG
    This DAG runs the dbt models to transform the raw sailboat data into cleaned, analysis-ready tables.
    It is triggered automatically after the `sailboat_search_crawl` DAG successfully loads new data.
    """,
    tags=["dbt", "transform"],
)
def dbt_run_dag():
    BashOperator(
        task_id="run_dbt_models",
        bash_command=(
            f"dbt run --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROFILES_DIR}"
        ),
    )

dbt_run_dag()