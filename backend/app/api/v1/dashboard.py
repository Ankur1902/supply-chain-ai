from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.auth.permissions import Permission
from app.common.responses import success
from app.core.database import get_db
from app.repositories import analytics_repository
from app.repositories.analytics_repository import AnalyticsFilters

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


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


@router.get("")
def get_dashboard(
    filters: AnalyticsFilters = Depends(_filters),
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.ANALYTICS_READ)),
):
    kpis = analytics_repository.get_dashboard_kpis(db, filters)
    supplier_health = analytics_repository.get_supplier_health_summary(db)
    delay_trend = analytics_repository.get_delay_trend(db, filters)
    risk_distribution = analytics_repository.get_risk_distribution(db, filters)
    delay_by_mode = analytics_repository.get_delay_by_dimension(db, filters, "shipping_mode")
    delay_by_region = analytics_repository.get_delay_by_dimension(db, filters, "region")

    return success(
        {
            "kpis": {**kpis, "supplier_health_avg_score": supplier_health["avg_score"]},
            "charts": {
                "delay_trend": delay_trend,
                "risk_distribution": risk_distribution,
                "delay_by_shipping_mode": delay_by_mode,
                "delay_by_region": delay_by_region,
            },
        }
    )
