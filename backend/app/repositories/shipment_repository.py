from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.shipment import Order, Product, Shipment
from app.models.supplier import Supplier
from app.schemas.shipment import ShipmentFilterParams

ALLOWED_SORT_COLUMNS = {
    "order_date": Shipment.order_date,
    "risk_score": Shipment.risk_score,
    "sales": Shipment.sales,
    "scheduled_shipping_days": Shipment.scheduled_shipping_days,
}


def _apply_filters(query, filters: ShipmentFilterParams):
    if filters.region:
        query = query.filter(Shipment.destination_region == filters.region)
    if filters.market:
        query = query.filter(Shipment.origin_market == filters.market)
    if filters.shipping_mode:
        query = query.filter(Shipment.shipping_mode == filters.shipping_mode)
    if filters.supplier_id:
        query = query.filter(Shipment.supplier_id == filters.supplier_id)
    if filters.product_category:
        query = query.filter(Product.category_name == filters.product_category)
    if filters.risk_level:
        query = query.filter(Shipment.risk_level == filters.risk_level)
    if filters.status:
        query = query.filter(Shipment.status == filters.status)
    if filters.date_from:
        query = query.filter(Shipment.order_date >= filters.date_from)
    if filters.date_to:
        query = query.filter(Shipment.order_date <= filters.date_to)
    if filters.search:
        like = f"%{filters.search}%"
        query = query.filter(
            or_(Shipment.shipment_code.ilike(like), Product.name.ilike(like))
        )
    return query


def list_shipments(db: Session, filters: ShipmentFilterParams) -> tuple[list[Shipment], int]:
    base_query = (
        select(Shipment)
        .join(Product, Shipment.product_id == Product.id)
        .options(joinedload(Shipment.product), joinedload(Shipment.supplier))
    )
    base_query = _apply_filters(base_query, filters)

    count_query = select(func.count()).select_from(base_query.subquery())
    total = db.execute(count_query).scalar_one()

    sort_col = ALLOWED_SORT_COLUMNS.get(filters.sort_by, Shipment.order_date)
    sort_col = sort_col.desc() if filters.sort_dir == "desc" else sort_col.asc()

    paged_query = (
        base_query.order_by(sort_col)
        .limit(filters.page_size)
        .offset((filters.page - 1) * filters.page_size)
    )
    rows = db.execute(paged_query).unique().scalars().all()
    return list(rows), total


def get_shipment_by_id(db: Session, shipment_id: int) -> Shipment | None:
    query = (
        select(Shipment)
        .options(
            joinedload(Shipment.product),
            joinedload(Shipment.supplier),
            joinedload(Shipment.order).joinedload(Order.customer),
        )
        .where(Shipment.id == shipment_id)
    )
    return db.execute(query).unique().scalar_one_or_none()


def get_shipment_by_code(db: Session, shipment_code: str) -> Shipment | None:
    query = (
        select(Shipment)
        .options(joinedload(Shipment.product), joinedload(Shipment.supplier))
        .where(Shipment.shipment_code == shipment_code)
    )
    return db.execute(query).unique().scalar_one_or_none()
