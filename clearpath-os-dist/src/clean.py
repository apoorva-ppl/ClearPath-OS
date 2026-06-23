"""
clean.py  —  Stage 1 of the pipeline.

IN : data/raw/astram_events.csv   (raw Astram incident export, ~8.2k rows)
OUT: data/processed/clean.parquet (typed, de-noised, analysis-ready)

What it does
------------
- Parses all timestamp columns to tz-aware datetimes.
- Drops columns that are <4% populated and carry no usable signal
  (direction, route_path, cargo_material, age_of_truck, reason_breakdown).
- Normalises event_cause (merges 'Debris'/'debris', lowercases, fills blanks).
- Keeps only rows with a valid start_datetime and in-Bengaluru coordinates.
- Computes raw clearance_minutes = closed_datetime - start_datetime
  (NOT cleaned here — targets.py does the capping; this is the raw signal).

Run:  python -m src.clean
"""
from __future__ import annotations

import pandas as pd

from .utils import load_config, resolve, log

# Columns to discard: each is <4% populated in the source and adds noise only.
DROP_SPARSE = [
    "direction", "route_path", "cargo_material",
    "age_of_truck", "reason_breakdown",
]

TS_COLS = [
    "start_datetime", "end_datetime", "created_date",
    "modified_datetime", "resolved_datetime", "closed_datetime",
]

# Bengaluru bounding box — anything outside is a geocoding error.
BBOX = dict(lat_min=12.6, lat_max=13.3, lng_min=77.2, lng_max=77.9)


def _parse_ts(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True)


def clean(cfg: dict | None = None) -> pd.DataFrame:
    cfg = cfg or load_config()
    raw_path = resolve(cfg["paths"]["raw_csv"])
    out_path = resolve(cfg["paths"]["clean_parquet"])

    log(f"reading {raw_path}")
    df = pd.read_csv(raw_path)
    n0 = len(df)

    # --- timestamps ---
    for c in TS_COLS:
        if c in df.columns:
            df[c] = _parse_ts(df[c])

    # --- drop sparse, useless columns ---
    df = df.drop(columns=[c for c in DROP_SPARSE if c in df.columns])

    # --- normalise event_cause ---
    df["event_cause"] = (
        df["event_cause"].astype(str).str.strip().str.lower()
        .replace({"nan": "others", "": "others"})
    )

    # --- normalise a few other categoricals ---
    df["event_type"] = df["event_type"].astype(str).str.strip().str.lower()
    df["priority"] = df["priority"].astype(str).str.strip().str.title()
    df["corridor"] = df["corridor"].fillna("Non-corridor").astype(str).str.strip()
    # requires_road_closure -> clean boolean
    df["requires_road_closure"] = (
        df["requires_road_closure"].astype(str).str.upper().eq("TRUE")
    )

    # --- coordinate sanity ---
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    in_bbox = (
        df["latitude"].between(BBOX["lat_min"], BBOX["lat_max"])
        & df["longitude"].between(BBOX["lng_min"], BBOX["lng_max"])
    )

    # --- row filter: need a start time + valid coords ---
    keep = df["start_datetime"].notna() & in_bbox
    df = df[keep].copy()

    # --- raw clearance minutes (uncleaned) ---
    df["clearance_minutes"] = (
        (df["closed_datetime"] - df["start_datetime"]).dt.total_seconds() / 60.0
    )

    # --- derived time parts (used downstream + handy for EDA) ---
    df["hour"] = df["start_datetime"].dt.hour
    df["dow"] = df["start_datetime"].dt.dayofweek          # 0=Mon
    df["month"] = df["start_datetime"].dt.month
    df["is_weekend"] = df["dow"].isin([5, 6]).astype(int)

    df = df.sort_values("start_datetime").reset_index(drop=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    log(f"clean: kept {len(df)}/{n0} rows -> {out_path}")
    return df


if __name__ == "__main__":
    clean()
