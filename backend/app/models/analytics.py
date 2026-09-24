from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, DECIMAL, ForeignKey, Index, JSON, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class RootCause(Base, TimestampMixin):
    """
    DERIVED — deterministic root-cause analytics output. Computed by
    app/analytics/root_cause.py from actual aggregates (never invented by an
    LLM). `entity_type` is 'shipment' or 'aggregate'; for 'aggregate',
    entity_id is null and `scope` describes the query (e.g. region=LATAM).
    """

    __tablename__ = "root_causes"
    __table_args__ = (Index("ix_root_causes_entity", "entity_type", "entity_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    scope: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    factor_name: Mapped[str] = mapped_column(String(100), nullable=False)
    contribution_pct: Mapped[float] = mapped_column(DECIMAL(6, 2), nullable=False)
    rank: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    supporting_metric: Mapped[str] = mapped_column(Text, nullable=False, default="")

    computed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Recommendation(Base, TimestampMixin):
    """
    AI-GENERATED recommendation, grounded in structured tool outputs
    (see app/ai/tools.py). `confidence` is a model-estimated probability,
    never a certainty claim. `ai_generated` is always True for rows written
    by app/ai/recommendations.py — kept explicit so the UI can badge it.
    """

    __tablename__ = "recommendations"
    __table_args__ = (Index("ix_recommendations_shipment", "shipment_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shipment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    recommendation_text: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    expected_impact: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(DECIMAL(4, 3), nullable=False)
    supporting_metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
