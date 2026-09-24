from datetime import datetime

from pydantic import BaseModel


class AlertOut(BaseModel):
    id: int
    severity: str
    title: str
    description: str
    entity_type: str
    entity_id: int | None
    recommended_action: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertActionResponse(BaseModel):
    id: int
    status: str
    message: str
