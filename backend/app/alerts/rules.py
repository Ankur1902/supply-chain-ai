"""
Deterministic alert rules (section 28). Each rule inspects real aggregates
and writes an `Alert` row when a threshold is crossed. No LLM involvement —
alerts must be reproducible and auditable. Intended to run periodically
(see scripts/run_pipeline.py or a scheduled job); safe to re-run since it
skips creating a duplicate open alert for the same entity+title.
"""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.shipment import Shipment
from app.models.supplier import Supplier, SupplierMetric

CRITICAL_RISK_ALERT_THRESHOLD = 85.0
HIGH_SUPPLIER_RISK_THRESHOLD = 70.0
SUPPLIER_SCORE_DETERIORATION_THRESHOLD = 10.0  # point drop month-over-month
DELAY_SPIKE_MULTIPLE = 1.5  # current period vs trailing average


def _alert_exists(db: Session, entity_type: str, entity_id: int | None, title: str) -> bool:
    return (
        db.execute(
            select(Alert.id).where(
                Alert.entity_type == entity_type,
                Alert.entity_id == entity_id,
                Alert.title == title,
                Alert.status != "resolved",
            )
        ).first()
        is not None
    )


def check_critical_shipment_risk(db: Session) -> list[Alert]:
    created = []
    shipments = db.execute(
        select(Shipment).where(Shipment.risk_score >= CRITICAL_RISK_ALERT_THRESHOLD)
    ).scalars().all()
    for s in shipments:
        title = f"Critical delay risk: {s.shipment_code}"
        if _alert_exists(db, "shipment", s.id, title):
            continue
        alert = Alert(
            severity="critical",
            title=title,
            description=(
                f"Shipment {s.shipment_code} has a modeled risk score of {s.risk_score}, "
                f"above the {CRITICAL_RISK_ALERT_THRESHOLD} critical threshold."
            ),
            entity_type="shipment",
            entity_id=s.id,
            recommended_action="Review shipment and consider expediting or notifying the customer.",
            status="open",
        )
        db.add(alert)
        created.append(alert)
    return created


def check_high_supplier_risk(db: Session) -> list[Alert]:
    created = []
    suppliers = db.execute(
        select(Supplier).where(Supplier.risk_score >= HIGH_SUPPLIER_RISK_THRESHOLD)
    ).scalars().all()
    for sup in suppliers:
        title = f"High supplier risk: {sup.supplier_name}"
        if _alert_exists(db, "supplier", sup.id, title):
            continue
        alert = Alert(
            severity="high",
            title=title,
            description=(
                f"Supplier {sup.supplier_name} has a risk score of {sup.risk_score} "
                f"(synthetic enrichment layer), above the {HIGH_SUPPLIER_RISK_THRESHOLD} threshold."
            ),
            entity_type="supplier",
            entity_id=sup.id,
            recommended_action="Evaluate alternate suppliers for this category/region.",
            status="open",
        )
        db.add(alert)
        created.append(alert)
    return created


def check_supplier_deterioration(db: Session) -> list[Alert]:
    created = []
    suppliers = db.execute(select(Supplier)).scalars().all()
    for sup in suppliers:
        metrics = db.execute(
            select(SupplierMetric)
            .where(SupplierMetric.supplier_id == sup.id)
            .order_by(SupplierMetric.period_start.desc())
            .limit(2)
        ).scalars().all()
        if len(metrics) < 2:
            continue
        latest, previous = metrics[0], metrics[1]
        drop = float(previous.score) - float(latest.score)
        if drop >= SUPPLIER_SCORE_DETERIORATION_THRESHOLD:
            title = f"Supplier performance deteriorating: {sup.supplier_name}"
            if _alert_exists(db, "supplier", sup.id, title):
                continue
            alert = Alert(
                severity="medium",
                title=title,
                description=(
                    f"{sup.supplier_name}'s score dropped {drop:.1f} points "
                    f"({previous.score} -> {latest.score}) month-over-month."
                ),
                entity_type="supplier",
                entity_id=sup.id,
                recommended_action="Investigate recent order performance and lead times.",
                status="open",
            )
            db.add(alert)
            created.append(alert)
    return created


def check_delay_spike(db: Session, lookback_days: int = 30) -> list[Alert]:
    """Compares the most recent week's delay rate to the trailing lookback
    window's average delay rate; flags a system-level alert on a spike."""
    now = datetime.utcnow()
    recent_window_start = now - timedelta(days=7)
    baseline_window_start = now - timedelta(days=lookback_days)

    def _rate(start, end) -> tuple[int, float]:
        row = db.execute(
            select(
                func.count(Shipment.id),
                func.avg(Shipment.late_delivery_risk),
            ).where(Shipment.order_date >= start, Shipment.order_date < end)
        ).one()
        total = row[0] or 0
        rate = float(row[1]) if row[1] is not None else 0.0
        return total, rate

    recent_total, recent_rate = _rate(recent_window_start, now)
    baseline_total, baseline_rate = _rate(baseline_window_start, recent_window_start)

    created = []
    if baseline_total >= 20 and recent_total >= 5 and baseline_rate > 0:
        if recent_rate >= baseline_rate * DELAY_SPIKE_MULTIPLE:
            title = "Unusual delay spike detected"
            if not _alert_exists(db, "system", None, title):
                alert = Alert(
                    severity="high",
                    title=title,
                    description=(
                        f"Delay rate over the last 7 days is {recent_rate:.1%}, vs. a "
                        f"{lookback_days}-day baseline of {baseline_rate:.1%}."
                    ),
                    entity_type="system",
                    entity_id=None,
                    recommended_action="Review recent shipments for a common route/supplier/mode cause.",
                    status="open",
                )
                db.add(alert)
                created.append(alert)
    return created


def run_all_alert_checks(db: Session) -> int:
    created = []
    created += check_critical_shipment_risk(db)
    created += check_high_supplier_risk(db)
    created += check_supplier_deterioration(db)
    created += check_delay_spike(db)
    db.commit()
    return len(created)
