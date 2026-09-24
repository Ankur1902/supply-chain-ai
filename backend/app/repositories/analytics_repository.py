from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.shipment import Product, Shipment


class AnalyticsFilters:
    def __init__(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        region: str | None = None,
        market: str | None = None,
        shipping_mode: str | None = None,
        supplier_id: int | None = None,
        product_category: str | None = None,
    ):
        self.date_from = date_from
        self.date_to = date_to
        self.region = region
        self.market = market
        self.shipping_mode = shipping_mode
        self.supplier_id = supplier_id
        self.product_category = product_category


def apply_filters(query, f: AnalyticsFilters, needs_product_join: bool = False):
    if needs_product_join:
        query = query.join(Product, Shipment.product_id == Product.id)
    if f.date_from:
        query = query.filter(Shipment.order_date >= f.date_from)
    if f.date_to:
        query = query.filter(Shipment.order_date <= f.date_to)
    if f.region:
        query = query.filter(Shipment.destination_region == f.region)
    if f.market:
        query = query.filter(Shipment.origin_market == f.market)
    if f.shipping_mode:
        query = query.filter(Shipment.shipping_mode == f.shipping_mode)
    if f.supplier_id:
        query = query.filter(Shipment.supplier_id == f.supplier_id)
    if f.product_category:
        query = query.filter(Product.category_name == f.product_category)
    return query


def get_dashboard_kpis(db: Session, f: AnalyticsFilters) -> dict:
    query = select(
        func.count(Shipment.id).label("total"),
        func.sum(case((Shipment.late_delivery_risk == True, 1), else_=0)).label("delayed"),  # noqa: E712
        func.sum(case((Shipment.risk_level.in_(["HIGH", "CRITICAL"]), 1), else_=0)).label("at_risk"),
        func.sum(case((Shipment.risk_level == "CRITICAL", 1), else_=0)).label("critical"),
        func.avg(Shipment.days_for_shipping_real).label("avg_delivery_days"),
        func.avg(Shipment.scheduled_shipping_days).label("avg_scheduled_days"),
        func.sum(
            case((Shipment.risk_level.in_(["HIGH", "CRITICAL"]), Shipment.sales), else_=0)
        ).label("value_at_risk"),
        func.sum(
            case(
                (Shipment.risk_level.in_(["HIGH", "CRITICAL"]), Shipment.order_profit_per_order),
                else_=0,
            )
        ).label("profit_at_risk"),
    )
    query = apply_filters(query, f, needs_product_join=bool(f.product_category))
    row = db.execute(query).one()

    total = row.total or 0
    return {
        "total_shipments": total,
        "at_risk_shipments": row.at_risk or 0,
        "critical_shipments": row.critical or 0,
        "delay_rate": round((row.delayed or 0) / total, 4) if total else 0.0,
        "at_risk_rate": round((row.at_risk or 0) / total, 4) if total else 0.0,
        "critical_rate": round((row.critical or 0) / total, 4) if total else 0.0,
        "average_delivery_time": round(float(row.avg_delivery_days or 0), 2),
        "average_scheduled_days": round(float(row.avg_scheduled_days or 0), 2),
        "estimated_value_at_risk": round(float(row.value_at_risk or 0), 2),
        "profit_at_risk": round(float(row.profit_at_risk or 0), 2),
    }


def get_delay_trend(db: Session, f: AnalyticsFilters) -> list[dict]:
    period = func.date_format(Shipment.order_date, "%Y-%m-01").label("period")
    query = select(
        period,
        func.count(Shipment.id).label("total"),
        func.sum(case((Shipment.late_delivery_risk == True, 1), else_=0)).label("delayed"),  # noqa: E712
    ).group_by(period).order_by(period)
    query = apply_filters(query, f, needs_product_join=bool(f.product_category))
    rows = db.execute(query).all()
    return [
        {
            "period": r.period,
            "total": r.total,
            "delayed": r.delayed,
            "delay_rate": round((r.delayed or 0) / r.total, 4) if r.total else 0.0,
        }
        for r in rows
    ]


def get_risk_distribution(db: Session, f: AnalyticsFilters) -> list[dict]:
    query = select(
        func.coalesce(Shipment.risk_level, "UNSCORED").label("risk_level"),
        func.count(Shipment.id).label("count"),
    ).group_by(Shipment.risk_level)
    query = apply_filters(query, f, needs_product_join=bool(f.product_category))
    rows = db.execute(query).all()
    return [{"risk_level": r.risk_level, "count": r.count} for r in rows]


def get_delay_by_dimension(db: Session, f: AnalyticsFilters, dimension: str) -> list[dict]:
    column_map = {
        "shipping_mode": Shipment.shipping_mode,
        "region": Shipment.destination_region,
        "market": Shipment.origin_market,
        "product_category": Product.category_name,
    }
    col = column_map[dimension]
    query = select(
        col.label("dimension"),
        func.count(Shipment.id).label("total"),
        func.sum(case((Shipment.late_delivery_risk == True, 1), else_=0)).label("delayed"),  # noqa: E712
        func.avg(Shipment.days_for_shipping_real).label("avg_delivery_days"),
    ).group_by(col).order_by(func.count(Shipment.id).desc())
    query = apply_filters(query, f, needs_product_join=(dimension == "product_category" or bool(f.product_category)))
    rows = db.execute(query).all()
    return [
        {
            "dimension": r.dimension,
            "total": r.total,
            "delayed": r.delayed,
            "delay_rate": round((r.delayed or 0) / r.total, 4) if r.total else 0.0,
            "avg_delivery_days": round(float(r.avg_delivery_days or 0), 2),
        }
        for r in rows
    ]


def get_supplier_health_summary(db: Session) -> dict:
    from app.models.supplier import SupplierMetric

    latest_period = db.execute(select(func.max(SupplierMetric.period_start))).scalar_one_or_none()
    if latest_period is None:
        return {"avg_score": None, "supplier_count": 0}
    row = db.execute(
        select(func.avg(SupplierMetric.score), func.count(SupplierMetric.id)).where(
            SupplierMetric.period_start == latest_period
        )
    ).one()
    return {"avg_score": round(float(row[0]), 2) if row[0] is not None else None, "supplier_count": row[1]}
