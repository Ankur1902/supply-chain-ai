from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.auth.permissions import Permission
from app.common.exceptions import NotFoundError
from app.common.responses import paginated, success
from app.core.database import get_db
from app.repositories import supplier_repository
from app.schemas.supplier import (
    SupplierComparisonOut,
    SupplierDetailOut,
    SupplierListItem,
    SupplierScoreBreakdown,
    SupplierTrendPoint,
)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def _to_detail(supplier, metric, trend=None) -> SupplierDetailOut:
    return SupplierDetailOut(
        id=supplier.id,
        supplier_code=supplier.supplier_code,
        supplier_name=supplier.supplier_name,
        supplier_region=supplier.supplier_region,
        supplier_tier=supplier.supplier_tier,
        product_category=supplier.product_category,
        historical_lead_time_days=float(supplier.historical_lead_time_days),
        capacity_score=float(supplier.capacity_score),
        quality_score=float(supplier.quality_score),
        reliability_score=float(supplier.reliability_score),
        cost_score=float(supplier.cost_score),
        risk_score=float(supplier.risk_score),
        is_synthetic=supplier.is_synthetic,
        score=float(metric.score) if metric else None,
        score_breakdown=(
            SupplierScoreBreakdown(
                reliability_component=float(metric.reliability_component),
                delivery_component=float(metric.delivery_component),
                quality_component=float(metric.quality_component),
                lead_time_component=float(metric.lead_time_component),
                cost_component=float(metric.cost_component),
                risk_component=float(metric.risk_component),
            )
            if metric
            else None
        ),
        delay_rate=float(metric.delay_rate) if metric else None,
        avg_lead_time_days=float(metric.avg_lead_time_days) if metric else None,
        order_volume=metric.order_volume if metric else None,
        trend=[
            SupplierTrendPoint(
                period_start=m.period_start,
                score=float(m.score),
                delay_rate=float(m.delay_rate),
                order_volume=m.order_volume,
            )
            for m in (trend or [])
        ],
    )


@router.get("")
def list_suppliers(
    region: str | None = None,
    product_category: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    sort_by: str = Query(default="score"),
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.SUPPLIERS_READ)),
):
    rows, total = supplier_repository.list_suppliers(
        db, region=region, product_category=product_category, page=page, page_size=page_size, sort_by=sort_by
    )
    items = [
        SupplierListItem(
            id=s.id,
            supplier_code=s.supplier_code,
            supplier_name=s.supplier_name,
            supplier_region=s.supplier_region,
            supplier_tier=s.supplier_tier,
            product_category=s.product_category,
            score=float(m.score) if m else None,
            delay_rate=float(m.delay_rate) if m else None,
            avg_lead_time_days=float(m.avg_lead_time_days) if m else None,
            order_volume=m.order_volume if m else None,
            risk_score=float(s.risk_score),
            is_synthetic=s.is_synthetic,
        ).model_dump()
        for s, m in rows
    ]
    return paginated(items, page, page_size, total)


@router.get("/compare")
def compare_suppliers(
    supplier_ids: str = Query(..., description="Comma-separated supplier IDs, e.g. 1,2"),
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.SUPPLIERS_READ)),
):
    ids = [int(i) for i in supplier_ids.split(",") if i.strip()]
    details = []
    for sid in ids:
        supplier, metric = supplier_repository.get_supplier_with_latest_metric(db, sid)
        if supplier is None:
            continue
        trend = supplier_repository.get_supplier_trend(db, sid)
        details.append(_to_detail(supplier, metric, trend))
    return success(SupplierComparisonOut(suppliers=details).model_dump())


@router.get("/{supplier_id}")
def get_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.SUPPLIERS_READ)),
):
    supplier, metric = supplier_repository.get_supplier_with_latest_metric(db, supplier_id)
    if supplier is None:
        raise NotFoundError("SUPPLIER_NOT_FOUND", f"Supplier {supplier_id} not found")
    trend = supplier_repository.get_supplier_trend(db, supplier_id)
    return success(_to_detail(supplier, metric, trend).model_dump())
