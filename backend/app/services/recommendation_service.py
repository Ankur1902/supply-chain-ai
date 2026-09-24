from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analytics import Recommendation
from app.schemas.shipment import RecommendationOut


def get_recommendations_for_shipment(db: Session, shipment_id: int) -> list[RecommendationOut]:
    query = (
        select(Recommendation)
        .where(Recommendation.shipment_id == shipment_id)
        .order_by(Recommendation.created_at.desc())
    )
    rows = db.execute(query).scalars().all()
    return [
        RecommendationOut(
            id=r.id,
            action_type=r.action_type,
            recommendation_text=r.recommendation_text,
            reason=r.reason,
            expected_impact=r.expected_impact,
            confidence=float(r.confidence),
            ai_generated=r.ai_generated,
        )
        for r in rows
    ]
