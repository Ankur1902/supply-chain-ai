# Business Glossary

## Shipment
One line item within a customer order (one product, one quantity, one
shipping mode). This is the grain of the `shipments` table — a single order
with three different products becomes three shipment rows.

## Late Delivery Risk
The historical, POST-OUTCOME label (`late_delivery_risk`) indicating whether
a shipment's actual transit time exceeded its scheduled transit time. This
is what the ML model is trained to PREDICT before the outcome is known — see
"Risk Score" below for the prediction-time version.

## Risk Score
A 0-100 score produced by the ML model at prediction time, before a
shipment's outcome is known. Higher means more likely to be late. Mapped to
a Risk Level using configurable thresholds (default: 0-25 LOW, 25-50
MEDIUM, 50-75 HIGH, 75-100 CRITICAL).

## Risk Level
The bucketed version of Risk Score: LOW, MEDIUM, HIGH, or CRITICAL.
Thresholds are configurable in app/analytics/kpi_definitions.py.

## Supplier Score
A 0-100 composite score for a supplier, combining reliability (25%),
delivery performance (25%), quality (15%), lead time (15%), cost (10%), and
risk (10%). See app/analytics/supplier_scoring.py for the exact formula.
Some inputs (quality, cost, risk, and the lead-time baseline) come from the
SYNTHETIC supplier enrichment layer, not real supplier data — see
"Synthetic Supplier Data" below.

## Synthetic Supplier Data
The DataCo Smart Supply Chain dataset does not include real supplier
identities. This platform generates a deterministic, seeded, clearly-labeled
synthetic supplier master (supplier names, regions, tiers, and baseline
scores) so supplier-level features can be demonstrated. Every supplier row
has `is_synthetic=True`. Never treat these as real companies.

## Root Cause Factor
A ranked, deterministically-computed contributor to a delay pattern (e.g.
"Shipping mode: Same Day" or "Destination region: West Africa"), produced by
comparing a segment's delay rate to the overall baseline. This is a
correlation/variance-attribution heuristic, not a proven causal mechanism —
the platform is always careful to call these "contributing factors," never
"causes."

## What-If Scenario
A hypothetical change to a shipment (shipping mode, delivery buffer,
supplier) whose effect on modeled risk is estimated by re-running the trained
model with modified inputs. Labeled "Model-based scenario estimate" in the
UI — it is not a guarantee of the real-world outcome.

## Value at Risk / Profit at Risk
ESTIMATED financial exposure: the sum of order value (or profit) across
shipments currently classified HIGH or CRITICAL risk. This is exposure, not
a forecast of actual loss — see the Financial Impact page's Assumptions
panel for the exact formula and caveats.

## Model Version
Every prediction is tagged with the exact model_versions.version that
produced it, so risk scores remain explainable and comparable even after the
model is retrained.
