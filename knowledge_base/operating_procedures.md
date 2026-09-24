# Operating Procedures / Playbooks

## When a shipment is flagged CRITICAL risk
1. Open the shipment detail page and review the top SHAP risk factors.
2. Check the What-If Simulator: does switching shipping mode or adding a
   1-2 day delivery buffer meaningfully reduce modeled risk?
3. If the driving factor is supplier-related, check that supplier's recent
   score trend — a single bad shipment might be part of a broader pattern.
4. Acknowledge the corresponding alert once a decision is made (escalate,
   notify customer, reroute, or accept the risk), and record the action so
   it appears in the shipment's audit history.

## When a supplier's score drops sharply month-over-month
1. Check whether the drop is driven by delay rate, lead time, or a
   synthetic-layer field (quality/cost/risk) — the supplier detail page
   breaks the score into its six weighted components.
2. Compare against other suppliers in the same category/region using the
   supplier comparison view.
3. A drop concentrated in delivery/reliability components (both DERIVED
   from real shipment history) is a stronger operational signal than a
   change in the synthetic components, which don't change on their own.

## When delay rates spike platform-wide
1. Check the Root Cause Analytics page for the current top contributing
   factors (shipping mode, region, category, supplier, schedule tightness).
2. Cross-reference with the Alerts page — an "Unusual delay spike detected"
   alert fires automatically when the trailing 7-day delay rate exceeds
   1.5x the trailing 30-day baseline.
3. Isolate whether the spike is concentrated in one route/supplier/mode
   before taking a platform-wide action.

## Using the AI Copilot responsibly
- Ask concrete questions ("which suppliers are riskiest in LATAM right
  now?") rather than open-ended ones — the copilot answers using live tool
  calls against the database, not general knowledge.
- Treat scenario and recommendation outputs as decision support, not a
  final answer — they carry a stated confidence level for a reason.
- If the copilot says a model or prediction is unavailable, that means no
  active model is registered (see docs/ml-system.md) — retrain via
  `python ml/training/train.py` rather than trusting a fallback guess.
