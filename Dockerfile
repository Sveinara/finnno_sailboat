# Use a specific version of the official Airflow image
FROM apache/airflow:2.8.1

# Switch to root to install system dependencies if needed, then back to airflow
USER root
# Example of installing system dependencies:
# RUN apt-get update && apt-get install -y --no-install-recommends \
#         tini \
#     && apt-get clean && rm -rf /var/lib/apt/lists/*

# Switch back to the airflow user
USER airflow

# Copy the requirements file
COPY requirements.txt /

# Install Python dependencies from requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# Install the minio client library
RUN pip install --no-cache-dir minio

# Install dbt and the postgres adapter
RUN pip install --no-cache-dir dbt-core dbt-postgres