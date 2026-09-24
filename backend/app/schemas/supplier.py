from datetime import date

from pydantic import BaseModel, Field


class SupplierListItem(BaseModel):
    id: int
    supplier_code: str
    supplier_name: str
    supplier_region: str
    supplier_tier: str
    product_category: str
    score: float | None
    delay_rate: float | None
    avg_lead_time_days: float | None
    order_volume: int | None
    risk_score: float
    is_synthetic: bool


class SupplierScoreBreakdown(BaseModel):
    reliability_component: float
    delivery_component: float
    quality_component: float
    lead_time_component: float
    cost_component: float
    risk_component: float


class SupplierTrendPoint(BaseModel):
    period_start: date
    score: float
    delay_rate: float
    order_volume: int


class SupplierDetailOut(BaseModel):
    id: int
    supplier_code: str
    supplier_name: str
    supplier_region: str
    supplier_tier: str
    product_category: str
    historical_lead_time_days: float
    capacity_score: float
    quality_score: float
    reliability_score: float
    cost_score: float
    risk_score: float
    is_synthetic: bool

    score: float | None
    score_breakdown: SupplierScoreBreakdown | None
    delay_rate: float | None
    avg_lead_time_days: float | None
    order_volume: int | None
    trend: list[SupplierTrendPoint] = Field(default_factory=list)


class SupplierComparisonOut(BaseModel):
    suppliers: list[SupplierDetailOut]
