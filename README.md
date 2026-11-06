# NASA EONET ETL Pipeline

A Python ETL pipeline that pulls natural event data (wildfires, severe storms, volcanoes, sea and lake ice and more) from NASA's [EONET v3 API](https://eonet.gsfc.nasa.gov/docs/v3), flattens the nested JSON into one row per event reading, cleans and types the data with pandas, and loads it into a **PostgreSQL** database (hosted on Aiven) with a **CSV** backup.

## Table of contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Project structure](#project-structure)
4. [Requirements](#requirements)
5. [Setup](#setup)
6. [Configuration](#configuration)
7. [Usage](#usage)
8. [How it works](#how-it-works)
9. [Data model](#data-model)
10. [Verifying the data](#verifying-the-data)
11. [Error handling](#error-handling)
12. [Troubleshooting](#troubleshooting)
13. [Known limitations](#known-limitations)
14. [Roadmap](#roadmap)

## Overview

| Stage         | Function          | What happens                                                                                   |
|---------------|-------------------|------------------------------------------------------------------------------------------------|
| **Extract**   | `extraction()`    | Calls the EONET `/events` endpoint (up to 1000 events) and returns the JSON payload.           |
| **Transform** | `transformation()`| Flattens events and their geometry readings, enforces column types, parses dates to `YYYY-MM-DD`. |
| **Load (CSV)**| `load()`          | Writes the cleaned DataFrame to `output/nasa_extracted.csv`.                                   |
| **Load (DB)** | `load_postgres()` | Full load into the `nasa_events` table: truncate, then insert, in one transaction.             |
| **Orchestrate** | `main()`        | Runs the stages in order and prints a null-value summary.                                      |

## Architecture

```
                         ┌──► output/nasa_extracted.csv   (backup copy)
EONET API ──► extraction() ──► transformation() ──┤
 (JSON)         (dict)          (DataFrame)       └──► PostgreSQL (Aiven)
                                                       table: nasa_events
```

## Project structure

```
nasa-etl-pipeline/
├── extract.py               # the ETL script
├── output/
│   └── nasa_extracted.csv   # generated CSV backup
├── requirements.txt         # Python dependencies
├── .env                     # local secrets and settings (never commit)
├── .gitignore
└── README.md
```

## Requirements

- Python 3.9 or newer
- A PostgreSQL database (this project uses an Aiven-hosted instance)
- Python packages:
  - `pandas` 2.0 or newer (date parsing uses `format="mixed"`)
  - `requests`
  - `python-dotenv`
  - `sqlalchemy`
  - `psycopg2-binary`

## Setup

1. **Clone the repository**

   ```bash
   git clone <your-repo-url>
   cd nasa-etl-pipeline
   ```

2. **Create and activate a virtual environment**

   Windows (PowerShell):

   ```powershell
   python -m venv nasa-env
   .\nasa-env\Scripts\Activate.ps1
   ```

   macOS / Linux:

   ```bash
   python -m venv nasa-env
   source nasa-env/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Create the `.env` file** (see [Configuration](#configuration)).

5. **Make sure `.env` and `nasa-env/` are listed in `.gitignore`** so credentials and the virtual environment are never committed.

## Configuration

Create a `.env` file in the project root:

```dotenv
API_KEY=<your NASA API key>
DB_HOST=<your-service>.aivencloud.com
DB_PORT=<port shown in the Aiven console>
DB_NAME=defaultdb
DB_USER=avnadmin
DB_PASSWORD=<your database password>
DB_SSLMODE=require
```

| Variable      | Required | Description                                                                 |
|---------------|----------|-----------------------------------------------------------------------------|
| `API_KEY`     | Yes*     | NASA API key. EONET itself is public, but the script checks for this at startup. Get one free at [api.nasa.gov](https://api.nasa.gov/). |
| `DB_HOST`     | No       | Database host. Defaults to `localhost`.                                     |
| `DB_PORT`     | No       | Database port. Defaults to `5432`. Aiven uses its own port, so set it.      |
| `DB_NAME`     | Yes      | Database name. `defaultdb` is created automatically by Aiven.               |
| `DB_USER`     | Yes      | Database user (`avnadmin` on Aiven).                                        |
| `DB_PASSWORD` | Yes      | Database password.                                                          |
| `DB_SSLMODE`  | No       | SSL mode. Defaults to `require`, which Aiven needs.                         |

**Other settings** live in `extract.py`:

| Setting       | Default                      | Description                          |
|---------------|------------------------------|--------------------------------------|
| `API_URL`     | EONET v3 `/events`           | API endpoint                         |
| `PATH_OUTPUT` | `output/nasa_extracted.csv`  | CSV output path                      |
| `TABLE_NAME`  | `nasa_events`                | Target table                         |
| `limit`       | `1000`                       | Events requested per run (in `main`) |

> **Security:** never paste your password or API key into chats, tickets or commits. If a credential is exposed, reset it (Aiven console > your service > **Users**) and update `.env`.

## Usage

```bash
python extract.py
```

A successful run prints the event count, the transformed DataFrame shape, a null-value summary and a preview, then ends with:

```
CSV FILE SUCCESSFULLY LOADED to output\nasa_extracted.csv
POSTGRES: full load complete - <n> rows now in 'nasa_events'
```

## How it works

1. **Startup checks.** `.env` is loaded. The script exits with code 1 if `API_KEY` or any required `DB_*` setting is missing.
2. **Extract.** `extraction()` requests up to 1000 events. On a timeout, connection error, bad status or invalid JSON it prints a message and exits.
3. **Flatten.** `transformation()` loops over each event and each of its geometry readings. Every reading becomes one row, with the event's id, title, first category and first source repeated on each row. Longitude and latitude are only read for `Point` geometries.
4. **Type and clean.** Text columns use pandas' `string` dtype (so real nulls survive), numeric columns use `to_numeric`, and `event_date` is parsed from ISO timestamps to a UTC date. Duplicate readings (same event, date, longitude and latitude) are dropped.
5. **Load to CSV.** `load()` creates the `output/` folder if needed and writes the CSV.
6. **Load to Postgres (full load).** `load_postgres()` runs one transaction that creates the table if needed, **truncates** it, and **inserts** the whole fresh dataset. If anything fails, the transaction rolls back and the previous data stays intact. If the DataFrame is empty, the load is skipped so existing data is never wiped by an empty extract.

## Data model

Table: `nasa_events` (one row per event reading)

| Column            | Type                 | Description                                       |
|-------------------|----------------------|---------------------------------------------------|
| `event_id`        | VARCHAR(50), NOT NULL| EONET event ID (repeats across an event's readings) |
| `event_title`     | VARCHAR(255)         | Event name                                        |
| `category_title`  | VARCHAR(100)         | Event category (e.g. Wildfires, Severe Storms)    |
| `source`          | VARCHAR(100)         | ID of the first listed data source                |
| `magnitude_value` | DOUBLE PRECISION     | Measured magnitude, if provided                   |
| `magnitude_unit`  | VARCHAR(30)          | Unit of the magnitude (e.g. acres, kts)           |
| `event_date`      | DATE                 | Date of the reading (UTC)                         |
| `lon`             | DOUBLE PRECISION     | Longitude (Point geometries only)                 |
| `lat`             | DOUBLE PRECISION     | Latitude (Point geometries only)                  |
| `loaded_at`       | TIMESTAMPTZ          | Set automatically at load time                    |

`event_id` is not unique on its own. Use `event_id` + `event_date` + `lon` + `lat` to identify a reading.

`DOUBLE PRECISION` is used for numbers instead of strict `DECIMAL(p, s)` so that values never overflow the column. The script creates the table itself with `CREATE TABLE IF NOT EXISTS`. If you change the column types later, drop the old table first (`DROP TABLE IF EXISTS nasa_events;`) so the script recreates it.

## Verifying the data

In DBeaver (or any SQL client), connect to the database and run:

```sql
SELECT COUNT(*) FROM nasa_events;

SELECT category_title, COUNT(*) AS readings
FROM nasa_events
GROUP BY category_title
ORDER BY readings DESC;

SELECT event_title, category_title, event_date, lat, lon
FROM nasa_events
ORDER BY event_date DESC
LIMIT 10;
```

In DBeaver's navigator the table appears under `defaultdb` > `Databases` > `defaultdb` > `Schemas` > `public` > `Tables`. Select **Tables** and press **F5** to refresh.

## Error handling

| Situation                       | Message                                      | Result      |
|---------------------------------|----------------------------------------------|-------------|
| Missing `API_KEY`               | `API_KEY not found. Check your .env file`    | exit code 1 |
| Missing `DB_*` settings         | `Missing database settings in .env: [...]`   | exit code 1 |
| Request times out               | `Server took long to respond`                | exit code 1 |
| No network                      | `Please check your Internet Connection`      | exit code 1 |
| HTTP 4xx / 5xx                  | `Bad status code`                            | exit code 1 |
| Response is not valid JSON      | `Invalid JSON format`                        | exit code 1 |
| Database error                  | `Database error: ...` (transaction rolled back) | exit code 1 |
| Empty DataFrame                 | `DataFrame is empty - skipping Postgres load...` | table untouched |

## Troubleshooting

**`numeric field overflow` / `NumericValueOutOfRange`**
A column was created with a strict type such as `DECIMAL(8, 6)`. Change the column types to `DOUBLE PRECISION` in `CREATE_TABLE_SQL`, then run `DROP TABLE IF EXISTS nasa_events;` so the table is recreated. Editing the code alone does not change an existing table.

**`value too long for type character varying(...)`**
A text value is longer than its column. Widen that column and recreate the table.

**`password authentication failed`**
`DB_PASSWORD` does not match Aiven's. If you reset it, copy the new one exactly.

**`could not connect` / timeout**
Check `DB_HOST` and `DB_PORT`, and in the Aiven console check **Allowed IP addresses**.

**SSL errors**
Make sure `DB_SSLMODE=require` is set.

**`database "nasa_db" does not exist`**
Set `DB_NAME=defaultdb`, or create the database first (`CREATE DATABASE nasa_db;`).

**`ModuleNotFoundError: psycopg2`**
Activate `nasa-env` and run `pip install -r requirements.txt`.

**`ValueError` about `format="mixed"`**
Upgrade pandas: `pip install --upgrade pandas`.

**`PermissionError` writing the CSV**
`nasa_extracted.csv` is open in Excel. Close it and rerun.

**The table looks empty in DBeaver**
DBeaver does not refresh on its own. Select the table or its **Tables** folder and press **F5**.

## Known limitations

- **Full load:** every run replaces the table, so events that disappear from the API's results also disappear from the table. The API returns open events by default. Add `status=all` to the request, or switch to an incremental load, if you need history.
- **Point geometries only:** `lon` and `lat` are `NULL` for events with `Polygon` geometry.
- **First category and source only:** only the first category and first source of each event are kept.
- **Up to 1000 events per run:** raise `limit` or add paging for more.
- **`API_KEY` is required by the script** even though the EONET endpoint does not need one.
- **No automated tests or scheduling yet.**

## Roadmap

- Handle `Polygon` geometries (for example, store the centroid).
- Add `status`, `days` and category filters via command-line arguments.
- Switch to an incremental (upsert) load to keep history.
- Add logging in place of `print`.
- Add unit tests for `transformation()` with sample payloads.
- Schedule recurring runs (cron, Windows Task Scheduler or Airflow).
- Build a dashboard on top of `nasa_events`.

## Data source

Event data comes from NASA's Earth Observatory Natural Event Tracker (EONET). See the [EONET documentation](https://eonet.gsfc.nasa.gov/docs/v3) for the full API reference.