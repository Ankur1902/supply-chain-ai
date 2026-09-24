from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.auth.permissions import Permission
from app.common.exceptions import NotFoundError
from app.common.responses import paginated, success
from app.core.database import get_db
from app.models.alert import Alert
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.alert import AlertActionResponse, AlertOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    severity: str | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.ALERTS_READ)),
):
    query = select(Alert)
    if severity:
        query = query.filter(Alert.severity == severity)
    if status:
        query = query.filter(Alert.status == status)

    total = len(db.execute(query).all())
    query = query.order_by(Alert.created_at.desc()).limit(page_size).offset((page - 1) * page_size)
    rows = db.execute(query).scalars().all()
    items = [AlertOut.model_validate(a).model_dump() for a in rows]
    return paginated(items, page, page_size, total)


@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.ALERTS_WRITE)),
):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise NotFoundError("ALERT_NOT_FOUND", f"Alert {alert_id} not found")
    alert.status = "acknowledged"
    alert.acknowledged_by = user.id
    alert.acknowledged_at = datetime.utcnow()
    db.add(
        AuditLog(
            user_id=user.id,
            action="alert.acknowledge",
            entity_type="alert",
            entity_id=alert.id,
            details={},
        )
    )
    db.commit()
    return success(AlertActionResponse(id=alert.id, status=alert.status, message="Alert acknowledged").model_dump())


@router.post("/{alert_id}/resolve")
def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.ALERTS_WRITE)),
):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise NotFoundError("ALERT_NOT_FOUND", f"Alert {alert_id} not found")
    alert.status = "resolved"
    alert.resolved_by = user.id
    alert.resolved_at = datetime.utcnow()
    db.add(
        AuditLog(
            user_id=user.id, action="alert.resolve", entity_type="alert", entity_id=alert.id, details={}
        )
    )
    db.commit()
    return success(AlertActionResponse(id=alert.id, status=alert.status, message="Alert resolved").model_dump())
