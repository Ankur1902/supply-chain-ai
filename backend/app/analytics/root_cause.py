"""
Deterministic root-cause analytics engine.

Every number here comes from an actual SQL aggregation over `shipments`
(joined to `suppliers`/`products`/`customers` as needed) — nothing is
invented or estimated by an LLM. The AI copilot may *summarize* this output
in natural language, but the ranked factors and their contribution
percentages are computed here, deterministically, every time. See
docs/ml-system.md and section 18 of the platform spec.

Method: for each candidate dimension (shipping mode, destination region,
supplier, product category, customer segment, scheduled-window tightness),
compute the shipment-count-weighted average absolute deviation of each
segment's delay rate from the overall (filtered-scope) delay rate. A
dimension where delay rates vary a lot between segments — weighted by how
many shipments sit in the worst segments — "explains" more of the variance
than a dimension where every segment behaves about the same. Dimension
scores are normalized to sum to 100 and reported as `contribution_pct`.

This is a variance-attribution heuristic, not a causal model — it tells you
which dimensions correlate most with delay outcomes in the selected scope,
not that changing them will fix delays. That distinction is preserved in
the UI copy ("contributing factor", never "cause").
"""

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.shipment import Product, Shipment
from app.models.supplier import Supplier
from app.repositories.analytics_repository import AnalyticsFilters, apply_filters

DIMENSION_LABELS = {
    "shipping_mode": "Shipping mode",
    "destination_region": "Destination region",
    "supplier": "Supplier performance",
    "product_category": "Product category",
    "customer_segment": "Customer segment",
    "schedule_tightness": "Tight delivery window",
}


def _global_delay_rate(db: Session, f: AnalyticsFilters) -> tuple[int, int]:
    query = select(
        func.count(Shipment.id),
        func.sum(case((Shipment.late_delivery_risk == True, 1), else_=0)),  # noqa: E712
    )
    query = apply_filters(query, f, needs_product_join=bool(f.product_category))
    total, delayed = db.execute(query).one()
    return total or 0, float(delayed or 0)


def _weighted_deviation_for_dimension(
    db: Session, f: AnalyticsFilters, dimension_col, global_rate: float, needs_join=None
) -> tuple[float, str]:
    query = select(
        dimension_col.label("segment"),
        func.count(Shipment.id).label("total"),
        func.sum(case((Shipment.late_delivery_risk == True, 1), else_=0)).label("delayed"),  # noqa: E712
    ).group_by(dimension_col)
    query = apply_filters(query, f, needs_product_join=bool(f.product_category))
    if needs_join is not None:
        query = query.join(needs_join)

    rows = db.execute(query).all()
    total_all = sum(r.total for r in rows) or 1
    weighted_dev = 0.0
    worst_segment, worst_rate, best_segment, best_rate = None, -1.0, None, 2.0
    for r in rows:
        rate = float(r.delayed or 0) / r.total if r.total else 0.0
        weighted_dev += r.total * abs(rate - global_rate)
        if rate > worst_rate:
            worst_rate, worst_segment = rate, r.segment
        if rate < best_rate:
            best_rate, best_segment = rate, r.segment
    weighted_dev /= total_all

    metric = ""
    if worst_segment is not None and best_segment is not None:
        metric = (
            f"Worst segment '{worst_segment}' delays {worst_rate:.1%} of shipments vs. "
            f"best segment '{best_segment}' at {best_rate:.1%} (overall {global_rate:.1%})."
        )
    return weighted_dev, metric


def get_aggregate_root_causes(db: Session, f: AnalyticsFilters, top_n: int = 5) -> list[dict]:
    total, delayed = _global_delay_rate(db, f)
    if total == 0:
        return []
    global_rate = delayed / total

    scores: dict[str, tuple[float, str]] = {}
    scores["shipping_mode"] = _weighted_deviation_for_dimension(db, f, Shipment.shipping_mode, global_rate)
    scores["destination_region"] = _weighted_deviation_for_dimension(
        db, f, Shipment.destination_region, global_rate
    )
    scores["supplier"] = _weighted_deviation_for_dimension(
        db, f, Supplier.supplier_name, global_rate, needs_join=Supplier
    )
    scores["product_category"] = _weighted_deviation_for_dimension(
        db, f, Product.category_name, global_rate, needs_join=None if f.product_category else Product
    )

    schedule_bucket = case(
        (Shipment.scheduled_shipping_days <= 2, "Tight (<=2 days)"), else_="Standard (>2 days)"
    )
    scores["schedule_tightness"] = _weighted_deviation_for_dimension(
        db, f, schedule_bucket, global_rate
    )

    total_score = sum(v[0] for v in scores.values()) or 1.0
    ranked = sorted(scores.items(), key=lambda kv: kv[1][0], reverse=True)[:top_n]

    return [
        {
            "factor_name": DIMENSION_LABELS[name],
            "contribution_pct": round(100 * dev / total_score, 2),
            "rank": i + 1,
            "supporting_metric": metric,
        }
        for i, (name, (dev, metric)) in enumerate(ranked)
    ]


def get_shipment_root_causes(db: Session, shipment_id: int, top_n: int = 5) -> list[dict]:
    """Per-shipment root cause: how does *this* shipment's segment on each
    dimension compare to the global baseline?"""
    shipment = db.get(Shipment, shipment_id)
    if shipment is None:
        return []

    f = AnalyticsFilters()
    total, delayed = _global_delay_rate(db, f)
    global_rate = delayed / total if total else 0.0

    factors = []

    def _segment_rate(filter_col, value) -> tuple[int, float]:
        q = select(
            func.count(Shipment.id), func.sum(case((Shipment.late_delivery_risk == True, 1), else_=0))  # noqa: E712
        ).where(filter_col == value)
        t, d = db.execute(q).one()
        return t or 0, float(d or 0)

    mode_total, mode_delayed = _segment_rate(Shipment.shipping_mode, shipment.shipping_mode)
    if mode_total:
        rate = mode_delayed / mode_total
        factors.append(
            (
                f"Shipping mode: {shipment.shipping_mode}",
                rate - global_rate,
                f"{shipment.shipping_mode} shipments delay {rate:.1%} of the time vs. {global_rate:.1%} overall.",
            )
        )

    region_total, region_delayed = _segment_rate(Shipment.destination_region, shipment.destination_region)
    if region_total:
        rate = region_delayed / region_total
        factors.append(
            (
                f"Destination region: {shipment.destination_region}",
                rate - global_rate,
                f"{shipment.destination_region} shipments delay {rate:.1%} of the time vs. {global_rate:.1%} overall.",
            )
        )

    supplier_total, supplier_delayed = _segment_rate(Shipment.supplier_id, shipment.supplier_id)
    if supplier_total:
        rate = supplier_delayed / supplier_total
        supplier_name = shipment.supplier.supplier_name if shipment.supplier else str(shipment.supplier_id)
        factors.append(
            (
                f"Supplier: {supplier_name}",
                rate - global_rate,
                f"{supplier_name} shipments delay {rate:.1%} of the time vs. {global_rate:.1%} overall.",
            )
        )

    is_tight = shipment.scheduled_shipping_days <= 2
    tight_q = select(
        func.count(Shipment.id), func.sum(case((Shipment.late_delivery_risk == True, 1), else_=0))  # noqa: E712
    ).where(Shipment.scheduled_shipping_days <= 2 if is_tight else Shipment.scheduled_shipping_days > 2)
    tight_total, tight_delayed = db.execute(tight_q).one()
    if tight_total:
        rate = float(tight_delayed or 0) / tight_total
        label = "Tight delivery window (<=2 scheduled days)" if is_tight else "Standard delivery window"
        factors.append((label, rate - global_rate, f"This window delays {rate:.1%} of the time vs. {global_rate:.1%} overall."))

    factors.sort(key=lambda x: abs(x[1]), reverse=True)
    total_abs = sum(abs(x[1]) for x in factors) or 1.0

    return [
        {
            "factor_name": name,
            "contribution_pct": round(100 * abs(delta) / total_abs, 2),
            "rank": i + 1,
            "supporting_metric": metric,
        }
        for i, (name, delta, metric) in enumerate(factors[:top_n])
    ]
