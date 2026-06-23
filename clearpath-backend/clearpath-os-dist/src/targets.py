"""
targets.py  —  Stage 2 of the pipeline.

IN : data/processed/clean.parquet
OUT: same frame + target/label columns, written back to clean.parquet
       - closure_label   : 0/1  (requires_road_closure)  -> SUPERVISED classifier target
       - dur_target_min  : cleaned clearance minutes (NaN where unusable) -> regressor target
       - impact_level    : ordinal 0/1/2 (Low/Medium/High) -> DISPLAY rubric only (not learned)
       - impact_score    : the rubric's raw score (for auditing)

What the model learns vs what is a rule
---------------------------------------
The model's SUPERVISED target is `requires_road_closure` — a real, recorded
operational decision that is NOT constructed from the features. Predicting it is
genuine forecasting: "given cause/corridor/time/location/recent-activity, will
this incident require a road closure?" This is deliberately separated from the
impact rubric to avoid a circular target.

`impact_level` is a TRANSPARENT DISPLAY RUBRIC (not a learned target). It buckets
incidents for the control room from closure + priority + cause + duration-tier.
At inference time the app derives the displayed severity from the MODEL'S closure
probability + predicted duration + cause weight — so the number shown to an
operator is driven by learned predictions, while the bucketing thresholds remain
auditable business rules. The data has no measured congestion column, so impact
itself is never claimed as a learned quantity.

Run:  python -m src.targets
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .utils import load_config, resolve, log


def _clean_duration(df: pd.DataFrame, cfg: dict) -> pd.Series:
    """Return a cleaned clearance-minutes series; unusable rows -> NaN."""
    d = df["clearance_minutes"].copy()
    dc = cfg["duration"]
    # non-positive or absurd -> NaN
    d = d.where(d >= dc["min_minutes"])
    # absolute hard ceiling
    d = d.where(d <= dc["hard_cap_minutes"])
    # percentile cap on what remains
    if d.notna().any():
        cap = d.quantile(dc["cap_percentile"])
        d = d.clip(upper=cap)
    return d


def _severity_score(df: pd.DataFrame, dur_clean: pd.Series, cfg: dict) -> pd.Series:
    s = cfg["severity"]
    score = pd.Series(0, index=df.index, dtype=float)

    # closure
    score += df["requires_road_closure"].astype(int) * s["closure_points"]
    # priority
    score += df["priority"].eq("High").astype(int) * s["priority_high_points"]
    # cause points
    cause_pts = df["event_cause"].map(s["cause_points"]).fillna(s["default_cause_points"])
    score += cause_pts
    # duration tier points (only where duration is usable)
    over_240 = (dur_clean > 240).fillna(False)
    over_60 = ((dur_clean > 60) & (dur_clean <= 240)).fillna(False)
    score += over_240.astype(int) * s["duration_points"]["over_240_min"]
    score += over_60.astype(int) * s["duration_points"]["over_60_min"]
    return score


def build_targets(cfg: dict | None = None) -> pd.DataFrame:
    cfg = cfg or load_config()
    path = resolve(cfg["paths"]["clean_parquet"])
    df = pd.read_parquet(path)

    # --- SUPERVISED classifier target: requires_road_closure (real, recorded) ---
    df["closure_label"] = df["requires_road_closure"].astype(int)

    # --- SUPERVISED regression target: cleaned clearance minutes ---
    dur_clean = _clean_duration(df, cfg)
    df["dur_target_min"] = dur_clean

    # --- DISPLAY rubric (NOT learned): impact_level for the control room ---
    score = _severity_score(df, dur_clean, cfg)
    bins = cfg["severity"]["bins"]
    level = np.where(
        score >= bins["high_min"], 2,
        np.where(score >= bins["medium_min"], 1, 0),
    )
    df["impact_score"] = score
    df["impact_level"] = level.astype(int)

    df.to_parquet(path, index=False)

    pos = int(df["closure_label"].sum())
    log(f"targets: closure_label (SUPERVISED) positives = {pos}/{len(df)} "
        f"({100*pos/len(df):.1f}% -> imbalanced, handled in training)")
    dist = df["impact_level"].value_counts().sort_index()
    log(f"targets: impact_level DISPLAY rubric (0=Low,1=Med,2=High):\n{dist.to_string()}")
    log(f"targets: usable duration rows = {df['dur_target_min'].notna().sum()}/{len(df)}")
    return df


if __name__ == "__main__":
    build_targets()
