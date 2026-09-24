"""
Builds a prediction-time feature row for a shipment (or a what-if scenario
variant of one) by combining:

  - the shipment's own stored attributes (shipping_mode, scheduled days, etc.)
  - the supplier's synthetic master data (reliability_score, lead time)
  - CURRENT trailing delay-rate aggregates queried live from MySQL, as a
    stand-in for the causal (as-of-order-date) rates computed offline during
    training (see ml/features/feature_engineering.py).

KNOWN LIMITATION (documented in docs/ml-system.md): training computes these
rate features causally (only using data strictly before each row's own
order_date), while serving here uses "as of now" aggregates. For a live
shipment being scored shortly after it was created, these are nearly
identical; the gap only matters when scoring a shipment against
today's global rates long after the fact. Acceptable for a portfolio-scale
system with a database that isn't updated in real time from many sources —
called out explicitly rather than silently glossed over.
"""

from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.shipment import Product, Shipment
from app.models.supplier import Supplier


def _delay_rate(db: Session, column, value, join_product: bool = False) -> float:
    query = select(
        func.count(Shipment.id),
        func.sum(case((Shipment.late_delivery_risk == True, 1), else_=0)),  # noqa: E712
    )
    if join_product:
        query = query.join(Product, Shipment.product_id == Product.id)
    query = query.where(column == value)
    total, delayed = db.execute(query).one()
    return float(delayed or 0) / total if total else 0.0


def build_feature_row(db: Session, shipment: Shipment, overrides: dict | None = None) -> dict:
    overrides = overrides or {}

    shipping_mode = overrides.get("shipping_mode", shipment.shipping_mode)
    supplier_id = overrides.get("supplier_id", shipment.supplier_id)
    scheduled_shipping_days = overrides.get("scheduled_shipping_days", shipment.scheduled_shipping_days)
    order_item_quantity = overrides.get("order_item_quantity", shipment.order_item_quantity)
    destination_region = overrides.get("destination_region", shipment.destination_region)

    supplier = db.get(Supplier, supplier_id)
    product = db.get(Product, shipment.product_id)

    order_date = shipment.order_date or datetime.utcnow()

    row = {
        "shipping_mode": shipping_mode,
        "market": shipment.origin_market,
        "destination_region": destination_region,
        "customer_segment": shipment.order.customer.segment if shipment.order and shipment.order.customer else "Consumer",
        "category_name": product.category_name if product else "",
        "department_name": product.department_name if product else "",
        "order_day_of_week": order_date.strftime("%A"),
        "scheduled_shipping_days": scheduled_shipping_days,
        "order_hour": order_date.hour,
        "order_month": order_date.month,
        "order_item_quantity": order_item_quantity,
        "product_price": float(shipment.product_price),
        "discount_rate": float(shipment.discount_rate),
        "sales": float(shipment.sales),
        "historical_supplier_reliability": float(supplier.reliability_score) if supplier else 50.0,
        "supplier_lead_time": float(supplier.historical_lead_time_days) if supplier else 5.0,
        "shipping_mode_delay_rate": _delay_rate(db, Shipment.shipping_mode, shipping_mode),
        "category_delay_rate": _delay_rate(db, Product.category_name, product.category_name, join_product=True)
        if product
        else 0.2,
        "supplier_delay_rate": _delay_rate(db, Shipment.supplier_id, supplier_id),
        "route_risk": _delay_rate(db, Shipment.destination_region, destination_region),
    }
    return row
