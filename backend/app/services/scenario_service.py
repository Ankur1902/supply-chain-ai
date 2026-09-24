"""
What-if scenario simulator (section 21). Re-scores a shipment under a
hypothetical change and reports the modeled risk delta plus a heuristic
cost-impact estimate. Every number here is either a direct model output or
an explicitly-labeled assumption — see ASSUMED_SHIPPING_MODE_COST_MULTIPLIER
below and the `assumptions` field returned to the UI (section 30: never
invent unsupported real-world cost assumptions silently).
"""

from sqlalchemy.orm import Session

from app.ml import feature_builder, inference
from app.repositories import shipment_repository
from app.schemas.scenario import ScenarioResponse

# ASSUMPTION: relative cost multiplier by shipping mode, applied to the
# shipment's `sales` value as a rough proxy for shipping cost sensitivity.
# This is NOT sourced from the dataset (which has no carrier cost field) —
# it's a stated modeling assumption, surfaced explicitly in every scenario
# response rather than presented as measured fact.
ASSUMED_SHIPPING_MODE_COST_MULTIPLIER = {
    "Same Day": 1.5,
    "First Class": 1.25,
    "Second Class": 1.10,
    "Standard Class": 1.0,
}


def run_scenario(db: Session, shipment_code: str, changes: dict) -> ScenarioResponse:
    shipment = shipment_repository.get_shipment_by_code(db, shipment_code)
    if shipment is None:
        raise ValueError(f"Shipment {shipment_code} not found")

    overrides: dict = {}
    assumptions: list[str] = []

    if changes.get("shipping_mode"):
        overrides["shipping_mode"] = changes["shipping_mode"]
    if changes.get("scheduled_shipping_days") is not None:
        overrides["scheduled_shipping_days"] = changes["scheduled_shipping_days"]
    if changes.get("order_item_quantity") is not None:
        overrides["order_item_quantity"] = changes["order_item_quantity"]
    if changes.get("supplier_code"):
        from sqlalchemy import select

        from app.models.supplier import Supplier

        alt_supplier = db.execute(
            select(Supplier).where(Supplier.supplier_code == changes["supplier_code"])
        ).scalar_one_or_none()
        if alt_supplier is None:
            raise ValueError(f"Supplier {changes['supplier_code']} not found")
        overrides["supplier_id"] = alt_supplier.id

    baseline_row = feature_builder.build_feature_row(db, shipment)
    scenario_row = feature_builder.build_feature_row(db, shipment, overrides)

    baseline = inference.predict(db, baseline_row)
    scenario = inference.predict(db, scenario_row)

    cost_delta = 0.0
    if "shipping_mode" in overrides:
        base_mult = ASSUMED_SHIPPING_MODE_COST_MULTIPLIER.get(shipment.shipping_mode, 1.0)
        new_mult = ASSUMED_SHIPPING_MODE_COST_MULTIPLIER.get(overrides["shipping_mode"], 1.0)
        cost_delta = round(float(shipment.sales) * (new_mult - base_mult), 2)
        assumptions.append(
            "Shipping-mode cost impact uses an assumed relative cost multiplier "
            "(Same Day 1.5x, First Class 1.25x, Second Class 1.1x, Standard Class 1.0x of order "
            "sales value) — the dataset has no real carrier cost field."
        )

    return ScenarioResponse(
        shipment_code=shipment_code,
        baseline_risk_score=baseline.risk_score,
        scenario_risk_score=scenario.risk_score,
        risk_delta=round(scenario.risk_score - baseline.risk_score, 2),
        baseline_risk_level=baseline.risk_level,
        scenario_risk_level=scenario.risk_level,
        estimated_cost_delta=cost_delta,
        assumptions=assumptions,
    )
