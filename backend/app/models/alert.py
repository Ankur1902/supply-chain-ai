from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Alert(Base, TimestampMixin):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_severity_status", "severity", "status"),
        Index("ix_alerts_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # severity: low | medium | high | critical
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # entity_type: shipment | supplier | route | system
    entity_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    # status: open | acknowledged | resolved

    acknowledged_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
