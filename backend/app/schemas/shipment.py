from datetime import datetime

from pydantic import BaseModel, Field


class ShipmentListItem(BaseModel):
    id: int
    shipment_code: str
    order_date: datetime
    product_name: str
    supplier_name: str
    origin_market: str
    destination_region: str
    shipping_mode: str
    scheduled_shipping_days: int
    risk_score: float | None
    risk_level: str | None
    status: str
    sales: float

    model_config = {"from_attributes": True}


class RiskFactorOut(BaseModel):
    feature_name: str
    feature_value: str
    shap_value: float
    direction: str
    rank: int

    model_config = {"from_attributes": True}


class PredictionOut(BaseModel):
    probability: float
    risk_score: float
    risk_level: str
    model_version: str
    predicted_at: datetime
    risk_factors: list[RiskFactorOut]


class RecommendationOut(BaseModel):
    id: int
    action_type: str
    recommendation_text: str
    reason: str
    expected_impact: str
    confidence: float
    ai_generated: bool

    model_config = {"from_attributes": True}


class ShipmentDetailOut(BaseModel):
    id: int
    shipment_code: str
    order_date: datetime
    shipping_mode: str
    scheduled_shipping_days: int
    order_item_quantity: int
    product_price: float
    discount_rate: float
    sales: float
    order_profit_per_order: float
    origin_market: str
    destination_region: str
    status: str
    risk_score: float | None
    risk_level: str | None

    product_name: str
    product_category: str
    supplier_id: int
    supplier_name: str
    customer_segment: str

    # POST-OUTCOME fields — labeled explicitly, historical/eval use only
    days_for_shipping_real: int
    delivery_status: str
    late_delivery_risk: bool

    prediction: PredictionOut | None = None
    recommendations: list[RecommendationOut] = Field(default_factory=list)


class ShipmentFilterParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=200)
    search: str | None = None
    region: str | None = None
    market: str | None = None
    shipping_mode: str | None = None
    supplier_id: int | None = None
    product_category: str | None = None
    risk_level: str | None = None
    status: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    sort_by: str = "order_date"
    sort_dir: str = "desc"
