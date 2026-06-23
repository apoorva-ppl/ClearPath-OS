"""
train_duration.py  —  Stage 4b.

IN : data/processed/features.parquet
OUT: models/duration.txt   (LightGBM regressor, predicts log1p(minutes))
     metrics.json updated with duration MAE / median-AE (in minutes)

Task type
---------
SUPERVISED REGRESSION on cleaned clearance time. Trained only on rows where
dur_target_min is usable (positive, under the 24h ceiling, percentile-capped).
We learn in log space (log1p) because clearance times are heavily right-skewed,
then invert with expm1 for reporting in real minutes.

If MAE is poor, the app falls back to presenting a TIER (<60 / 60-240 / 240+ min)
rather than a misleadingly precise number — see pipeline.py.

Run:  python -m src.train_duration
"""
from __future__ import annotations

import json

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, median_absolute_error

from .features import CATEGORICAL, FEATURE_COLS
from .utils import load_config, resolve, log


def train(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    df = pd.read_parquet(resolve(cfg["paths"]["features_parquet"]))
    df = df[df["dur_target_min"].notna()].copy()

    cut = pd.Timestamp(cfg["split"]["train_end"], tz="UTC")
    tr = df[df["start_datetime"] < cut]
    va = df[df["start_datetime"] >= cut]
    log(f"duration: train={len(tr)} val={len(va)} (usable-duration rows only)")

    if len(va) < 20:
        log("duration: WARNING — tiny validation set; metrics are indicative only.")

    y_tr = np.log1p(tr["dur_target_min"].values)
    y_va_real = va["dur_target_min"].values

    train_set = lgb.Dataset(tr[FEATURE_COLS], label=y_tr,
                            categorical_feature=CATEGORICAL)

    params = dict(
        objective="regression_l1",   # L1 -> optimise toward MAE directly
        metric="l1",
        learning_rate=0.05,
        num_leaves=31,
        min_data_in_leaf=20,
        feature_fraction=0.9,
        bagging_fraction=0.9,
        bagging_freq=1,
        seed=cfg["seed"],
        verbose=-1,
    )

    # validation in log space
    val_set = lgb.Dataset(va[FEATURE_COLS], label=np.log1p(y_va_real),
                          reference=train_set, categorical_feature=CATEGORICAL)
    model = lgb.train(
        params, train_set,
        num_boost_round=500,
        valid_sets=[val_set],
        callbacks=[lgb.early_stopping(40, verbose=False), lgb.log_evaluation(0)],
    )

    pred_real = np.expm1(model.predict(va[FEATURE_COLS]))
    pred_real = np.clip(pred_real, 0, None)
    mae = mean_absolute_error(y_va_real, pred_real)
    medae = median_absolute_error(y_va_real, pred_real)
    log(f"duration: val MAE={mae:.1f} min  median-AE={medae:.1f} min")

    model_path = resolve(cfg["paths"]["duration_model"])
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(model_path))

    metrics = {"duration": {
        "mae_minutes": round(float(mae), 2),
        "median_ae_minutes": round(float(medae), 2),
        "n_train": int(len(tr)),
        "n_val": int(len(va)),
        "best_iteration": model.best_iteration,
    }}
    _merge_metrics(cfg, metrics)
    return metrics


def _merge_metrics(cfg: dict, new: dict) -> None:
    path = resolve(cfg["paths"]["metrics"])
    data = json.loads(path.read_text()) if path.exists() else {}
    data.update(new)
    path.write_text(json.dumps(data, indent=2))


if __name__ == "__main__":
    train()
