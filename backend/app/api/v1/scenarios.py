from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.auth.permissions import Permission
from app.common.responses import success
from app.core.database import get_db
from app.ml.inference import ModelUnavailableError
from app.schemas.scenario import ScenarioRequest
from app.services.scenario_service import run_scenario

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.post("/run")
def run(
    payload: ScenarioRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.SCENARIOS_RUN)),
):
    changes = payload.model_dump(exclude={"shipment_code"}, exclude_none=True)
    try:
        result = run_scenario(db, payload.shipment_code, changes)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e)}},
        ) from e
    except ModelUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "MODEL_UNAVAILABLE", "message": str(e)}},
        ) from e
    return success(result.model_dump())
