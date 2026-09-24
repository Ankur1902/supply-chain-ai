"""
Import every model module here so Alembic's autogenerate (env.py imports
Base.metadata from this package) sees the full schema.
"""

from app.models.base import Base  # noqa: F401
from app.models.user import Role, User, UserRole  # noqa: F401
from app.models.supplier import Supplier, SupplierMetric  # noqa: F401
from app.models.shipment import Customer, Product, Order, Shipment  # noqa: F401
from app.models.ml import ModelVersion, ShipmentPrediction, ShipmentRiskFactor  # noqa: F401
from app.models.analytics import RootCause, Recommendation  # noqa: F401
from app.models.alert import Alert  # noqa: F401
from app.models.ai_chat import AIConversation, AIMessage  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401

__all__ = [
    "Base",
    "Role",
    "User",
    "UserRole",
    "Supplier",
    "SupplierMetric",
    "Customer",
    "Product",
    "Order",
    "Shipment",
    "ModelVersion",
    "ShipmentPrediction",
    "ShipmentRiskFactor",
    "RootCause",
    "Recommendation",
    "Alert",
    "AIConversation",
    "AIMessage",
    "AuditLog",
]
