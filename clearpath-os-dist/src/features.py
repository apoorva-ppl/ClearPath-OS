"""
features.py  —  Stage 3 of the pipeline.

IN : data/processed/clean.parquet   (must already have targets from targets.py)
OUT: data/processed/features.parquet (model-ready feature matrix + targets + meta)

Feature set (kept deliberately lean and defensible)
---------------------------------------------------
  categorical : event_cause, event_type, corridor   (as pandas 'category' codes)
  temporal    : hour, dow, month, is_weekend
  spatial     : latitude, longitude
  engineered  : corridor_recent_count
                = number of incidents on the SAME corridor in the prior 7 days.
                This is the one genuinely clever, leak-free signal: it captures
                "this stretch has been hot lately" without peeking into the future.

Both models (severity classifier, duration regressor) read this one table.

Run:  python -m src.features
"""
from __future__ import annotations

import pandas as pd

from .utils import load_config, resolve, log

CATEGORICAL = ["event_cause", "event_type", "corridor"]
TEMPORAL = ["hour", "dow", "month", "is_weekend"]
SPATIAL = ["latitude", "longitude"]
ENGINEERED = ["corridor_recent_count"]

FEATURE_COLS = CATEGORICAL + TEMPORAL + SPATIAL + ENGINEERED


def _corridor_recent_count(df: pd.DataFrame, window_days: int = 7) -> pd.Series:
    """For each row: # incidents on the same corridor in the preceding window.

    Leak-free: counts only events strictly BEFORE the current one (the row
    itself is excluded). Implemented per corridor with a time-indexed rolling
    count, then aligned back by the original index — no positional lookups, so
    it cannot silently corrupt a row.
    """
    out = pd.Series(0, index=df.index, dtype=int)
    window = pd.Timedelta(days=window_days)

    for _, grp in df.groupby("corridor", sort=False):
        # time-indexed series of 1s; sort by time within the corridor
        g = grp.sort_values("start_datetime")
        s = pd.Series(1, index=g["start_datetime"].values)
        # rolling COUNT over the time window, inclusive of the current point...
        rolled = s.rolling(window=window, closed="both").count()
        # ...then subtract 1 to exclude the current event itself -> "preceding".
        # Ties at the exact same timestamp are treated as preceding, which is the
        # conservative/safe choice for a recency feature.
        counts = (rolled.to_numpy() - 1).astype(int)
        # align back to the original frame index for this group (order preserved)
        out.loc[g.index] = counts

    # safety: the feature must never be negative
    assert (out >= 0).all(), "corridor_recent_count produced a negative value"
    return out


def build_features(cfg: dict | None = None) -> pd.DataFrame:
    cfg = cfg or load_config()
    clean_path = resolve(cfg["paths"]["clean_parquet"])
    out_path = resolve(cfg["paths"]["features_parquet"])

    df = pd.read_parquet(clean_path)

    # engineered rolling feature
    log("features: computing corridor_recent_count (7d rolling)...")
    df["corridor_recent_count"] = _corridor_recent_count(df, window_days=7)

    # cast categoricals to category dtype (LightGBM consumes these natively)
    for c in CATEGORICAL:
        df[c] = df[c].astype("category")

    # assemble output: features + targets + a few meta cols for the app/eval
    keep = (
        FEATURE_COLS
        + ["closure_label", "impact_level", "impact_score", "dur_target_min"]
        + ["id", "start_datetime", "requires_road_closure",
           "police_station", "status", "resolved_datetime", "address"]
    )
    keep = [c for c in keep if c in df.columns]
    out = df[keep].copy()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(out_path, index=False)
    log(f"features: wrote {out.shape[0]} rows x {len(FEATURE_COLS)} features -> {out_path}")
    return out


if __name__ == "__main__":
    build_features()
