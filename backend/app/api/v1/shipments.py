from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.auth.permissions import Permission
from app.common.exceptions import NotFoundError
from app.common.responses import paginated, success
from app.core.database import get_db
from app.repositories import shipment_repository
from app.schemas.shipment import (
    PredictionOut,
    RecommendationOut,
    ShipmentDetailOut,
    ShipmentFilterParams,
    ShipmentListItem,
)
from app.services.prediction_service import get_latest_prediction
from app.services.recommendation_service import get_recommendations_for_shipment

router = APIRouter(prefix="/shipments", tags=["shipments"])


@router.get("")
def list_shipments(
    filters: ShipmentFilterParams = Depends(),
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.SHIPMENTS_READ)),
):
    rows, total = shipment_repository.list_shipments(db, filters)
    items = [
        ShipmentListItem(
            id=s.id,
            shipment_code=s.shipment_code,
            order_date=s.order_date,
            product_name=s.product.name,
            supplier_name=s.supplier.supplier_name,
            origin_market=s.origin_market,
            destination_region=s.destination_region,
            shipping_mode=s.shipping_mode,
            scheduled_shipping_days=s.scheduled_shipping_days,
            risk_score=float(s.risk_score) if s.risk_score is not None else None,
            risk_level=s.risk_level,
            status=s.status,
            sales=float(s.sales),
        ).model_dump()
        for s in rows
    ]
    return paginated(items, filters.page, filters.page_size, total)


@router.get("/{shipment_id}")
def get_shipment(
    shipment_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.SHIPMENTS_READ)),
):
    s = shipment_repository.get_shipment_by_id(db, shipment_id)
    if s is None:
        raise NotFoundError("SHIPMENT_NOT_FOUND", f"Shipment {shipment_id} not found")

    prediction = get_latest_prediction(db, s.id)
    recommendations = get_recommendations_for_shipment(db, s.id)

    detail = ShipmentDetailOut(
        id=s.id,
        shipment_code=s.shipment_code,
        order_date=s.order_date,
        shipping_mode=s.shipping_mode,
        scheduled_shipping_days=s.scheduled_shipping_days,
        order_item_quantity=s.order_item_quantity,
        product_price=float(s.product_price),
        discount_rate=float(s.discount_rate),
        sales=float(s.sales),
        order_profit_per_order=float(s.order_profit_per_order),
        origin_market=s.origin_market,
        destination_region=s.destination_region,
        status=s.status,
        risk_score=float(s.risk_score) if s.risk_score is not None else None,
        risk_level=s.risk_level,
        product_name=s.product.name,
        product_category=s.product.category_name,
        supplier_id=s.supplier_id,
        supplier_name=s.supplier.supplier_name,
        customer_segment=s.order.customer.segment if s.order and s.order.customer else "",
        days_for_shipping_real=s.days_for_shipping_real,
        delivery_status=s.delivery_status,
        late_delivery_risk=s.late_delivery_risk,
        prediction=prediction,
        recommendations=recommendations,
    )
    return success(detail.model_dump())


@router.get("/{shipment_id}/prediction")
def get_shipment_prediction(
    shipment_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.SHIPMENTS_READ)),
):
    prediction = get_latest_prediction(db, shipment_id)
    if prediction is None:
        raise NotFoundError("PREDICTION_NOT_FOUND", f"No prediction found for shipment {shipment_id}")
    return success(prediction.model_dump())


@router.get("/{shipment_id}/recommendations")
def get_shipment_recommendations(
    shipment_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.SHIPMENTS_READ)),
):
    from app.ai.recommendations import generate_recommendations

    recs = get_recommendations_for_shipment(db, shipment_id)
    if not recs:
        shipment = shipment_repository.get_shipment_by_id(db, shipment_id)
        if shipment is not None:
            generate_recommendations(db, shipment.shipment_code)
            recs = get_recommendations_for_shipment(db, shipment_id)
    return success([r.model_dump() for r in recs])
