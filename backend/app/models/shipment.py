from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    DECIMAL,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Customer(Base, TimestampMixin):
    """SOURCE DATA — derived from DataCo customer fields (de-identified)."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_customer_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    segment: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    state: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    zipcode: Mapped[str] = mapped_column(String(20), nullable=False, default="")


class Product(Base, TimestampMixin):
    """SOURCE DATA — derived from DataCo product/category/department fields."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_product_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    category_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    department_id: Mapped[int] = mapped_column(Integer, nullable=False)
    department_name: Mapped[str] = mapped_column(String(150), nullable=False)
    price: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False, default=0)


class Order(Base, TimestampMixin):
    """SOURCE DATA — one row per DataCo order (order header)."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_order_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customers.id"), nullable=False, index=True
    )
    order_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    order_status: Mapped[str] = mapped_column(String(50), nullable=False)
    market: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    order_region: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    order_country: Mapped[str] = mapped_column(String(100), nullable=False)
    order_state: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    order_city: Mapped[str] = mapped_column(String(100), nullable=False, default="")

    customer: Mapped["Customer"] = relationship()
    shipments: Mapped[list["Shipment"]] = relationship(back_populates="order")


class Shipment(Base, TimestampMixin):
    """
    One row per DataCo order-item (the dataset's shipment-level grain).

    IMPORTANT — target leakage boundary:
    `days_for_shipping_real` and `delivery_status` are POST-OUTCOME fields.
    They are stored here for historical analytics/reporting/evaluation ONLY.
    They must NEVER be passed as features to the ML model at prediction time.
    See scripts/check_data_leakage.py and docs/ml-system.md.
    """

    __tablename__ = "shipments"
    __table_args__ = (
        Index("ix_shipments_supplier_risk", "supplier_id", "risk_level"),
        Index("ix_shipments_order_date_mode", "order_date", "shipping_mode"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shipment_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)

    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id"), nullable=False, index=True
    )
    supplier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("suppliers.id"), nullable=False, index=True
    )

    # --- Prediction-time features (available BEFORE outcome is known) ---
    order_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    shipping_mode: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    scheduled_shipping_days: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    order_item_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    product_price: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    discount_rate: Mapped[float] = mapped_column(DECIMAL(5, 4), nullable=False, default=0)
    sales: Mapped[float] = mapped_column(DECIMAL(12, 2), nullable=False)
    order_profit_per_order: Mapped[float] = mapped_column(DECIMAL(12, 2), nullable=False, default=0)

    origin_market: Mapped[str] = mapped_column(String(50), nullable=False)
    destination_region: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # --- POST-OUTCOME fields — analytics/eval only, never used as ML features ---
    days_for_shipping_real: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(50), nullable=False)
    late_delivery_risk: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)

    # --- Derived / operational state ---
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    risk_score: Mapped[float | None] = mapped_column(DECIMAL(5, 2), nullable=True, index=True)
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)

    order: Mapped["Order"] = relationship(back_populates="shipments")
    product: Mapped["Product"] = relationship()
    supplier: Mapped["Supplier"] = relationship()
