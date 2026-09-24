from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.auth.permissions import Permission
from app.common.responses import success
from app.core.database import get_db
from app.models.ml import ModelVersion

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
def list_models(
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.MODELS_READ)),
):
    rows = db.execute(select(ModelVersion).order_by(ModelVersion.training_date.desc())).scalars().all()
    items = [
        {
            "id": m.id,
            "version": m.version,
            "algorithm": m.algorithm,
            "training_date": m.training_date.isoformat(),
            "dataset_version": m.dataset_version,
            "feature_count": m.feature_count,
            "metrics": m.metrics,
            "status": m.status,
        }
        for m in rows
    ]
    return success(items)


@router.get("/active")
def get_active_model(
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.MODELS_READ)),
):
    m = db.execute(select(ModelVersion).where(ModelVersion.status == "active")).scalar_one_or_none()
    if m is None:
        return success(None)
    return success(
        {
            "id": m.id,
            "version": m.version,
            "algorithm": m.algorithm,
            "training_date": m.training_date.isoformat(),
            "dataset_version": m.dataset_version,
            "feature_count": m.feature_count,
            "metrics": m.metrics,
            "status": m.status,
        }
    )
