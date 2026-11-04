# import the necessary python modules and libraries

import pandas as pd
import requests
from pathlib import Path
import json

import os
import sys
from dotenv import load_dotenv

API_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"
PATH_OUTPUT = Path("output")/"nasa_extracted.csv"

load_dotenv() 
API_KEY= os.getenv("API_KEY")

if not API_KEY:
    print("API_KEY not found. Check your .env file")
    sys.exit(1)

params = {"api_key": API_KEY}

print("Success: libraries and API_KEY imported\n")


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
    df = pd.DataFrame(rows)        

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


# the down stream main function

def load (df:pd.DataFrame, path=PATH_OUTPUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path



def main():
    print("Extraction Initiated...\n")
    payload = extraction(params={**params, "limit":1000})

    if payload is None:
        print("**** Extraction failed ****")
        sys.exit(1)

    print("API resonse is succesful\n")
    print(f"TOP LEVEL API_KEYS: {payload.keys()}\n")
    print(f"JSON RESPONSE: {json.dumps(payload, indent=2)}")


    df = transformation(payload)
    print()
    expected_columns = ["event_id", "event_title", "category_title", "source", "magnitude_value", "magnitude_unit", "event_date", "lon", "lat"]
    print(f"Expected columns: {expected_columns}\n")
    print()

    print(f"=========Null records summary=========:\n {df.isna().sum()}\n")
    print(df)

    PATH_OUTPUT = Path("output")/"nasa_extracted.csv"

    load(df, path=PATH_OUTPUT)
    print(f"CSV_FILE SUCCESSFULLY LOADED to {PATH_OUTPUT}")
    print("====HAPPY ENGINEERING!---------")


if __name__ == "__main__":
    main()