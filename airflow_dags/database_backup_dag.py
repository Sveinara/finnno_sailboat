import os
from datetime import datetime, timedelta
from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator
import logging
from minio import Minio
from minio.error import S3Error

# Minio Connection Details from Environment Variables
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minio")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minio123")
MINIO_BACKUP_BUCKET_NAME = "postgres-backups"

# PostgreSQL connection details from environment (Airflow's default env vars)
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "postgres")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

BACKUP_FILE_PATH = "/tmp/postgres_backup.sql.gz"

@dag(
    dag_id='database_backup_to_minio',
    start_date=datetime(2024, 1, 1),
    schedule='@daily',  # Run once a day
    catchup=False,
    tags=['maintenance', 'backup', 'postgres', 'minio'],
    doc_md="""
    ### Database Backup DAG
    This DAG performs a full backup of the PostgreSQL database,
    compresses it, and uploads it to a Minio bucket.
    """
)
def database_backup_dag():

    dump_database = BashOperator(
        task_id='dump_database',
        bash_command=f"""
        export PGPASSWORD='{POSTGRES_PASSWORD}'
        pg_dump -h {POSTGRES_HOST} -U {POSTGRES_USER} -d {POSTGRES_DB} | gzip > {BACKUP_FILE_PATH}
        """,
        doc_md="Uses `pg_dump` to create a gzipped SQL dump of the database."
    )

    @task(task_id="upload_backup_to_minio")
    def upload_backup_to_minio(**kwargs):
        logical_date = kwargs['logical_date']

        try:
            client = Minio(
                MINIO_ENDPOINT,
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY,
                secure=False
            )

            # Ensure the backup bucket exists
            found = client.bucket_exists(MINIO_BACKUP_BUCKET_NAME)
            if not found:
                client.make_bucket(MINIO_BACKUP_BUCKET_NAME)
                logging.info(f"Created bucket {MINIO_BACKUP_BUCKET_NAME}")

            # Define a unique object name for the backup
            object_name = f"backup-{logical_date.strftime('%Y-%m-%dT%H-%M-%S')}.sql.gz"

            # Upload the file
            client.fput_object(
                MINIO_BACKUP_BUCKET_NAME,
                object_name,
                BACKUP_FILE_PATH,
            )
            logging.info(f"Successfully uploaded {object_name} to Minio bucket {MINIO_BACKUP_BUCKET_NAME}.")

        except S3Error as exc:
            logging.error("Error occurred while uploading to Minio.", exc_info=True)
            raise

    cleanup_local_backup = BashOperator(
        task_id='cleanup_local_backup',
        bash_command=f"rm -f {BACKUP_FILE_PATH}",
        trigger_rule='all_done', # Run whether the upload succeeds or fails
        doc_md="Removes the temporary local backup file."
    )

    # Define task dependencies
    dump_database >> upload_backup_to_minio() >> cleanup_local_backup

database_backup_dag()