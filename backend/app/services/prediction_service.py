from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.ml import ShipmentPrediction
from app.schemas.shipment import PredictionOut, RiskFactorOut


def get_latest_prediction(db: Session, shipment_id: int) -> PredictionOut | None:
    query = (
        select(ShipmentPrediction)
        .options(joinedload(ShipmentPrediction.risk_factors), joinedload(ShipmentPrediction.model_version))
        .where(ShipmentPrediction.shipment_id == shipment_id)
        .order_by(ShipmentPrediction.predicted_at.desc())
        .limit(1)
    )
    prediction = db.execute(query).unique().scalar_one_or_none()
    if prediction is None:
        return None

    factors = sorted(prediction.risk_factors, key=lambda f: f.rank)
    return PredictionOut(
        probability=float(prediction.probability),
        risk_score=float(prediction.risk_score),
        risk_level=prediction.risk_level,
        model_version=prediction.model_version.version,
        predicted_at=prediction.predicted_at,
        risk_factors=[
            RiskFactorOut(
                feature_name=f.feature_name,
                feature_value=f.feature_value,
                shap_value=float(f.shap_value),
                direction=f.direction,
                rank=f.rank,
            )
            for f in factors
        ],
    )
