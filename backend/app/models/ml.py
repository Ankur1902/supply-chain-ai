from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    DECIMAL,
    ForeignKey,
    Index,
    Integer,
    JSON,
    SmallInteger,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ModelVersion(Base, TimestampMixin):
    """Model registry — one row per trained model artifact."""

    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    algorithm: Mapped[str] = mapped_column(String(50), nullable=False)
    training_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(50), nullable=False)
    feature_count: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    artifact_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="archived", index=True)
    # status: 'active' | 'archived'

    predictions: Mapped[list["ShipmentPrediction"]] = relationship(back_populates="model_version")


class ShipmentPrediction(Base, TimestampMixin):
    """PREDICTED — one row per (shipment, model_version) inference."""

    __tablename__ = "shipment_predictions"
    __table_args__ = (
        Index("ix_shipment_predictions_shipment_model", "shipment_id", "model_version_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shipment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_version_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("model_versions.id"), nullable=False, index=True
    )

    probability: Mapped[float] = mapped_column(DECIMAL(6, 5), nullable=False)
    risk_score: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    model_version: Mapped["ModelVersion"] = relationship(back_populates="predictions")
    risk_factors: Mapped[list["ShipmentRiskFactor"]] = relationship(
        back_populates="prediction", cascade="all, delete-orphan"
    )


class ShipmentRiskFactor(Base):
    """
    SHAP-derived explanation rows for one prediction. `shap_value` is the raw
    signed contribution; `direction` is 'positive' (increases risk) or
    'negative' (decreases risk); `rank` orders by |shap_value| descending.
    """

    __tablename__ = "shipment_risk_factors"
    __table_args__ = (Index("ix_risk_factors_prediction_rank", "prediction_id", "rank"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    prediction_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shipment_predictions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature_name: Mapped[str] = mapped_column(String(100), nullable=False)
    feature_value: Mapped[str] = mapped_column(String(255), nullable=False)
    shap_value: Mapped[float] = mapped_column(DECIMAL(10, 6), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    rank: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    prediction: Mapped["ShipmentPrediction"] = relationship(back_populates="risk_factors")
