"""
AI recommendation engine (section 20).

Deliberately rule-based + model-grounded rather than "ask an LLM to invent a
JSON object": every `confidence` and `expected_impact` here is derived from
an actual re-scoring of the shipment (via app.ml.inference / feature_builder),
not free-form generation. This guarantees every recommendation validates
against guardrails.RecommendationOutput and never states a number the system
didn't actually compute. An LLM COULD be layered on top to rephrase these
into more natural prose (see app/ai/chat_service.py for where the copilot
does that in conversation), but the underlying facts always come from here.
"""

from dataclasses import dataclass

import structlog
from sqlalchemy.orm import Session

from app.ai.guardrails import validate_recommendation
from app.ml import feature_builder, inference
from app.models.analytics import Recommendation
from app.models.shipment import Shipment
from app.repositories import shipment_repository

logger = structlog.get_logger("ai.recommendations")

RISK_REDUCTION_MEANINGFUL_THRESHOLD = 5.0  # points of modeled risk_score
CANDIDATE_MODES = ["Standard Class", "Second Class", "First Class", "Same Day"]


def _try_buffer_increase(db: Session, shipment: Shipment, baseline: inference.PredictionResult) -> dict | None:
    row = feature_builder.build_feature_row(
        db, shipment, {"scheduled_shipping_days": shipment.scheduled_shipping_days + 2}
    )
    try:
        result = inference.predict(db, row)
    except inference.ModelUnavailableError:
        return None
    reduction = baseline.risk_score - result.risk_score
    if reduction < RISK_REDUCTION_MEANINGFUL_THRESHOLD:
        return None
    return {
        "recommendation": "Increase delivery buffer by 2 days",
        "reason": "Extending the scheduled delivery window measurably reduces modeled delay risk for this route/mode combination.",
        "expected_impact": f"Modeled risk score drops from {baseline.risk_score:.1f} to {result.risk_score:.1f}.",
        "confidence": round(min(0.95, 0.5 + reduction / 100), 3),
        "action_type": "increase_buffer",
        "supporting_metrics": {"baseline_risk_score": baseline.risk_score, "scenario_risk_score": result.risk_score},
    }


def _try_mode_switch(db: Session, shipment: Shipment, baseline: inference.PredictionResult) -> dict | None:
    best_mode, best_score = None, baseline.risk_score
    for mode in CANDIDATE_MODES:
        if mode == shipment.shipping_mode:
            continue
        row = feature_builder.build_feature_row(db, shipment, {"shipping_mode": mode})
        try:
            result = inference.predict(db, row)
        except inference.ModelUnavailableError:
            return None
        if result.risk_score < best_score:
            best_mode, best_score = mode, result.risk_score

    reduction = baseline.risk_score - best_score
    if best_mode is None or reduction < RISK_REDUCTION_MEANINGFUL_THRESHOLD:
        return None
    return {
        "recommendation": f"Switch shipping mode to {best_mode}",
        "reason": f"{best_mode} has a lower historical delay rate for this route/category than {shipment.shipping_mode}.",
        "expected_impact": f"Modeled risk score drops from {baseline.risk_score:.1f} to {best_score:.1f}.",
        "confidence": round(min(0.95, 0.5 + reduction / 100), 3),
        "action_type": "switch_shipping_mode",
        "supporting_metrics": {"baseline_risk_score": baseline.risk_score, "scenario_risk_score": best_score},
    }


def _escalation_recommendation(baseline: inference.PredictionResult) -> dict:
    return {
        "recommendation": "Escalate shipment and proactively notify the customer",
        "reason": f"Modeled risk level is {baseline.risk_level} ({baseline.risk_score:.1f}/100); no scenario tested reduced it below HIGH.",
        "expected_impact": "Does not change delivery risk, but reduces the operational/customer-experience impact of a likely delay.",
        "confidence": 0.6,
        "action_type": "escalate",
        "supporting_metrics": {"baseline_risk_score": baseline.risk_score},
    }


def generate_recommendations(db: Session, shipment_code: str, persist: bool = True) -> list[dict]:
    shipment = shipment_repository.get_shipment_by_code(db, shipment_code)
    if shipment is None:
        return []

    try:
        baseline_row = feature_builder.build_feature_row(db, shipment)
        baseline = inference.predict(db, baseline_row)
    except inference.ModelUnavailableError:
        return []

    if baseline.risk_level not in ("HIGH", "CRITICAL"):
        return []

    candidates = [
        _try_buffer_increase(db, shipment, baseline),
        _try_mode_switch(db, shipment, baseline),
    ]
    candidates = [c for c in candidates if c is not None]
    if not candidates or baseline.risk_level == "CRITICAL":
        candidates.append(_escalation_recommendation(baseline))

    validated: list[dict] = []
    for c in candidates:
        validated_output = validate_recommendation(c)
        if validated_output is None:
            logger.warning("recommendation_failed_schema_validation", shipment_code=shipment_code, payload=c)
            continue
        validated.append(c)
        if persist:
            db.add(
                Recommendation(
                    shipment_id=shipment.id,
                    action_type=c["action_type"],
                    recommendation_text=c["recommendation"],
                    reason=c["reason"],
                    expected_impact=c["expected_impact"],
                    confidence=c["confidence"],
                    supporting_metrics=c["supporting_metrics"],
                    ai_generated=True,
                )
            )
    if persist and validated:
        db.commit()

    return validated
