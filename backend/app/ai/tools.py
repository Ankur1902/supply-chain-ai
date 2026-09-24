"""
Deterministic tool implementations the AI copilot can call (section 22).

Every tool here returns data computed by real SQL/analytics code — the LLM
never fabricates a number. The chat orchestrator (app/ai/chat_service.py)
is responsible for turning the LLM's requested tool_use blocks into calls
into this module and feeding the JSON result back to the model.

Tool allowlisting: TOOL_REGISTRY is the exhaustive set of callable tools.
The orchestrator refuses to execute anything not in this dict, even if a
model somehow requests an unlisted tool name.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.llm_provider import ToolDefinition
from app.ai.sql_guard import execute_safe_sql
from app.analytics import root_cause
from app.analytics.kpi_definitions import risk_level_for_score
from app.core.database import ReadOnlySessionLocal
from app.ml import feature_builder, inference
from app.models.alert import Alert
from app.models.shipment import Shipment
from app.models.supplier import Supplier
from app.repositories import analytics_repository, shipment_repository, supplier_repository
from app.repositories.analytics_repository import AnalyticsFilters
from app.schemas.shipment import ShipmentFilterParams


def tool_search_shipments(db: Session, args: dict) -> dict:
    filters = ShipmentFilterParams(
        region=args.get("region"),
        market=args.get("market"),
        shipping_mode=args.get("shipping_mode"),
        risk_level=args.get("risk_level"),
        page=1,
        page_size=min(int(args.get("limit", 20)), 50),
    )
    rows, total = shipment_repository.list_shipments(db, filters)
    return {
        "total_matching": total,
        "shipments": [
            {
                "shipment_code": s.shipment_code,
                "risk_score": float(s.risk_score) if s.risk_score is not None else None,
                "risk_level": s.risk_level,
                "shipping_mode": s.shipping_mode,
                "destination_region": s.destination_region,
                "supplier_name": s.supplier.supplier_name,
            }
            for s in rows
        ],
    }


def tool_get_shipment_details(db: Session, args: dict) -> dict:
    shipment = shipment_repository.get_shipment_by_code(db, args["shipment_code"])
    if shipment is None:
        return {"error": f"Shipment {args['shipment_code']} not found"}
    return {
        "shipment_code": shipment.shipment_code,
        "shipping_mode": shipment.shipping_mode,
        "scheduled_shipping_days": shipment.scheduled_shipping_days,
        "destination_region": shipment.destination_region,
        "origin_market": shipment.origin_market,
        "sales": float(shipment.sales),
        "supplier_name": shipment.supplier.supplier_name,
        "product_name": shipment.product.name,
        "risk_score": float(shipment.risk_score) if shipment.risk_score is not None else None,
        "risk_level": shipment.risk_level,
        "status": shipment.status,
    }


def tool_get_supplier_details(db: Session, args: dict) -> dict:
    supplier = db.execute(
        select(Supplier).where(Supplier.supplier_code == args["supplier_code"])
    ).scalar_one_or_none()
    if supplier is None:
        return {"error": f"Supplier {args['supplier_code']} not found"}
    _, metric = supplier_repository.get_supplier_with_latest_metric(db, supplier.id)
    return {
        "supplier_name": supplier.supplier_name,
        "region": supplier.supplier_region,
        "tier": supplier.supplier_tier,
        "category": supplier.product_category,
        "is_synthetic": supplier.is_synthetic,
        "score": float(metric.score) if metric else None,
        "delay_rate": float(metric.delay_rate) if metric else None,
        "avg_lead_time_days": float(metric.avg_lead_time_days) if metric else None,
        "order_volume": metric.order_volume if metric else None,
    }


def tool_get_supplier_rankings(db: Session, args: dict) -> dict:
    rows, _ = supplier_repository.list_suppliers(
        db,
        region=args.get("region"),
        product_category=args.get("product_category"),
        page=1,
        page_size=min(int(args.get("limit", 10)), 25),
        sort_by="delay_rate" if args.get("worst_first") else "score",
    )
    return {
        "suppliers": [
            {
                "supplier_name": s.supplier_name,
                "supplier_code": s.supplier_code,
                "score": float(m.score) if m else None,
                "delay_rate": float(m.delay_rate) if m else None,
                "risk_score": float(s.risk_score),
            }
            for s, m in rows
        ]
    }


def tool_get_delay_statistics(db: Session, args: dict) -> dict:
    filters = AnalyticsFilters(
        region=args.get("region"), market=args.get("market"), shipping_mode=args.get("shipping_mode")
    )
    return {
        "kpis": analytics_repository.get_dashboard_kpis(db, filters),
        "trend": analytics_repository.get_delay_trend(db, filters)[-6:],
    }


def tool_get_route_statistics(db: Session, args: dict) -> dict:
    filters = AnalyticsFilters()
    return {"by_region": analytics_repository.get_delay_by_dimension(db, filters, "region")}


def tool_get_product_statistics(db: Session, args: dict) -> dict:
    filters = AnalyticsFilters()
    return {"by_category": analytics_repository.get_delay_by_dimension(db, filters, "product_category")}


def tool_get_prediction(db: Session, args: dict) -> dict:
    shipment = shipment_repository.get_shipment_by_code(db, args["shipment_code"])
    if shipment is None:
        return {"error": f"Shipment {args['shipment_code']} not found"}
    try:
        row = feature_builder.build_feature_row(db, shipment)
        result = inference.predict(db, row)
    except inference.ModelUnavailableError as e:
        return {"error": str(e)}
    return {
        "shipment_code": shipment.shipment_code,
        "probability": result.probability,
        "risk_score": result.risk_score,
        "risk_level": result.risk_level,
        "model_version": result.model_version,
        "top_factors": [
            {"feature": f.feature_name, "value": f.feature_value, "direction": f.direction}
            for f in result.risk_factors
        ],
    }


def tool_get_root_causes(db: Session, args: dict) -> dict:
    if args.get("shipment_code"):
        shipment = shipment_repository.get_shipment_by_code(db, args["shipment_code"])
        if shipment is None:
            return {"error": f"Shipment {args['shipment_code']} not found"}
        return {"factors": root_cause.get_shipment_root_causes(db, shipment.id)}
    filters = AnalyticsFilters(region=args.get("region"))
    return {"factors": root_cause.get_aggregate_root_causes(db, filters)}


def tool_run_scenario(db: Session, args: dict) -> dict:
    shipment = shipment_repository.get_shipment_by_code(db, args["shipment_code"])
    if shipment is None:
        return {"error": f"Shipment {args['shipment_code']} not found"}

    overrides = {}
    if args.get("shipping_mode"):
        overrides["shipping_mode"] = args["shipping_mode"]
    if args.get("scheduled_shipping_days") is not None:
        overrides["scheduled_shipping_days"] = int(args["scheduled_shipping_days"])
    if args.get("supplier_code"):
        alt_supplier = db.execute(
            select(Supplier).where(Supplier.supplier_code == args["supplier_code"])
        ).scalar_one_or_none()
        if alt_supplier:
            overrides["supplier_id"] = alt_supplier.id

    try:
        baseline_row = feature_builder.build_feature_row(db, shipment)
        scenario_row = feature_builder.build_feature_row(db, shipment, overrides)
        baseline = inference.predict(db, baseline_row)
        scenario = inference.predict(db, scenario_row)
    except inference.ModelUnavailableError as e:
        return {"error": str(e)}

    return {
        "note": "Model-based scenario estimate, not a causal guarantee.",
        "baseline_risk_score": baseline.risk_score,
        "scenario_risk_score": scenario.risk_score,
        "risk_delta": round(scenario.risk_score - baseline.risk_score, 2),
    }


def tool_get_alerts(db: Session, args: dict) -> dict:
    query = select(Alert).order_by(Alert.created_at.desc()).limit(min(int(args.get("limit", 10)), 25))
    if args.get("severity"):
        query = query.where(Alert.severity == args["severity"])
    if args.get("status"):
        query = query.where(Alert.status == args["status"])
    rows = db.execute(query).scalars().all()
    return {
        "alerts": [
            {"severity": a.severity, "title": a.title, "status": a.status, "recommended_action": a.recommended_action}
            for a in rows
        ]
    }


def tool_run_sql_analytics(db: Session, args: dict) -> dict:
    """The safe Text-to-SQL escape hatch — for ad-hoc questions the other
    structured tools don't cover. Runs on the READ-ONLY connection, never the
    session passed to other tools."""
    ro_db = ReadOnlySessionLocal()
    try:
        rows = execute_safe_sql(ro_db, args["sql"])
        return {"row_count": len(rows), "rows": rows[:100]}
    except Exception as e:  # noqa: BLE001 — surfaced back to the LLM as a tool error, not raised
        return {"error": str(e)}
    finally:
        ro_db.close()


TOOL_REGISTRY: dict[str, Any] = {
    "search_shipments": tool_search_shipments,
    "get_shipment_details": tool_get_shipment_details,
    "get_supplier_details": tool_get_supplier_details,
    "get_supplier_rankings": tool_get_supplier_rankings,
    "get_delay_statistics": tool_get_delay_statistics,
    "get_route_statistics": tool_get_route_statistics,
    "get_product_statistics": tool_get_product_statistics,
    "get_prediction": tool_get_prediction,
    "get_root_causes": tool_get_root_causes,
    "run_scenario": tool_run_scenario,
    "get_alerts": tool_get_alerts,
    "run_sql_analytics": tool_run_sql_analytics,
}

TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="search_shipments",
        description="Search shipments by region, market, shipping mode, or risk level.",
        input_schema={
            "type": "object",
            "properties": {
                "region": {"type": "string"},
                "market": {"type": "string"},
                "shipping_mode": {"type": "string"},
                "risk_level": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
                "limit": {"type": "integer", "default": 20},
            },
        },
    ),
    ToolDefinition(
        name="get_shipment_details",
        description="Get full details for one shipment by its shipment_code (e.g. SHP-12345-1).",
        input_schema={
            "type": "object",
            "properties": {"shipment_code": {"type": "string"}},
            "required": ["shipment_code"],
        },
    ),
    ToolDefinition(
        name="get_supplier_details",
        description="Get details and current score for one supplier by supplier_code.",
        input_schema={
            "type": "object",
            "properties": {"supplier_code": {"type": "string"}},
            "required": ["supplier_code"],
        },
    ),
    ToolDefinition(
        name="get_supplier_rankings",
        description="Get top/bottom suppliers ranked by score or delay rate.",
        input_schema={
            "type": "object",
            "properties": {
                "region": {"type": "string"},
                "product_category": {"type": "string"},
                "worst_first": {"type": "boolean", "default": False},
                "limit": {"type": "integer", "default": 10},
            },
        },
    ),
    ToolDefinition(
        name="get_delay_statistics",
        description="Get delay-rate KPIs and recent trend, optionally filtered by region/market/shipping_mode.",
        input_schema={
            "type": "object",
            "properties": {
                "region": {"type": "string"},
                "market": {"type": "string"},
                "shipping_mode": {"type": "string"},
            },
        },
    ),
    ToolDefinition(
        name="get_route_statistics",
        description="Get delay rate broken down by destination region.",
        input_schema={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="get_product_statistics",
        description="Get delay rate broken down by product category.",
        input_schema={"type": "object", "properties": {}},
    ),
    ToolDefinition(
        name="get_prediction",
        description="Get the current ML delay-risk prediction and SHAP top factors for one shipment.",
        input_schema={
            "type": "object",
            "properties": {"shipment_code": {"type": "string"}},
            "required": ["shipment_code"],
        },
    ),
    ToolDefinition(
        name="get_root_causes",
        description="Get ranked, deterministic root-cause factors for one shipment (pass shipment_code) or in aggregate (optionally pass region).",
        input_schema={
            "type": "object",
            "properties": {"shipment_code": {"type": "string"}, "region": {"type": "string"}},
        },
    ),
    ToolDefinition(
        name="run_scenario",
        description="Re-score a shipment under a hypothetical change (shipping_mode, scheduled_shipping_days, or supplier_code) and compare to its current risk.",
        input_schema={
            "type": "object",
            "properties": {
                "shipment_code": {"type": "string"},
                "shipping_mode": {"type": "string"},
                "scheduled_shipping_days": {"type": "integer"},
                "supplier_code": {"type": "string"},
            },
            "required": ["shipment_code"],
        },
    ),
    ToolDefinition(
        name="get_alerts",
        description="Get recent operational alerts, optionally filtered by severity or status.",
        input_schema={
            "type": "object",
            "properties": {
                "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                "status": {"type": "string", "enum": ["open", "acknowledged", "resolved"]},
                "limit": {"type": "integer", "default": 10},
            },
        },
    ),
    ToolDefinition(
        name="run_sql_analytics",
        description=(
            "Run a read-only SQL SELECT against the analytics tables for questions the other tools don't "
            "cover. Table allowlist only: shipments, orders, products, customers, suppliers, "
            "supplier_metrics, alerts, root_causes, recommendations, shipment_predictions, "
            "shipment_risk_factors, model_versions. Always include a LIMIT."
        ),
        input_schema={"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]},
    ),
]
