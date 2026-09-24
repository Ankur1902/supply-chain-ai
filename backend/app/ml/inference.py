"""
Online inference glue: loads the ACTIVE model artifact (as recorded in the
`model_versions` table) and exposes predict() for a single feature row.

The artifact is a full sklearn Pipeline (ColumnTransformer + classifier)
saved by ml/training/train.py — inference never reimplements encoding
logic, it just calls pipeline.predict_proba(). This is what keeps
training/serving consistent (no train/serve skew from divergent code paths).

Fails safely (section 39): if no active model is registered, or the artifact
file is missing/incompatible, predict() raises ModelUnavailableError rather
than crashing the request — callers (API routes, the scenario simulator, the
AI copilot) turn this into a clear "prediction unavailable" response instead
of a 500.
"""

import warnings
from dataclasses import dataclass
from functools import lru_cache

import joblib
import numpy as np
import scipy.sparse
from sklearn.exceptions import InconsistentVersionWarning
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.kpi_definitions import risk_level_for_score
from app.core.config import get_settings
from app.ml import shap_utils
from app.models.ml import ModelVersion

settings = get_settings()
TOP_N_RISK_FACTORS = 5


class ModelUnavailableError(Exception):
    pass


@dataclass
class RiskFactorResult:
    feature_name: str
    feature_value: str
    shap_value: float
    direction: str
    rank: int


@dataclass
class PredictionResult:
    probability: float
    risk_score: float
    risk_level: str
    model_version: str
    risk_factors: list[RiskFactorResult]


def get_active_model_version(db: Session) -> ModelVersion | None:
    return db.execute(select(ModelVersion).where(ModelVersion.status == "active")).scalar_one_or_none()


@lru_cache(maxsize=4)
def _load_pipeline_cached(artifact_path: str, algorithm: str):
    full_path = settings.resolve_path(artifact_path)
    if not full_path.exists():
        raise ModelUnavailableError(f"Model artifact not found at {full_path}")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        pipeline = joblib.load(full_path)
    # An artifact pickled by a different scikit-learn than the one running here
    # loads "successfully" but can fail later with confusing AttributeErrors.
    # Fail early with an actionable message instead.
    for w in caught:
        if isinstance(w.message, InconsistentVersionWarning):
            raise ModelUnavailableError(
                f"Model artifact {full_path.name} was trained with scikit-learn "
                f"{w.message.original_sklearn_version} but this environment has "
                f"{w.message.current_sklearn_version}. Retrain with the project's pinned "
                "environment (backend/.venv or the backend container)."
            )
    return pipeline


def _compute_shap(clf, X_transformed: np.ndarray, algorithm: str) -> np.ndarray:
    import shap

    if algorithm == "logistic_regression":
        explainer = shap.LinearExplainer(clf, X_transformed)
    else:
        explainer = shap.TreeExplainer(clf)
    values = explainer.shap_values(X_transformed)
    if isinstance(values, list):
        values = values[1] if len(values) > 1 else values[0]
    values = np.asarray(values)
    if values.ndim == 3:
        values = values[:, :, 1]
    return values


def predict(db: Session, feature_row: dict) -> PredictionResult:
    """feature_row must contain every key in
    CATEGORICAL_FEATURES + NUMERIC_FEATURES (see ml/features/feature_spec.py)."""
    model_version = get_active_model_version(db)
    if model_version is None:
        raise ModelUnavailableError("No active model is registered. Run ml/training/train.py.")

    pipeline = _load_pipeline_cached(model_version.artifact_path, model_version.algorithm)
    preprocessor = pipeline.named_steps["preprocess"]
    clf = pipeline.named_steps["clf"]

    import pandas as pd

    categorical_features = list(preprocessor.transformers[0][2])
    all_features = categorical_features + list(preprocessor.transformers[1][2])
    X = pd.DataFrame([{k: feature_row.get(k) for k in all_features}])

    probability = float(pipeline.predict_proba(X)[:, 1][0])
    risk_score = round(probability * 100, 2)
    risk_level = risk_level_for_score(risk_score)

    X_transformed = preprocessor.transform(X)
    if scipy.sparse.issparse(X_transformed):
        X_transformed = X_transformed.toarray()

    shap_values = _compute_shap(clf, X_transformed, model_version.algorithm)[0]
    feature_names_out = list(preprocessor.get_feature_names_out())

    factors = shap_utils.top_risk_factors(
        shap_values, feature_names_out, categorical_features, feature_row, top_n=TOP_N_RISK_FACTORS
    )
    risk_factors = [
        RiskFactorResult(
            feature_name=f["feature_name"],
            feature_value=f["feature_value"],
            shap_value=f["shap_value"],
            direction=f["direction"],
            rank=f["rank"],
        )
        for f in factors
    ]

    return PredictionResult(
        probability=probability,
        risk_score=risk_score,
        risk_level=risk_level,
        model_version=model_version.version,
        risk_factors=risk_factors,
    )
