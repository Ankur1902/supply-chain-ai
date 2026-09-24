from pydantic import BaseModel, Field


class ScenarioRequest(BaseModel):
    shipment_code: str
    shipping_mode: str | None = None
    supplier_code: str | None = None
    scheduled_shipping_days: int | None = Field(default=None, ge=0, le=30)
    order_item_quantity: int | None = Field(default=None, ge=1, le=1000)


class ScenarioResponse(BaseModel):
    shipment_code: str
    baseline_risk_score: float
    scenario_risk_score: float
    risk_delta: float
    baseline_risk_level: str
    scenario_risk_level: str
    estimated_cost_delta: float
    note: str = "Model-based scenario estimate — not a causal guarantee."
    assumptions: list[str] = Field(default_factory=list)
