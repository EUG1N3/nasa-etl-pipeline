# NASA EONET ETL Pipeline

A Python ETL pipeline that pulls natural event data (wildfires, storms, volcanoes, sea and lake ice, etc.) from NASA's [EONET v3 API](https://eonet.gsfc.nasa.gov/docs/v3), flattens the nested JSON into one row per event reading, cleans and types the columns, and saves the result as a CSV.

## Table of contents

1. [Overview](#overview)
2. [Project structure](#project-structure)
3. [Requirements](#requirements)
4. [Setup](#setup)
5. [Usage](#usage)
6. [How it works](#how-it-works)
7. [Function reference](#function-reference)
8. [Output schema](#output-schema)
9. [Configuration](#configuration)
10. [Error handling](#error-handling)
11. [Troubleshooting](#troubleshooting)
12. [Known limitations](#known-limitations)
13. [Roadmap](#roadmap)

## Overview

| Stage         | Function         | What happens                                                                 |
|---------------|------------------|------------------------------------------------------------------------------|
| **Extract**   | `extraction()`   | Sends a GET request to the EONET `/events` endpoint and returns the JSON.    |
| **Transform** | `transformation()` | Flattens events and their geometry readings, enforces types, parses dates. |
| **Load**      | `load()`         | Writes the cleaned DataFrame to `output/nasa_extracted.csv`.                 |
| **Orchestrate** | `main()`       | Runs the stages in order and prints a null-value summary.                    |

## Project structure

```
nasa-etl-pipeline/
├── extract.py               # ETL script: extraction, transformation, load, main
├── output/
│   └── nasa_extracted.csv   # generated output
├── requirements.txt         # Python dependencies
├── .env                     # local environment variables (not committed)
├── .gitignore
└── README.md
```

## Requirements

- Python 3.9 or newer
- `pandas` 2.0 or newer (the date parsing uses `format="mixed"`, which was added in pandas 2.0)
- `requests`
- `python-dotenv`

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

4. **Create a `.env` file** in the project root:

   ```
   API_KEY=your_api_key_here
   ```

   > The EONET endpoint is public and does not need a key, but `extract.py` checks for `API_KEY` at startup and exits if it is missing. A free key is available at [api.nasa.gov](https://api.nasa.gov/).

Make sure `.env` and `nasa-env/` are listed in `.gitignore` so secrets and the virtual environment are never committed.

## Usage

```bash
python extract.py
```

A successful run prints:

- the top-level keys of the API response,
- the full JSON response (large at 1000 events, see [Known limitations](#known-limitations)),
- the expected columns,
- a per-column null count,
- the transformed DataFrame,
- a confirmation that the CSV was written to `output/nasa_extracted.csv`.

## How it works

```
EONET API ──► extraction() ──► transformation() ──► load() ──► output/nasa_extracted.csv
  (JSON)        (dict)           (DataFrame)          (CSV)
```

1. **Startup.** `.env` is loaded and `API_KEY` is read. The script exits with code 1 if the key is missing.
2. **Extract.** `main()` calls `extraction()` with `limit=1000`. The function returns the parsed JSON, or prints an error and exits on failure.
3. **Flatten.** `transformation()` loops over `payload["events"]` and then over each event's `geometry` list. Every geometry entry (a "reading") becomes one row, with event-level fields (`id`, `title`, first category, first source) repeated on each row.
4. **Validate.** The function checks that all expected columns exist and exits if any are missing.
5. **Type.** Text columns are cast to `str`, numeric columns to `float`, and `event_date` is parsed to a UTC date.
6. **Load.** `load()` creates the `output/` folder if needed and writes the CSV without the index.

## Function reference

### `extraction(url=API_URL, params=params, timeout=10.0) -> dict`

Calls the EONET API and returns the parsed JSON payload. Calls `sys.exit(1)` after printing a message on timeout, connection error, bad HTTP status, or invalid JSON.

### `transformation(payload: dict) -> pd.DataFrame`

Turns the payload into a typed DataFrame with the columns listed in [Output schema](#output-schema). Exits if an expected column is missing.

### `load(df, path=PATH_OUTPUT) -> Path`

Creates the parent folder of `path` if it does not exist, writes the DataFrame to CSV, and returns the path.

### `main()`

Runs the full pipeline and prints diagnostics.

## Output schema

| Column            | Type   | Description                                      |
|-------------------|--------|--------------------------------------------------|
| `event_id`        | string | Unique EONET event ID                            |
| `event_title`     | string | Event name                                       |
| `category_title`  | string | Event category (e.g. Wildfires, Severe Storms)   |
| `source`          | string | ID of the first listed data source               |
| `magnitude_value` | float  | Measured magnitude, if provided                  |
| `magnitude_unit`  | string | Unit of the magnitude (e.g. acres, kts)          |
| `event_date`      | date   | Date of the reading, `YYYY-MM-DD` (UTC)          |
| `lon`             | float  | Longitude of the reading                         |
| `lat`             | float  | Latitude of the reading                          |

**Granularity:** one row per reading. An event with several geometry entries appears on several rows, so `event_id` is not unique on its own. Use `event_id` + `event_date` (+ `lon`, `lat`) as the row key.

## Configuration

| Setting        | Location                | Default                       |
|----------------|-------------------------|-------------------------------|
| `API_URL`      | `extract.py`            | EONET v3 `/events` endpoint   |
| `PATH_OUTPUT`  | `extract.py`            | `output/nasa_extracted.csv`   |
| `limit`        | `main()` in `extract.py`| `1000` events                 |
| `timeout`      | `extraction()`          | `10.0` seconds                |
| `API_KEY`      | `.env`                  | none (required by the script) |

EONET also supports query parameters such as `status` (`open`, `closed`, `all`), `days`, `category`, `start` and `end`. Add them to the `params` dict passed in `main()`. By default the API returns open events only.

## Error handling

| Situation                  | Message printed                  | Result       |
|----------------------------|----------------------------------|--------------|
| Request times out          | `Server took long to respond`    | exit code 1  |
| No network                 | `Please check your Internet Connection` | exit code 1 |
| HTTP 4xx / 5xx             | `Bad status code`                | exit code 1  |
| Response is not valid JSON | `Invalid JSON format`            | exit code 1  |
| Missing `API_KEY`          | `API_KEY not found. Check your .env file` | exit code 1 |
| Missing DataFrame columns  | `Missing Features in the DataFrame: [...]` | exit code 1 |

## Troubleshooting

**`API_KEY not found. Check your .env file`**
The `.env` file is missing, is not in the folder you run the script from, or the variable name is not exactly `API_KEY`.

**`ValueError` about `format="mixed"`**
Your pandas is older than 2.0. Run `pip install --upgrade pandas`.

**`TypeError` or `ValueError` on `df["lon"].astype(float)`**
Some events use `Polygon` geometry, where `coordinates` is a nested list rather than `[lon, lat]`. The script assumes `Point` geometry. See [Known limitations](#known-limitations).

**`IndexError` in `transformation`**
An event has an empty `categories` or `sources` list, and the script indexes `[0]` directly.

**`PermissionError` when writing the CSV**
`nasa_extracted.csv` is open in Excel. Close it and rerun.

**Console floods with JSON**
The script prints the entire response. Remove the `json.dumps(payload, indent=2)` line in `main()` for normal runs.

## Known limitations

- **Polygon geometries are not handled.** `lon` and `lat` are read as `coordinates[0]` and `coordinates[1]`, which is only correct for `Point` geometry. A `Polygon` reading can make the float conversion fail.
- **Only the first category and first source** of each event are kept.
- **Missing text values become the strings `"None"` or `"nan"`** because of `.astype(str)`, so the null summary under-reports nulls in text columns. Using `.astype("string")` preserves real nulls.
- **No deduplication.** Re-running the script overwrites the CSV, and duplicate readings are not removed.
- **Full API response is printed**, which is slow and noisy at `limit=1000`.
- **API key is required by the script** even though EONET does not need one.
- **`main()` redefines `PATH_OUTPUT`** locally, duplicating the module-level constant.

## Roadmap

- Handle `Point` and `Polygon` geometries separately (for example, use the polygon centroid).
- Use `.get()` with safe defaults for categories and sources.
- Use the `"string"` dtype so nulls survive in the CSV.
- Add `status`, `days` and category filters via command-line arguments.
- Add logging in place of `print`.
- Add unit tests for `transformation()` with sample payloads.
- Load into a database (SQLite or PostgreSQL) instead of, or alongside, the CSV.
- Schedule recurring runs (cron, Task Scheduler, or Airflow).

## Data source

Event data comes from NASA's Earth Observatory Natural Event Tracker (EONET). See the [EONET documentation](https://eonet.gsfc.nasa.gov/docs/v3) for the full API reference.