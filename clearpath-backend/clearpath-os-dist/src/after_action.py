"""
after_action.py  —  Stage 7  (the differentiator deliverable).

IN : data/processed/features.parquet  +  models/duration.txt
OUT: - models/after_action.csv   (per-incident predicted vs actual clearance)
     - models/after_action.json  (summary: MAE before vs after retrain)
     returns a dict the Streamlit app plots.

Directly answers the PS gap "No post-event learning system."
We take CLOSED incidents that have a real resolved/closed time, compute ACTUAL
clearance minutes, and compare against what the model would have predicted. We
then demonstrate the learning loop: retrain including the most recent closed
window and show the held-out error shrink. That is the "model learns from its
own errors" story, grounded in real columns (status == closed, closed_datetime).

Run:  python -m src.after_action
"""
from __future__ import annotations

import json

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error

from .features import CATEGORICAL, FEATURE_COLS
from .utils import load_config, resolve, log


def run(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    df = pd.read_parquet(resolve(cfg["paths"]["features_parquet"]))

    # only incidents with a usable, real clearance time
    closed = df[(df["status"] == "closed") & df["dur_target_min"].notna()].copy()
    closed = closed.sort_values("start_datetime")
    log(f"after-action: {len(closed)} closed incidents with real clearance time")

    def _fit(train_df):
        ds = lgb.Dataset(train_df[FEATURE_COLS],
                         label=np.log1p(train_df["dur_target_min"].values),
                         categorical_feature=CATEGORICAL)
        return lgb.train(
            dict(objective="regression_l1", metric="l1", learning_rate=0.05,
                 num_leaves=31, min_data_in_leaf=20, seed=cfg["seed"], verbose=-1),
            ds, num_boost_round=300,
        )

    # Expanding-window evaluation of the learning loop.
    # Fix the final slice as the common held-out "future" both models are scored on.
    # V1 = the early model (small history). V2 = the matured model that has since
    # ingested more closed incidents (everything up to the holdout). Both are
    # evaluated on the SAME unseen holdout, so any gap reflects genuine learning.
    n = len(closed)
    holdout_start = int(n * 0.80)
    seed_end = int(n * 0.40)                 # V1 sees only the first 40%
    holdout = closed.iloc[holdout_start:]
    if len(holdout) < 10:
        log("after-action: holdout small; results indicative only")

    m1 = _fit(closed.iloc[:seed_end])               # early / naive model
    m2 = _fit(closed.iloc[:holdout_start])          # matured model (more data)

    y_true = holdout["dur_target_min"].values
    p1 = np.clip(np.expm1(m1.predict(holdout[FEATURE_COLS])), 0, None)
    p2 = np.clip(np.expm1(m2.predict(holdout[FEATURE_COLS])), 0, None)

    mae_before = float(mean_absolute_error(y_true, p1))
    mae_after = float(mean_absolute_error(y_true, p2))
    delta_pct = (mae_before - mae_after) / mae_before * 100 if mae_before else 0.0
    # positive delta_pct => matured model is better; negative => distribution drift
    # dominates and more history did not help. We report it honestly either way;
    # the deliverable's value is the MONITORING loop, not a guaranteed win.
    learning_helped = mae_after < mae_before

    # per-incident table for the scatter plot (deployed model vs actual)
    table = holdout[["id", "start_datetime", "event_cause", "corridor"]].copy()
    table["actual_min"] = y_true
    table["predicted_min"] = p2 if learning_helped else p1
    table["abs_error_min"] = np.abs(
        y_true - (p2 if learning_helped else p1))
    table.to_csv(resolve("models/after_action.csv"), index=False)

    summary = {
        "n_closed": int(len(closed)),
        "n_holdout": int(len(holdout)),
        "mae_seed_model_min": round(mae_before, 1),
        "mae_matured_model_min": round(mae_after, 1),
        "delta_pct": round(delta_pct, 1),
        "learning_helped": bool(learning_helped),
        "note": ("Matured model improved on the unseen window."
                 if learning_helped else
                 "More history did not reduce error on the latest window — "
                 "evidence of distribution drift; the loop surfaces this so an "
                 "operator can investigate rather than trust a stale model."),
    }
    resolve("models/after_action.json").write_text(json.dumps(summary, indent=2))
    log(f"after-action: seed MAE {mae_before:.1f} -> matured {mae_after:.1f} min "
        f"({delta_pct:+.1f}%); learning_helped={learning_helped}")
    return {"summary": summary, "table": table}


if __name__ == "__main__":
    run()
