from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.supplier import Supplier, SupplierMetric


def _latest_metric_subquery(db: Session):
    return (
        select(
            SupplierMetric.supplier_id,
            func.max(SupplierMetric.period_start).label("max_period"),
        )
        .group_by(SupplierMetric.supplier_id)
        .subquery()
    )


def list_suppliers(
    db: Session,
    region: str | None = None,
    product_category: str | None = None,
    page: int = 1,
    page_size: int = 25,
    sort_by: str = "score",
) -> tuple[list[tuple[Supplier, SupplierMetric | None]], int]:
    latest = _latest_metric_subquery(db)
    query = (
        select(Supplier, SupplierMetric)
        .outerjoin(latest, latest.c.supplier_id == Supplier.id)
        .outerjoin(
            SupplierMetric,
            (SupplierMetric.supplier_id == latest.c.supplier_id)
            & (SupplierMetric.period_start == latest.c.max_period),
        )
    )
    if region:
        query = query.filter(Supplier.supplier_region == region)
    if product_category:
        query = query.filter(Supplier.product_category == product_category)

    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar_one()

    # MySQL has no native NULLS LAST syntax (unlike Postgres), so we emulate
    # it with an explicit "is this null" tiebreaker column sorted first.
    if sort_by == "score":
        query = query.order_by(SupplierMetric.score.is_(None), SupplierMetric.score.desc())
    elif sort_by == "delay_rate":
        query = query.order_by(SupplierMetric.delay_rate.is_(None), SupplierMetric.delay_rate.desc())
    else:
        query = query.order_by(Supplier.supplier_name.asc())

    query = query.limit(page_size).offset((page - 1) * page_size)
    rows = db.execute(query).all()
    return [(r[0], r[1]) for r in rows], total


def get_supplier_with_latest_metric(db: Session, supplier_id: int) -> tuple[Supplier | None, SupplierMetric | None]:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        return None, None
    metric = db.execute(
        select(SupplierMetric)
        .where(SupplierMetric.supplier_id == supplier_id)
        .order_by(SupplierMetric.period_start.desc())
        .limit(1)
    ).scalar_one_or_none()
    return supplier, metric


def get_supplier_trend(db: Session, supplier_id: int, limit: int = 12) -> list[SupplierMetric]:
    rows = db.execute(
        select(SupplierMetric)
        .where(SupplierMetric.supplier_id == supplier_id)
        .order_by(SupplierMetric.period_start.desc())
        .limit(limit)
    ).scalars().all()
    return list(reversed(rows))
