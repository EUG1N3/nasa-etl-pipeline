# NASA EONET ETL Pipeline

A small Python ETL pipeline that pulls natural event data (wildfires, storms, volcanoes, etc.) from NASA's [EONET API](https://eonet.gsfc.nasa.gov/docs/v3), flattens it into a tabular format, and saves it as a CSV file.

## What it does

1. **Extract**: requests events from the EONET v3 `/events` endpoint (currently limited to 10 events).
2. **Transform**: flattens the nested JSON into one row per event reading, enforces column types, and converts timestamps to `YYYY-MM-DD` dates.
3. **Load**: writes the result to `output/nasa_extracted.csv`.

## Project structure

```
nasa-etl-pipeline/
├── extract.py          # the ETL script (extract, transform, load, main)
├── output/
│   └── nasa_extracted.csv   # generated output
├── requirements.txt    # Python dependencies
├── .env                # local environment variables (not committed)
├── .gitignore
└── README.md
```

## Requirements

- Python 3.9+
- Packages listed in `requirements.txt` (`pandas`, `requests`, `python-dotenv`)

## Setup

1. **Clone the repository and move into it**

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

   > The EONET endpoint is public and does not require a key, but the script currently checks for `API_KEY` at startup and exits if it is missing. You can get a free key at [api.nasa.gov](https://api.nasa.gov/).

## Usage

```bash
python extract.py
```

On success the script prints a null-value summary and the transformed DataFrame, then writes the CSV:

```
CSV_FILE SUCCESSFULLY LOADED to output\nasa_extracted.csv
```

## Output schema

| Column            | Description                                   |
|-------------------|-----------------------------------------------|
| `event_id`        | Unique EONET event ID                         |
| `event_title`     | Event name                                    |
| `category_title`  | Event category (e.g. Wildfires, Severe Storms)|
| `source`          | ID of the first listed data source            |
| `magnitude_value` | Measured magnitude, if provided               |
| `magnitude_unit`  | Unit of the magnitude (e.g. acres, kts)       |
| `event_date`      | Date of the reading (`YYYY-MM-DD`)            |

Each event can have several readings, so one `event_id` may appear on multiple rows.

## Configuration

| Setting      | Where                | Default                    |
|--------------|----------------------|----------------------------|
| `API_URL`    | `extract.py`         | EONET v3 `/events` endpoint|
| `PATH_OUTPUT`| `extract.py`         | `output/nasa_extracted.csv`|
| `limit`      | `main()` in `extract.py` | `10` events            |
| `API_KEY`    | `.env`               | none (required by script)  |

## Error handling

The extract step handles timeouts, connection errors, bad HTTP status codes, and invalid JSON. If extraction fails, the script prints a message and exits with status code 1.

## Known limitations

- Only the first category and first source of each event are kept.
- `lon` and `lat` are extracted but dropped from the final CSV.
- Only 10 events are fetched per run.

## Possible next steps

- Add `status` and `days` filters to the API request.
- Keep coordinates (handling Point vs Polygon geometries).
- Add logging, tests, and scheduled runs.
- Load into a database instead of a CSV.

## Data source

Event data is provided by NASA's Earth Observatory Natural Event Tracker (EONET).