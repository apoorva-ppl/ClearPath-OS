from __future__ import annotations
import json
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import (
    roc_auc_score, average_precision_score, f1_score,
    precision_score, recall_score, confusion_matrix, classification_report,)
from .features import CATEGORICAL, FEATURE_COLS
from .utils import load_config, resolve, log

TARGET = "closure_label"
DECISION_THRESHOLD = 0.5   # If predicted probability ≥ 0.5 → Closure, otherwise No Closure

#splits data chronologically into training n validation sets
#train on past incident + validate on future incidents
def _split(df: pd.DataFrame, cfg: dict):
    cut = pd.Timestamp(cfg["split"]["train_end"], tz="UTC")
    return df[df["start_datetime"] < cut], df[df["start_datetime"] >= cut]


def train(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    df = pd.read_parquet(resolve(cfg["paths"]["features_parquet"]))

    tr, va = _split(df, cfg)
    y_tr, y_va = tr[TARGET], va[TARGET]
    pos, neg = int(y_tr.sum()), int((y_tr == 0).sum())
    spw = max(1.0, neg / max(1, pos))     # scale_pos_weight
    log(f"closure: train={len(tr)} (pos={pos}) val={len(va)} (pos={int(y_va.sum())}) "
        f"scale_pos_weight={spw:.1f}")

    train_set = lgb.Dataset(tr[FEATURE_COLS], label=y_tr,
                            categorical_feature=CATEGORICAL)
    val_set = lgb.Dataset(va[FEATURE_COLS], label=y_va, reference=train_set,
                          categorical_feature=CATEGORICAL)
    #model parameters used 
    params = dict(
        objective="binary",
        metric="auc",
        scale_pos_weight=spw,
        learning_rate=0.05, #slow + stable
        num_leaves=31, #more leaves , more complex tree
        min_data_in_leaf=30,
        feature_fraction=0.9, #training sample per iteration to improve generalisation
        bagging_fraction=0.9,
        bagging_freq=1,
        seed=cfg["seed"], #makes training reproducible
        verbose=-1,
    )

    model = lgb.train(
        params, train_set,
        num_boost_round=500,
        valid_sets=[val_set],
        callbacks=[lgb.early_stopping(40, verbose=False), lgb.log_evaluation(0)], #Stops training if validation performance doesn't improve for 40 rounds
    )

   
    proba = model.predict(va[FEATURE_COLS])  # Predicts probability of road closure
    pred = (proba >= DECISION_THRESHOLD).astype(int) #Converts probability into Yes/No using threshold = 0.5
    
    #evaluation metrics.
    roc = roc_auc_score(y_va, proba) if y_va.nunique() > 1 else float("nan")
    pr = average_precision_score(y_va, proba) if y_va.nunique() > 1 else float("nan")
    f1_pos = f1_score(y_va, pred, pos_label=1, zero_division=0)
    prec_pos = precision_score(y_va, pred, pos_label=1, zero_division=0)
    rec_pos = recall_score(y_va, pred, pos_label=1, zero_division=0)
    cm = confusion_matrix(y_va, pred, labels=[0, 1]).tolist()
    report = classification_report(y_va, pred, labels=[0, 1],
                                   target_names=["No closure", "Closure"],
                                   zero_division=0)
    log(f"closure: ROC-AUC={roc:.3f}  PR-AUC={pr:.3f}  "
        f"closure-class P={prec_pos:.2f} R={rec_pos:.2f} F1={f1_pos:.2f}")
    log("closure: classification report\n" + report)


    model_path = resolve(cfg["paths"]["severity_model"])
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(model_path))
  
  #shows which features contributed the most to model decision.
    imp = pd.DataFrame({
        "feature": model.feature_name(),
        "gain": model.feature_importance(importance_type="gain"),
    }).sort_values("gain", ascending=False)
    imp.to_csv(resolve("models/severity_importance.csv"), index=False)

    metrics = {"closure": {
        "roc_auc": round(float(roc), 4),
        "pr_auc": round(float(pr), 4),
        "closure_precision": round(float(prec_pos), 4),
        "closure_recall": round(float(rec_pos), 4),
        "closure_f1": round(float(f1_pos), 4),
        "confusion_matrix": cm,
        "labels": ["No closure", "Closure"],
        "decision_threshold": DECISION_THRESHOLD,
        "n_train": len(tr),
        "n_val": len(va),
        "val_positives": int(y_va.sum()),
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
