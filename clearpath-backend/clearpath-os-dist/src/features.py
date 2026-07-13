from __future__ import annotations
import pandas as pd
from .utils import load_config, resolve, log

CATEGORICAL = ["event_cause", "event_type", "corridor"]
TEMPORAL = ["hour", "dow", "month", "is_weekend"] #answers when did the event happened
SPATIAL = ["latitude", "longitude"] #where did the incident happen
ENGINEERED = ["corridor_recent_count"] #how many events happened at the same corridor(feature engineered)

FEATURE_COLS = CATEGORICAL + TEMPORAL + SPATIAL + ENGINEERED

#Creates a traffic history feature for every corridor.
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
        g = grp.sort_values("start_datetime") #chronological sort
        s = pd.Series(1, index=g["start_datetime"].values)
        rolled = s.rolling(window=window, closed="both").count() #rolling->looks only at incident from past 7 days
        counts = (rolled.to_numpy() - 1).astype(int) #Removes the current incident from its own count to avoid data leakage
        out.loc[g.index] = counts

    # safety: the feature must never be negative
    assert (out >= 0).all(), "corridor_recent_count produced a negative value"
    return out

#Loads cleaned dataset with targets.
def build_features(cfg: dict | None = None) -> pd.DataFrame:
    cfg = cfg or load_config()
    clean_path = resolve(cfg["paths"]["clean_parquet"])
    out_path = resolve(cfg["paths"]["features_parquet"])

    df = pd.read_parquet(clean_path)

    # engineered rolling feature
    log("features: computing corridor_recent_count (7d rolling)...")
    df["corridor_recent_count"] = _corridor_recent_count(df, window_days=7)

    # Converts text columns into categorical data so LightGBM can handle them directly without One-Hot Encoding.
    for c in CATEGORICAL:
        df[c] = df[c].astype("category")

    # features + targets + a few meta cols for the app/eval
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
