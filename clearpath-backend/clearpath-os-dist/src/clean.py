from __future__ import annotations
import pandas as pd
from .utils import load_config, resolve, log

#Columns having less than 4% information, remove as it adds noise.
DROP_SPARSE = [
    "direction", "route_path", "cargo_material",
    "age_of_truck", "reason_breakdown",
]
#List of timestamp columns
TS_COLS = [
    "start_datetime", "end_datetime", "created_date",
    "modified_datetime", "resolved_datetime", "closed_datetime",
]

# Bengaluru bounding box , anything outside is a geocoding error.(lat n long should be in range of bengaluru city)
BBOX = dict(lat_min=12.6, lat_max=13.3, lng_min=77.2, lng_max=77.9)

#converts date cols to datetime format, if conversion fails return Nat
def _parse_ts(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True) #avoids timezone issues bugs .

#main function.
def clean(cfg: dict | None = None) -> pd.DataFrame:
    cfg = cfg or load_config()
    raw_path = resolve(cfg["paths"]["raw_csv"]) #locates raw csv file path .
    out_path = resolve(cfg["paths"]["clean_parquet"]) #load dataset.

    log(f"reading {raw_path}")
    df = pd.read_csv(raw_path)
    n0 = len(df)

    #convert timestamps to proper datetime format .
    for c in TS_COLS:
        if c in df.columns:
            df[c] = _parse_ts(df[c])

    # --- drop sparse, useless columns ---
    df = df.drop(columns=[c for c in DROP_SPARSE if c in df.columns])

    # Removes useless columns , improves model performance .
    df["event_cause"] = (
        df["event_cause"].astype(str).str.strip().str.lower()
        .replace({"nan": "others", "": "others"})
    )

    #normalise text cols (accident , Accident , ACCIDENT , etc -> accident)
    df["event_type"] = df["event_type"].astype(str).str.strip().str.lower()
    df["priority"] = df["priority"].astype(str).str.strip().str.title()
    df["corridor"] = df["corridor"].fillna("Non-corridor").astype(str).str.strip()
    # write in clean boolean(TRUE / FALSE -> True / False)
    df["requires_road_closure"] = (
        df["requires_road_closure"].astype(str).str.upper().eq("TRUE")
    )

    # converts lat/lng to numeric , invalid values becomes NaN.
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    in_bbox = (
        df["latitude"].between(BBOX["lat_min"], BBOX["lat_max"])
        & df["longitude"].between(BBOX["lng_min"], BBOX["lng_max"])
    )

    # row filter: need a start time + valid coords 
    keep = df["start_datetime"].notna() & in_bbox
    df = df[keep].copy()

    #  raw clearance minutes 
    df["clearance_minutes"] = (
        (df["closed_datetime"] - df["start_datetime"]).dt.total_seconds() / 60.0
    )

    # adds derived features : hour of day , day of week, month of year , is_weekend (14:00 != 2:00)
    df["hour"] = df["start_datetime"].dt.hour
    df["dow"] = df["start_datetime"].dt.dayofweek          # 0=Mon
    df["month"] = df["start_datetime"].dt.month
    df["is_weekend"] = df["dow"].isin([5, 6]).astype(int)

    df = df.sort_values("start_datetime").reset_index(drop=True) #keeps event in chronological order, resets index for better readability.
    
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)  #stores in clean parquet format for better performance + smaller size.
    log(f"clean: kept {len(df)}/{n0} rows -> {out_path}") #helpful for debugging
    return df


if __name__ == "__main__":
    clean()
