# Finnno Sailboat Project

This project scrapes sailboat listings from [Finn.no](https://www.finn.no/),
loads them into a PostgreSQL database and enriches the data with semantic
embeddings for advanced search and analysis.

## Requirements

- **PostgreSQL** with the `pgvector` extension enabled for storing
  embeddings.
- **Apache Airflow** for running scraping, database initialization and
  semantic-processing DAGs.

Install Python dependencies with:

```bash
pip install -r requirements.txt
```

## Repository Layout

```
scraper/       # Scrapers and parser utilities for Finn.no listings
semantic/      # Chunking, embedding and scoring helpers
airflow_dags/  # Airflow DAG definitions
scripts/       # Utility scripts and tests
```

## Usage

### Run the scraper

Fetch latest listings from Finn.no:

```bash
python scraper/scrape_boats.py
```

### Initialize the database schema

Run the Airflow DAG to create the `sailboat` schema and tables:

```bash
airflow dags test sailboat_db_init 2024-01-01
```

### Semantic processing

Execute the DAG that chunks descriptions, generates embeddings and scores
aspects:

```bash
airflow dags trigger sailboat_semantic_processing
```

## Tests

Run the semantic search test script which exercises chunking, embeddings and
aspect scoring:

```bash
python scripts/test_semantic_search.py
```
