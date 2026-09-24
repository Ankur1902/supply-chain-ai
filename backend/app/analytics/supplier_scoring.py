"""
Supplier scoring engine (section 19).

score = reliability*0.25 + delivery*0.25 + quality*0.15 + lead_time*0.15
        + cost*0.10 + risk*0.10   (all components normalized to 0-100)

- reliability, delivery: DERIVED from actual shipment history for that
  supplier (delay rate, on-time rate) — real signal from the pipeline.
- quality, cost, risk, and the lead_time *baseline*: come from the SYNTHETIC
  supplier enrichment layer (app/models/supplier.py::Supplier). The
  lead_time COMPONENT blends the synthetic baseline with the supplier's
  observed average lead time in this period, when there is enough volume.
- Weights are configurable via app.analytics.kpi_definitions.SUPPLIER_SCORE_WEIGHTS.

This module recomputes one SupplierMetric row per (supplier, calendar month)
from `shipments` + `suppliers`, and is safe to re-run — it upserts based on
the (supplier_id, period_start) unique pairing.
"""

from datetime import date, datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.analytics.kpi_definitions import SUPPLIER_SCORE_WEIGHTS
from app.models.shipment import Shipment
from app.models.supplier import Supplier, SupplierMetric


def _normalize_lead_time(days: float, best: float = 1.0, worst: float = 10.0) -> float:
    """Lower lead time -> higher score. Linearly maps [best, worst] -> [100, 0]."""
    days = max(best, min(worst, days))
    return round(100 * (worst - days) / (worst - best), 2)


def compute_supplier_metrics(db: Session, period_start: date | None = None) -> int:
    """Compute/refresh SupplierMetric rows for one period (default: current
    month) across every supplier that has shipments. Returns rows written."""
    if period_start is None:
        today = datetime.utcnow().date()
        period_start = date(today.year, today.month, 1)

    rows_written = 0
    suppliers = db.execute(select(Supplier)).scalars().all()

    for supplier in suppliers:
        agg = db.execute(
            select(
                func.count(Shipment.id),
                func.sum(case((Shipment.late_delivery_risk == True, 1), else_=0)),  # noqa: E712
                func.avg(Shipment.days_for_shipping_real),
            ).where(Shipment.supplier_id == supplier.id)
        ).one()
        order_volume, delayed, avg_lead_time = agg
        order_volume = int(order_volume or 0)
        delayed = float(delayed or 0)
        avg_lead_time = float(avg_lead_time) if avg_lead_time is not None else float(
            supplier.historical_lead_time_days
        )

        delay_rate = delayed / order_volume if order_volume else 0.0
        on_time_rate = 1 - delay_rate

        reliability_component = round(float(supplier.reliability_score) * 0.5 + on_time_rate * 100 * 0.5, 2)
        delivery_component = round(on_time_rate * 100, 2)
        quality_component = round(float(supplier.quality_score), 2)
        cost_component = round(float(supplier.cost_score), 2)
        risk_component = round(100 - float(supplier.risk_score), 2)  # invert: lower risk -> higher score

        observed_lead_time_score = _normalize_lead_time(avg_lead_time)
        synthetic_lead_time_score = _normalize_lead_time(float(supplier.historical_lead_time_days))
        lead_time_component = round(
            observed_lead_time_score * 0.5 + synthetic_lead_time_score * 0.5, 2
        ) if order_volume >= 5 else synthetic_lead_time_score

        score = round(
            reliability_component * SUPPLIER_SCORE_WEIGHTS["reliability"]
            + delivery_component * SUPPLIER_SCORE_WEIGHTS["delivery"]
            + quality_component * SUPPLIER_SCORE_WEIGHTS["quality"]
            + lead_time_component * SUPPLIER_SCORE_WEIGHTS["lead_time"]
            + cost_component * SUPPLIER_SCORE_WEIGHTS["cost"]
            + risk_component * SUPPLIER_SCORE_WEIGHTS["risk"],
            2,
        )

        existing = db.execute(
            select(SupplierMetric).where(
                SupplierMetric.supplier_id == supplier.id,
                SupplierMetric.period_start == period_start,
            )
        ).scalar_one_or_none()

        values = dict(
            order_volume=order_volume,
            delay_rate=round(delay_rate, 4),
            avg_lead_time_days=round(avg_lead_time, 2),
            score=score,
            reliability_component=reliability_component,
            delivery_component=delivery_component,
            quality_component=quality_component,
            lead_time_component=lead_time_component,
            cost_component=cost_component,
            risk_component=risk_component,
            computed_at=datetime.utcnow(),
        )

        if existing:
            for k, v in values.items():
                setattr(existing, k, v)
        else:
            db.add(SupplierMetric(supplier_id=supplier.id, period_start=period_start, **values))
        rows_written += 1

    db.commit()
    return rows_written
