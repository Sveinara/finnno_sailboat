# Finn.no Sailboat Analysis Platform

This project provides a complete, containerized data platform for scraping sailboat listings from Finn.no, storing them, transforming them, and preparing them for analysis. The entire platform runs on Docker and is orchestrated with Apache Airflow.

## Architecture Overview

The platform is built around a modern ELT (Extract, Load, Transform) architecture using a set of powerful open-source tools:

-   **Docker & Docker Compose:** The entire platform is defined in `docker-compose.yml`, allowing you to spin up all services with a single command.
-   **Apache Airflow:** Acts as the central orchestrator. It manages the data pipelines, from scheduling the scraper to triggering data transformations.
-   **PostgreSQL (with pgvector):** Serves as the data warehouse. It stores both raw data from the scraper and the final, transformed data models.
-   **Minio:** Provides S3-compatible object storage. It is used for two key purposes:
    1.  Archiving all raw, scraped JSON data for backup and historical purposes.
    2.  Storing regular, automated backups of the entire PostgreSQL database.
-   **dbt (Data Build Tool):** Handles the "Transform" step. It transforms the raw data in Postgres into clean, reliable, and analysis-ready data models.
-   **GitHub Actions:** A CI/CD pipeline is pre-configured to automatically build and test the platform on every push to the `main` branch.

## Getting Started (Local Development)

### Prerequisites

-   [Docker](https://www.docker.com/get-started)
-   [Docker Compose](https://docs.docker.com/compose/install/) (usually included with Docker Desktop)

### 1. Set up Environment File

The project uses a `project.env` file for local configuration. Create this file by copying the example:

```bash
cp project.env.example project.env
```

_Note: The default values in `project.env` are suitable for local development. This file is ignored by Git._

### 2. Build and Run the Platform

Start all services using Docker Compose:

```bash
docker-compose up --build
```

This command will:
-   Build the custom Airflow image (which includes dbt).
-   Start containers for Postgres, Minio, and Airflow (webserver, scheduler, and an init-job).
-   Initialize the Airflow database and create a default user.

### 3. Accessing Services

Once the containers are running, you can access the main services:

-   **Airflow UI:** [http://localhost:8080](http://localhost:8080)
    -   **Login:** `admin` / `admin`
-   **Minio Console:** [http://localhost:9001](http://localhost:9001)
    -   **Login:** Use the `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` from your `project.env` file (default is `minio` / `minio123`).

## Data Flow

The data flows through the platform in three main stages:

1.  **Extract & Load (Orchestrated by Airflow):**
    -   The `sailboat_search_crawl` DAG runs on a schedule.
    -   It scrapes Finn.no for new sailboat listings.
    -   The raw JSON data is immediately **archived** to the `raw-boat-data` bucket in Minio.
    -   The same raw data is **loaded** into the `sailboat.staging_ads` table in Postgres.

2.  **Transform (Orchestrated by Airflow & dbt):**
    -   The successful completion of the crawl DAG triggers the `dbt_run_sailboat_analysis` DAG.
    -   This DAG executes `dbt run`, which transforms the raw data from `staging_ads` into cleaned models within the `sailboat_dbt` schema in Postgres.

3.  **Backup (Orchestrated by Airflow):**
    -   The `database_backup_to_minio` DAG runs daily.
    -   It creates a full, compressed backup of the Postgres database.
    -   The backup file is stored in the `postgres-backups` bucket in Minio, ensuring data safety.

## CI/CD with GitHub Actions

This repository includes a pre-configured GitHub Actions workflow in `.github/workflows/main.yml`. This workflow automatically builds and tests the entire stack on every push or pull request to the `main` branch.

### Required Secrets

To make the workflow run, you must configure the following secrets in your GitHub repository's settings (`Settings > Secrets and variables > Actions`):

-   `POSTGRES_USER`: The username for the PostgreSQL database.
-   `POSTGRES_PASSWORD`: The password for the PostgreSQL database.
-   `POSTGRES_DB`: The name of the PostgreSQL database.
-   `MINIO_ROOT_USER`: The root user for Minio.
-   `MINIO_ROOT_PASSWORD`: The root password for Minio.

These secrets are securely passed to the Docker containers during the CI/CD run.