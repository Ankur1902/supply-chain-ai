from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analytics.kpi_definitions import KPI_DEFINITIONS
from app.analytics.root_cause import get_aggregate_root_causes
from app.auth.dependencies import require_permission
from app.auth.permissions import Permission
from app.common.responses import success
from app.core.database import get_db
from app.repositories import analytics_repository
from app.repositories.analytics_repository import AnalyticsFilters

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _filters(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    region: str | None = None,
    market: str | None = None,
    shipping_mode: str | None = None,
    supplier_id: int | None = None,
    product_category: str | None = None,
) -> AnalyticsFilters:
    return AnalyticsFilters(
        date_from=date_from,
        date_to=date_to,
        region=region,
        market=market,
        shipping_mode=shipping_mode,
        supplier_id=supplier_id,
        product_category=product_category,
    )


@router.get("/kpi-definitions")
def kpi_definitions(_user=Depends(require_permission(Permission.ANALYTICS_READ))):
    return success(KPI_DEFINITIONS)


@router.get("/delays")
def delay_analytics(
    filters: AnalyticsFilters = Depends(_filters),
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.ANALYTICS_READ)),
):
    return success(
        {
            "trend": analytics_repository.get_delay_trend(db, filters),
            "by_shipping_mode": analytics_repository.get_delay_by_dimension(db, filters, "shipping_mode"),
        }
    )


@router.get("/routes")
def route_analytics(
    filters: AnalyticsFilters = Depends(_filters),
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.ANALYTICS_READ)),
):
    return success(
        {
            "by_region": analytics_repository.get_delay_by_dimension(db, filters, "region"),
            "by_market": analytics_repository.get_delay_by_dimension(db, filters, "market"),
        }
    )


@router.get("/products")
def product_analytics(
    filters: AnalyticsFilters = Depends(_filters),
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.ANALYTICS_READ)),
):
    return success(
        {"by_category": analytics_repository.get_delay_by_dimension(db, filters, "product_category")}
    )


@router.get("/risk")
def risk_analytics(
    filters: AnalyticsFilters = Depends(_filters),
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.ANALYTICS_READ)),
):
    return success(
        {
            "distribution": analytics_repository.get_risk_distribution(db, filters),
            "top_root_causes": get_aggregate_root_causes(db, filters),
        }
    )
