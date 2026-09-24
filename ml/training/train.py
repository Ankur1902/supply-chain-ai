#!/usr/bin/env python
"""
Trains and compares candidate models for late-delivery-risk classification,
selects a winner, and persists everything needed for serving:

  - the full sklearn Pipeline (ColumnTransformer + classifier), so inference
    never has to reimplement encoding logic
  - metadata (feature names, metrics, dataset version, training timestamp)
  - a registry row in MySQL `model_versions` (status='active'; any
    previously active version is archived, never deleted)
  - SHAP-based per-shipment risk factors for every shipment currently in the
    database, plus a global feature-importance summary

CHRONOLOGICAL SPLIT: rows are sorted by order_date and split by a time
cutoff (not sklearn's random train_test_split), so the model is always
evaluated on orders that happened after everything it trained on — this
prevents a model that's memorized future trends from looking artificially
good. See docs/ml-system.md.

Usage:
    python ml/training/train.py --input data/processed/04_features.parquet
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import scipy.sparse
import shap
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend"))

from ml.features.feature_spec import (  # noqa: E402
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    TARGET_COLUMN,
)

ARTIFACTS_DIR = REPO_ROOT / "ml" / "artifacts"
TEST_FRACTION = 0.2
RANDOM_STATE = 42
TOP_N_RISK_FACTORS = 5
SHAP_BATCH_SIZE = 2000


def build_preprocessor(scale_numeric: bool) -> ColumnTransformer:
    numeric_steps = [("scaler", StandardScaler())] if scale_numeric else [("passthrough", "passthrough")]
    return ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
            ("num", Pipeline(numeric_steps) if scale_numeric else "passthrough", NUMERIC_FEATURES),
        ]
    )


def chronological_split(df: pd.DataFrame, test_fraction: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.sort_values("order_date").reset_index(drop=True)
    cutoff_idx = int(len(df) * (1 - test_fraction))
    cutoff_date = df.iloc[cutoff_idx]["order_date"]
    train = df[df["order_date"] < cutoff_date]
    test = df[df["order_date"] >= cutoff_date]
    return train, test


def evaluate(model: Pipeline, X_test: pd.DataFrame, y_test: pd.Series) -> dict:
    proba = model.predict_proba(X_test)[:, 1]
    preds = (proba >= 0.5).astype(int)

    cm = confusion_matrix(y_test, preds).tolist()
    metrics = {
        "accuracy": float((preds == y_test).mean()),
        "precision": float(precision_score(y_test, preds, zero_division=0)),
        "recall": float(recall_score(y_test, preds, zero_division=0)),
        "f1": float(f1_score(y_test, preds, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, proba)),
        "pr_auc": float(average_precision_score(y_test, proba)),
        "confusion_matrix": {"tn": cm[0][0], "fp": cm[0][1], "fn": cm[1][0], "tp": cm[1][1]},
        "class_distribution": {
            "positive": float(y_test.mean()),
            "negative": float(1 - y_test.mean()),
        },
    }
    # Calibration: mean predicted probability vs. observed rate, in deciles.
    bins = pd.qcut(proba, q=10, duplicates="drop")
    calibration = (
        pd.DataFrame({"proba": proba, "actual": y_test.values, "bin": bins})
        .groupby("bin", observed=True)
        .agg(mean_predicted=("proba", "mean"), observed_rate=("actual", "mean"), count=("actual", "size"))
        .reset_index(drop=True)
    )
    metrics["calibration"] = calibration.round(4).to_dict("records")
    return metrics


def compute_shap_matrix(clf, X_transformed: np.ndarray, algorithm: str) -> np.ndarray:
    """Returns a (n_samples, n_transformed_features) array of SHAP values for
    the POSITIVE class, regardless of which SHAP explainer/output shape the
    underlying model produces."""
    if algorithm == "logistic_regression":
        background = shap.sample(X_transformed, min(200, X_transformed.shape[0]), random_state=RANDOM_STATE)
        explainer = shap.LinearExplainer(clf, background)
        values = explainer.shap_values(X_transformed)
    else:
        explainer = shap.TreeExplainer(clf)
        values = explainer.shap_values(X_transformed)

    if isinstance(values, list):
        values = values[1] if len(values) > 1 else values[0]
    values = np.asarray(values)
    if values.ndim == 3:
        values = values[:, :, 1]
    return values


def register_model_version(metadata: dict) -> int:
    from app.core.database import SessionLocal
    from app.models.ml import ModelVersion

    with SessionLocal() as db:
        db.query(ModelVersion).filter(ModelVersion.status == "active").update({"status": "archived"})
        model_version = ModelVersion(
            version=metadata["version"],
            algorithm=metadata["algorithm"],
            training_date=datetime.fromisoformat(metadata["training_date"]),
            dataset_version=metadata["dataset_version"],
            feature_count=len(metadata["feature_names"]),
            metrics=metadata["metrics"],
            artifact_path=metadata["artifact_path"],
            status="active",
        )
        db.add(model_version)
        db.commit()
        db.refresh(model_version)
        return model_version.id


def score_all_shipments(pipeline: Pipeline, df: pd.DataFrame, algorithm: str, model_version_id: int) -> int:
    """Runs inference + SHAP for every row in df that matches a shipment_code
    already loaded into MySQL, writes shipment_predictions +
    shipment_risk_factors, and updates the denormalized
    shipments.risk_score/risk_level columns used for fast filtering."""
    from sqlalchemy import select

    from app.analytics.kpi_definitions import risk_level_for_score
    from app.core.database import SessionLocal
    from app.ml import shap_utils
    from app.models.ml import ShipmentPrediction, ShipmentRiskFactor
    from app.models.shipment import Shipment

    preprocessor = pipeline.named_steps["preprocess"]
    clf = pipeline.named_steps["clf"]
    feature_names_out = list(preprocessor.get_feature_names_out())

    X = df[CATEGORICAL_FEATURES + NUMERIC_FEATURES]
    proba_all = pipeline.predict_proba(X)[:, 1]

    scored = 0
    now = datetime.utcnow()

    with SessionLocal() as db:
        code_to_id = dict(db.execute(select(Shipment.shipment_code, Shipment.id)).all())

        for start in range(0, len(df), SHAP_BATCH_SIZE):
            batch = df.iloc[start : start + SHAP_BATCH_SIZE]
            batch_X = X.iloc[start : start + SHAP_BATCH_SIZE]
            batch_proba = proba_all[start : start + SHAP_BATCH_SIZE]

            X_transformed = preprocessor.transform(batch_X)
            if scipy.sparse.issparse(X_transformed):
                X_transformed = X_transformed.toarray()

            shap_matrix = compute_shap_matrix(clf, X_transformed, algorithm)

            for i, (_, row) in enumerate(batch.iterrows()):
                shipment_id = code_to_id.get(row["shipment_code"])
                if shipment_id is None:
                    continue

                probability = float(batch_proba[i])
                risk_score = round(probability * 100, 2)
                risk_level = risk_level_for_score(risk_score)

                prediction = ShipmentPrediction(
                    shipment_id=shipment_id,
                    model_version_id=model_version_id,
                    probability=probability,
                    risk_score=risk_score,
                    risk_level=risk_level,
                    predicted_at=now,
                )
                db.add(prediction)
                db.flush()  # get prediction.id

                row_shap = shap_matrix[i]
                factors = shap_utils.top_risk_factors(
                    row_shap, feature_names_out, CATEGORICAL_FEATURES, row.to_dict(), top_n=TOP_N_RISK_FACTORS
                )
                for f in factors:
                    db.add(
                        ShipmentRiskFactor(
                            prediction_id=prediction.id,
                            feature_name=f["feature_name"],
                            feature_value=f["feature_value"][:255],
                            shap_value=f["shap_value"],
                            direction=f["direction"],
                            rank=f["rank"],
                        )
                    )

                db.query(Shipment).filter(Shipment.id == shipment_id).update(
                    {"risk_score": risk_score, "risk_level": risk_level}
                )
                scored += 1

            db.commit()
            print(f"  scored {min(start + SHAP_BATCH_SIZE, len(df)):,}/{len(df):,} rows...")

    return scored


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=str, default=str(REPO_ROOT / "data/processed/04_features.parquet"))
    parser.add_argument("--dataset-version", type=str, default=None)
    parser.add_argument(
        "--skip-registration",
        action="store_true",
        help="Train/evaluate/save artifact only — skip MySQL model registration and shipment scoring.",
    )
    args = parser.parse_args()

    df = pd.read_parquet(args.input)
    dataset_version = args.dataset_version or f"features-{len(df)}rows-{Path(args.input).stat().st_mtime_ns}"

    train_df, test_df = chronological_split(df, TEST_FRACTION)
    print(f"Train: {len(train_df):,} rows (through {train_df['order_date'].max()})")
    print(f"Test:  {len(test_df):,} rows (from {test_df['order_date'].min()})")

    X_train, y_train = train_df[CATEGORICAL_FEATURES + NUMERIC_FEATURES], train_df[TARGET_COLUMN]
    X_test, y_test = test_df[CATEGORICAL_FEATURES + NUMERIC_FEATURES], test_df[TARGET_COLUMN]

    candidates = {
        "logistic_regression": (
            Pipeline(
                [
                    ("preprocess", build_preprocessor(scale_numeric=True)),
                    ("clf", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE)),
                ]
            )
        ),
        "random_forest": (
            Pipeline(
                [
                    ("preprocess", build_preprocessor(scale_numeric=False)),
                    (
                        "clf",
                        RandomForestClassifier(
                            n_estimators=200, max_depth=10, class_weight="balanced",
                            random_state=RANDOM_STATE, n_jobs=-1,
                        ),
                    ),
                ]
            )
        ),
        "gradient_boosting": (
            Pipeline(
                [
                    ("preprocess", build_preprocessor(scale_numeric=False)),
                    ("clf", GradientBoostingClassifier(n_estimators=200, max_depth=3, random_state=RANDOM_STATE)),
                ]
            )
        ),
        "xgboost": (
            Pipeline(
                [
                    ("preprocess", build_preprocessor(scale_numeric=False)),
                    (
                        "clf",
                        XGBClassifier(
                            n_estimators=300,
                            max_depth=5,
                            learning_rate=0.08,
                            subsample=0.9,
                            colsample_bytree=0.9,
                            eval_metric="logloss",
                            scale_pos_weight=(1 - y_train.mean()) / y_train.mean(),
                            random_state=RANDOM_STATE,
                            n_jobs=-1,
                        ),
                    ),
                ]
            )
        ),
    }

    results = {}
    fitted = {}
    for name, pipeline in candidates.items():
        start = time.perf_counter()
        pipeline.fit(X_train, y_train)
        elapsed = time.perf_counter() - start
        metrics = evaluate(pipeline, X_test, y_test)
        metrics["train_seconds"] = round(elapsed, 2)
        results[name] = metrics
        fitted[name] = pipeline
        print(
            f"[{name}] roc_auc={metrics['roc_auc']:.4f} pr_auc={metrics['pr_auc']:.4f} "
            f"recall={metrics['recall']:.4f} precision={metrics['precision']:.4f} "
            f"f1={metrics['f1']:.4f} ({elapsed:.1f}s)"
        )

    # Selection policy: this is a risk-management system, so recall on the
    # positive (late-delivery) class matters more than raw accuracy — missing
    # a real risk is costlier than a false alarm. We rank by PR-AUC (robust
    # under class imbalance) and prefer XGBoost when it's within 1% of the
    # best PR-AUC, per the platform's stated preference for gradient boosting.
    best_name = max(results, key=lambda n: results[n]["pr_auc"])
    xgb_pr_auc = results["xgboost"]["pr_auc"]
    if xgb_pr_auc >= results[best_name]["pr_auc"] - 0.01:
        best_name = "xgboost"

    print(f"\nSelected model: {best_name}")
    best_pipeline = fitted[best_name]
    best_metrics = results[best_name]

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    # Timestamp-based version id: robust to artifact files being deleted
    # between runs (a sequential counter based on glob() count would collide
    # with an existing file after a deletion — see docs/decisions.md).
    version = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{best_name}"
    artifact_path = ARTIFACTS_DIR / f"model_{version}.joblib"
    joblib.dump(best_pipeline, artifact_path)

    metadata = {
        "version": version,
        "algorithm": best_name,
        "training_date": datetime.utcnow().isoformat(),
        "dataset_version": dataset_version,
        "feature_names": CATEGORICAL_FEATURES + NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "metrics": best_metrics,
        "all_candidate_metrics": {k: {mk: mv for mk, mv in v.items() if mk != "calibration"} for k, v in results.items()},
        "artifact_path": artifact_path.relative_to(REPO_ROOT).as_posix(),
        "train_rows": len(train_df),
        "test_rows": len(test_df),
    }
    metadata_path = ARTIFACTS_DIR / f"model_{version}_meta.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")

    print(f"\nSaved model artifact: {artifact_path}")
    print(f"Saved metadata: {metadata_path}")

    if args.skip_registration:
        return metadata, best_pipeline, df

    model_version_id = register_model_version(metadata)
    print(f"Registered model_versions row id={model_version_id}, status=active")

    # Global feature importance from mean |SHAP| over a sample of the test set.
    preprocessor = best_pipeline.named_steps["preprocess"]
    clf = best_pipeline.named_steps["clf"]
    sample = X_test.sample(min(1000, len(X_test)), random_state=RANDOM_STATE)
    X_sample_transformed = preprocessor.transform(sample)
    if scipy.sparse.issparse(X_sample_transformed):
        X_sample_transformed = X_sample_transformed.toarray()
    shap_sample = compute_shap_matrix(clf, X_sample_transformed, best_name)
    feature_names_out = list(preprocessor.get_feature_names_out())

    from app.ml import shap_utils

    importance: dict[str, float] = {}
    for j, name in enumerate(feature_names_out):
        orig = shap_utils.original_feature_name(name, CATEGORICAL_FEATURES)
        importance[orig] = importance.get(orig, 0.0) + float(np.abs(shap_sample[:, j]).mean())
    importance = dict(sorted(importance.items(), key=lambda kv: kv[1], reverse=True))

    global_importance_path = ARTIFACTS_DIR / f"model_{version}_global_importance.json"
    global_importance_path.write_text(json.dumps(importance, indent=2), encoding="utf-8")
    print(f"Saved global feature importance: {global_importance_path}")

    print("\nScoring all shipments in the database (predictions + SHAP risk factors)...")
    scored = score_all_shipments(best_pipeline, df, best_name, model_version_id)
    print(f"Scored {scored:,} shipments.")

    return metadata, best_pipeline, df


if __name__ == "__main__":
    main()
