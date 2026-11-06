# import the necessary python modules and libraries

import pandas as pd
import requests
from pathlib import Path
import json

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError


API_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"
PATH_OUTPUT = Path("output")/"nasa_extracted.csv"
TABLE_NAME = "nasa_events"

COLUMNS = ["event_id", "event_title", "category_title", "source",
           "magnitude_value", "magnitude_unit", "event_date", "lon", "lat"]


KEY_COLUMNS = ["event_id", "event_date", "lon", "lat"]

load_dotenv() 
API_KEY= os.getenv("API_KEY")

if not API_KEY:
    print("API_KEY not found. Check your .env file")
    sys.exit(1)

# the databse settings must all in be present before we start
REQUIRED_DB_VARS = ["DB_NAME", "DB_USER", "DB_PASSWORD"]

missing_db_vars = [v for v in REQUIRED_DB_VARS if not os.getenv(v)]
if missing_db_vars:
    print(f"Missing database settings in .env: {missing_db_vars}")
    sys.exit(1)
 
params = {"api_key": API_KEY}
 
print("Success: libraries, API_KEY and database settings imported\n")



#----------------------------------------------------------------------


# commence wih the upstream extract function

def extraction (url:str=API_URL, params:dict=params, timeout:float=10.0) -> list[dict]:
    try: 
        response = requests.get(url=url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.Timeout:
        print("Server took long to respond")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("Please check your Internet Connection")
        sys.exit(1)
    except requests.exceptions.HTTPError:
        print("Bad status code")
        sys.exit(1)
    except requests.exceptions.JSONDecodeError:
        print("Invalid JSON format")
        sys.exit(1)


#------------------------------------------------------------------------
# Initiate the transformation 

def transformation (payload:dict) -> pd.DataFrame:
    rows = []
    for event in payload["events"]:
        for reading in event["geometry"]:
            rows.append({
                # from the event
                "event_id": event["id"],
                "event_title": event["title"],
                "category_title": event["categories"][0]["title"], 
                "source": event["sources"][0]["id"],
                # from the reading

                "magnitude_value": reading.get("magnitudeValue"),
                "magnitude_unit": reading.get("magnitudeUnit"),
                "event_date": reading.get("date"),
                "lon": reading.get("coordinates", [None, None])[0],
                "lat": reading.get("coordinates", [None, None])[1]})
    df = pd.DataFrame(rows, columns=COLUMNS)        

    expected_columns = ["event_id", "event_title", "category_title", "source", "magnitude_value", "magnitude_unit", "event_date", "lon", "lat"]

    missing_columns = [c for c in expected_columns if c not in df.columns]

    if missing_columns:
        print(f"Missing Features in the DataFrame: {missing_columns}")
        sys.exit(1)


    df["event_id"] = df["event_id"].astype(str)
    df["event_title"] = df["event_title"].astype(str)
    df["category_title"] = df["category_title"].astype(str)
    df["source"] = df["source"].astype(str)
    df["magnitude_value"] = df["magnitude_value"].astype(float)
    df["magnitude_unit"] = df["magnitude_unit"].astype(str)
    df["event_date"] = pd.to_datetime(df["event_date"], format= "mixed", errors="coerce", utc=True).dt.date
    df["lon"] = df["lon"].astype(float)
    df["lat"] = df["lat"].astype(float)

    finale_columns = ["event_id", "event_title", "category_title", "source", "magnitude_value", "magnitude_unit", "event_date", "lon", "lat"]
    df = df[finale_columns]

    return df
#-------------------------------------------------------------------------

# the down stream main function

def load (df:pd.DataFrame, path=PATH_OUTPUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path



CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    event_id         VARCHAR(50) NOT NULL,
    event_title      VARCHAR(255),
    category_title   VARCHAR(100),
    source           VARCHAR(100),
    magnitude_value  DOUBLE PRECISION,
    magnitude_unit   VARCHAR(30),
    event_date       DATE,
    lon              DOUBLE PRECISION,
    lat              DOUBLE PRECISION,
    loaded_at        TIMESTAMPTZ DEFAULT now()
);
"""

def get_engine():
    url = URL.create(
        drivername="postgresql+psycopg2",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME"),
    )
 # Aiven only accepts SSL connections, so default to "require"
    return create_engine(url, connect_args={"sslmode": os.getenv("DB_SSLMODE", "require")})



def load_postgres(df: pd.DataFrame, table: str = TABLE_NAME) -> int:
    """
    FULL LOAD: replace everything in the table with the current DataFrame.
    The old rows are removed and the new rows are inserted in ONE transaction,
    so if anything fails the table keeps its previous data (nothing is lost).
    Returns the number of rows loaded.
    """
    # safety: never wipe the table because of an empty extract
    if df.empty:
        print("DataFrame is empty - skipping Postgres load so existing data is kept")
        return 0
 
    engine = get_engine()
    try:
        with engine.begin() as conn:  # commit on success, rollback on any error
            conn.execute(text(CREATE_TABLE_SQL))
 
            # 1) remove all existing rows (keeps the table structure)
            conn.execute(text(f"TRUNCATE TABLE {table}"))
 
            # 2) insert the full, fresh dataset
            df.to_sql(table, conn, if_exists="append",
                      index=False, method="multi", chunksize=1000)
 
        return len(df)
    except SQLAlchemyError as e:
        print(f"Database error: {e}")
        sys.exit(1)
    finally:
        engine.dispose()

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

def main():
    print("Extraction Initiated...\n")
    payload = extraction(params={**params, "limit": 1000})
 
    if payload is None:
        print("**** Extraction failed ****")
        sys.exit(1)
 
    print("API response is successful\n")
    print(f"TOP LEVEL API KEYS: {list(payload.keys())}")
    print(f"Events received: {len(payload.get('events', []))}\n")
 
    df = transformation(payload)
    print(f"Transformed DataFrame shape: {df.shape}\n")
 
    print(f"========= Null records summary =========\n{df.isna().sum()}\n")
    print(df.head())
    print()
 
    # CSV backup
    csv_path = load(df, path=PATH_OUTPUT)
    print(f"CSV FILE SUCCESSFULLY LOADED to {csv_path}")
 
    # PostgreSQL
    loaded = load_postgres(df)
    print(f"POSTGRES: full load complete - {loaded} rows now in '{TABLE_NAME}'")
 
    print("====HAPPY ENGINEERING!---------")
 
 
if __name__ == "__main__":
    main()