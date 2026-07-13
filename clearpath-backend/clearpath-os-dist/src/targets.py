from __future__ import annotations
import numpy as np
import pandas as pd
from .utils import load_config, resolve, log

#creates clean regression and classification targets.
def _clean_duration(df: pd.DataFrame, cfg: dict) -> pd.Series:
    """Return a cleaned clearance-minutes series; unusable rows -> NaN."""
    d = df["clearance_minutes"].copy() #raw duration contains impossible values and extreme outliers 
    dc = cfg["duration"]
    # non-positive or absurd -> NaN
    d = d.where(d >= dc["min_minutes"])
    # absolute hard ceiling(70000 minutes= 48.5 days)->NaN.
    d = d.where(d <= dc["hard_cap_minutes"])
    # percentile cap on what remains
    if d.notna().any():
        cap = d.quantile(dc["cap_percentile"])
        d = d.clip(upper=cap) #clipping preserves row while reducing the impact of extreme outliers on the regression model.
    return d

#creates business score (severity score based on closure , priority , cause , duration)
#its Rule Based , not ML based .since its simpler + transparent + explainable + easy to tune for business needs.
def _severity_score(df: pd.DataFrame, dur_clean: pd.Series, cfg: dict) -> pd.Series:
    s = cfg["severity"]
    score = pd.Series(0, index=df.index, dtype=float)

    # closure
    score += df["requires_road_closure"].astype(int) * s["closure_points"]
    # priority
    score += df["priority"].eq("High").astype(int) * s["priority_high_points"]
    # cause points(diff events have diff weights)
    cause_pts = df["event_cause"].map(s["cause_points"]).fillna(s["default_cause_points"])
    score += cause_pts
    # duration tier points (only where duration is usable)
    over_240 = (dur_clean > 240).fillna(False)
    over_60 = ((dur_clean > 60) & (dur_clean <= 240)).fillna(False)
    score += over_240.astype(int) * s["duration_points"]["over_240_min"]
    score += over_60.astype(int) * s["duration_points"]["over_60_min"]
    return score

#main function.
def build_targets(cfg: dict | None = None) -> pd.DataFrame:
    cfg = cfg or load_config()
    path = resolve(cfg["paths"]["clean_parquet"])
    df = pd.read_parquet(path)

    # classification target -> "will this incident requires a road closure?(T/F)"
    df["closure_label"] = df["requires_road_closure"].astype(int)

    # regression target-> "how long will this incident last (in minutes)?""
    dur_clean = _clean_duration(df, cfg)
    df["dur_target_min"] = dur_clean

    # impact level target ->"how severe was the incident?"
    score = _severity_score(df, dur_clean, cfg)
    bins = cfg["severity"]["bins"]
    level = np.where(
        score >= bins["high_min"], 2,
        np.where(score >= bins["medium_min"], 1, 0),
    )
    df["impact_score"] = score
    df["impact_level"] = level.astype(int)

    df.to_parquet(path, index=False) #save the dataset which contains( classification target , regression target + impact score)

    pos = int(df["closure_label"].sum())
    #these logs warns if theres class imbalance.
    log(f"targets: closure_label (SUPERVISED) positives = {pos}/{len(df)} "
        f"({100*pos/len(df):.1f}% -> imbalanced, handled in training)")
    dist = df["impact_level"].value_counts().sort_index()
    log(f"targets: impact_level DISPLAY rubric (0=Low,1=Med,2=High):\n{dist.to_string()}")
    log(f"targets: usable duration rows = {df['dur_target_min'].notna().sum()}/{len(df)}")
    return df


if __name__ == "__main__":
    build_targets()
