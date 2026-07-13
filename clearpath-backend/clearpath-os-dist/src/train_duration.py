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

    y_tr = np.log1p(tr["dur_target_min"].values) #compresses very large clearane times into smaller range , making learning easier.
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

    pred_real = np.expm1(model.predict(va[FEATURE_COLS])) #Converts predictions back from log scale to real minutes.
    pred_real = np.clip(pred_real, 0, None) #Prevents the model from producing impossible negative clearance times.
    mae = mean_absolute_error(y_va_real, pred_real) #Average prediction error measured in minutes
    medae = median_absolute_error(y_va_real, pred_real) #Typical prediction error after ignoring a few extreme incidents.
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

#Merges the newly generated model metrics into metrics.json without deleting the existing ones.
def _merge_metrics(cfg: dict, new: dict) -> None:
    path = resolve(cfg["paths"]["metrics"])
    data = json.loads(path.read_text()) if path.exists() else {}
    data.update(new)
    path.write_text(json.dumps(data, indent=2))


if __name__ == "__main__":
    train()
