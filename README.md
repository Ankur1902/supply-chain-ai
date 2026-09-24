# AI Supply Chain Intelligence Platform

An enterprise-style operations platform that turns raw supply-chain data into
action: **data → analytics → ML prediction → explanation → root cause →
recommendation → action.** Built as a full-stack, production-shaped system
— not a notebook wired to a dashboard.

## Problem

Supply-chain operations teams need to answer, in one place: which shipments
are at risk of being late, why, which suppliers are underperforming, what
happens if we change shipping mode or supplier, what's the financial
exposure, and can an AI assistant answer these questions against real data
without hallucinating?

## What's here

- **Data pipeline**: ingest → validate → clean → **leakage audit** → feature
  engineering → MySQL, idempotent and batch-loaded.
- **ML**: leakage-safe delay-risk classifier, chronological train/test split,
  4-way algorithm comparison (Logistic Regression / Random Forest / Gradient
  Boosting / XGBoost), SHAP explainability, a real model registry.
- **Analytics**: centralized KPI definitions, a deterministic root-cause
  engine, supplier scoring.
- **AI copilot**: tool-calling LLM (Anthropic/Google, or a graceful no-op
  fallback), RAG over an internal knowledge base, a safe text-to-SQL layer
  with table/column allowlisting and a read-only DB user, full guardrails.
- **What-if simulator**: re-scores a shipment under a hypothetical shipping
  mode/supplier/buffer change using the live trained model.
- **Full-stack app**: FastAPI + MySQL 8 + Redis backend, Next.js 14 +
  TypeScript + Tailwind frontend, JWT auth, 4-role RBAC, Docker Compose.

Every value in the UI is labeled by provenance — **Source Data, Derived,
ML Prediction, Estimated, Synthetic Demo Data, or AI-Generated** — because
this project treats "don't fake it" as a hard requirement, not a nice-to-have.
See [Anti-hallucination / data integrity](#anti-hallucination--data-integrity).

## Architecture

```
Browser → Next.js 14 (App Router) → FastAPI → MySQL 8 + Redis
                                        ├─ ML inference (SHAP-explained)
                                        ├─ AI layer (tools, RAG, safe SQL)
                                        └─ Analytics (KPIs, root cause, supplier scoring)
```

Modular monolith, not microservices — one datastore, one team-sized
codebase, module boundaries enforced by import discipline
(`api/services/repositories/analytics/ml/ai/auth`). Full write-up:
[docs/architecture.md](docs/architecture.md).

## Tech stack

**Frontend**: Next.js 14, React 18, TypeScript, Tailwind CSS, Radix UI
primitives, Recharts, TanStack Query, React Hook Form + Zod.
**Backend**: Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic.
**Database**: MySQL 8 (not Postgres — see [ADR](docs/decisions.md)).
**Cache**: Redis. **ML**: pandas, scikit-learn, XGBoost, SHAP, joblib.
**AI**: Anthropic/Google SDKs behind a provider abstraction, ChromaDB (local
TF-IDF embedding — see [ADR](docs/decisions.md)), sqlglot for SQL validation.
**Testing**: pytest. **DevOps**: Docker, Docker Compose.

## Dataset

[DataCo Smart Supply Chain Dataset](https://www.kaggle.com/datasets/shashwatwork/dataco-smart-supply-chain-for-big-data-analysis)
(~180K order-item rows). Not committed to this repo (size + redistribution).
A **deterministic synthetic sample generator**
(`scripts/generate_sample_data.py`) produces dev/demo data with the identical
schema and a fixed seed, clearly documented as synthetic — never presented
as the real dataset. Full details: [docs/data-pipeline.md](docs/data-pipeline.md).

## Quick start

```bash
cp .env.example .env
docker compose up
```

Then, in another shell:

```bash
python scripts/generate_sample_data.py --rows 8000
python scripts/run_pipeline.py --sample
python ml/training/train.py
python scripts/seed_database.py
```

Open http://localhost:3001 and sign in with `admin@supplychain-demo.com` /
`DemoPass123!` (three other demo roles are one click away on the login
page). Full instructions, including non-Docker local setup and why the
ports are non-default: [docs/deployment.md](docs/deployment.md).

> **Heads-up: the full `docker compose up` path is unverified.** During
> development the Docker daemon on the author's machine wedged (`dockerd`
> alive but unresponsive to every client) and `docker compose up` for the
> backend/frontend containers could not be made to work, so those two
> Dockerfiles have never been run end-to-end. Everything else was verified
> by running the backend (`uvicorn`) and frontend (`npm run dev`) directly on
> the host against the MySQL container from `docker-compose.yml`
> (`docker compose up -d mysql redis`). If you can't get compose working
> either, use that split setup, or point `DATABASE_URL` at any MySQL 8
> instance you run yourself. See [docs/deployment.md](docs/deployment.md).

## Data pipeline

```
ingest → validate → clean → check_data_leakage → feature_engineering → load_database
```

Every stage is idempotent (unique-key upserts, batched at 5,000 rows) and
prints its own metrics. Full write-up: [docs/data-pipeline.md](docs/data-pipeline.md).

## Database design

Normalized MySQL 8 schema (19 tables), composite indexes matched to actual
query patterns (not every column indexed speculatively), Alembic migrations
verified from a genuinely empty database in both directions. Two real,
hard-won MySQL-specific bugs (no `NULLS LAST`, `Decimal` vs. `float`
arithmetic) are documented, not swept under the rug:
[docs/database.md](docs/database.md).

## ML pipeline & explainability

Target-leakage prevention is enforced by an automated audit
(`scripts/check_data_leakage.py`) that fails the pipeline on any
unclassified column or suspiciously-correlated "safe" feature — not just a
documented convention. Chronological train/test split. Four algorithms
genuinely compared (the winner isn't hardcoded — Random Forest beat XGBoost
on the checked-in run). Every prediction carries its top-5 SHAP factors,
fixed to avoid a real one-hot-encoding double-counting bug this project hit
and fixed. Full write-up: [docs/ml-system.md](docs/ml-system.md) and the
[model card](docs/model-card.md).

## Supplier scoring

0–100 composite score (reliability 25%, delivery performance 25%, quality
15%, lead time 15%, cost 10%, risk 10%), weights configurable in one place
(`app/analytics/kpi_definitions.py`). The DataCo dataset has no real supplier
identity — a clearly-labeled **synthetic enrichment layer** generates
deterministic supplier master data; delivery/reliability components are
still derived from real shipment history joined against that synthetic
assignment. Never presented as real company data.

## Root-cause analysis

Deterministic variance-attribution engine
(`app/analytics/root_cause.py`) — ranks shipping mode / region / supplier /
category / schedule-tightness by how much their segment-level delay rates
deviate from baseline, weighted by shipment volume. Reported as "contributing
factors," never as proven causes. The AI copilot can summarize this output
in natural language but never invents the ranking itself.

## AI architecture, tool calling, RAG, and safe text-to-SQL

A provider-agnostic LLM abstraction, an allowlisted tool registry backed by
real deterministic code, RAG over an internal knowledge base with a
dependency-light local embedding, and a defense-in-depth safe SQL layer (SQL
parsing + table/column allowlist + row cap + timeout + a database user that
is *physically* incapable of writing). Full write-up:
[docs/ai-system.md](docs/ai-system.md).

## Security

JWT auth, 4-role RBAC via a static permission table, a dedicated read-only
MySQL user for AI queries, rate limiting (global + AI-specific), request
size limits, security headers, sanitized error responses, audit logging.
Full write-up: [docs/security.md](docs/security.md).

## Testing

`backend/tests/` — pytest unit/integration tests covering auth, RBAC, the
SQL guard's rejection cases, and leakage-audit classification. See
[Limitations](#limitations) for what's not yet covered (frontend
component/E2E tests).

## Docker setup

`docker-compose.yml` — MySQL 8, Redis, backend, frontend, with healthchecks
and the backend waiting on MySQL before running migrations. Non-default
host ports (3001/8001/3307) to avoid colliding with other local projects —
see [docs/deployment.md](docs/deployment.md).

**Verification status**: the MySQL and Redis services were built, started,
and confirmed healthy this way, and `docker compose config` validates the
full file. The backend/frontend containers' build+run was not completed
end-to-end in this session — Docker's daemon stopped responding partway
through (see [Limitations](#limitations)) — so treat `docker compose up`
for the full stack as written-and-config-validated rather than
fully rehearsed. The entire application *is* fully verified working via the
non-Docker local setup (`uvicorn` + `npm run dev`), which exercises the
identical backend/frontend code.

## Environment setup

See `.env.example` for every variable, and
[docs/deployment.md](docs/deployment.md) for the full walkthrough.

## Training instructions

```bash
python ml/training/train.py
```

Trains, compares, selects, registers, and scores every shipment. See
[docs/ml-system.md](docs/ml-system.md).

## API documentation

Interactive OpenAPI docs at `/api/docs` once the backend is running;
conventions (response envelope, pagination, error codes) documented in
[docs/api.md](docs/api.md).

## Deployment

See [docs/deployment.md](docs/deployment.md).

## Anti-hallucination / data integrity

This is a portfolio project, and faking results defeats its purpose. Every
value shown is classified as one of: **Source Data, Derived, Predicted,
Estimated, Synthetic, or AI-Generated** — visible via badges throughout the
UI (dashboard KPIs, supplier pages, shipment detail, AI recommendations).
Financial "at risk" figures expose their assumptions explicitly in the UI
rather than presenting a made-up number as fact. The synthetic supplier
layer is never presented as real. Root-cause output is labeled "contributing
factor," never "cause." What-if scenario results are labeled "model-based
estimate," never a guarantee.

## Limitations

- The full-stack `docker compose up` path (backend + frontend containers)
  was written and its config validated, but not rehearsed end-to-end in
  this session — Docker's daemon became unresponsive partway through
  (likely a residual effect of an unrelated host disk-space incident during
  development). MySQL/Redis containers were verified healthy; the
  backend/frontend Dockerfiles reuse the same `requirements.txt`/`package.json`
  already proven to work via the local dev servers, but the containers
  themselves should be smoke-tested before relying on them.
- The checked-in demo model is trained on an 8,000-row **synthetic** sample,
  not the full real 180K-row dataset — metrics in the model card reflect
  that; see [docs/model-card.md](docs/model-card.md) for realistic
  expectations at full scale.
- Supplier scoring/behavior is partly grounded in synthetic data by
  necessity (see above) — real supplier signal is limited to what
  delivery/reliability history can derive.
- Serving-time historical delay-rate features use a live "as of now"
  approximation rather than a true as-of-date reconstruction — documented
  tradeoff in [docs/ml-system.md](docs/ml-system.md).
- Frontend automated test coverage (component/E2E) is thinner than backend
  coverage — the UI was verified through direct browser testing during
  development, not (yet) codified into a Playwright suite.
- The AI copilot's tool layer doesn't re-check per-resource RBAC on every
  individual tool call (relies on `AI_USE` only being granted to roles that
  already have full read access) — documented gap in
  [docs/ai-system.md](docs/ai-system.md).
- No hyperparameter tuning was performed; this demonstrates a correct
  pipeline, not a competition-tuned model.

## Future improvements

- Retrain on the full real DataCo dataset and re-validate leakage findings
  against its actual (possibly different) categorical value sets.
- Playwright E2E coverage for the golden paths (login → dashboard →
  shipment detail → what-if → copilot).
- Move the AI rate limiter from in-process memory to Redis for multi-instance
  deployments.
- Per-tool RBAC checks in the AI tool registry, for future roles with
  `AI_USE` but narrower read scope.
- Hyperparameter search (e.g. Optuna) once real-scale data is in place.

## Repository structure

```
frontend/    Next.js app
backend/     FastAPI app (api/core/models/schemas/services/repositories/analytics/ml/ai/auth/alerts)
ml/          offline training pipeline (features/training/evaluation/inference/artifacts)
data/        raw/processed/sample/external
knowledge_base/  RAG source documents
scripts/     data pipeline, seeding, ML training entrypoints
docs/        architecture, database, data-pipeline, ml-system, ai-system, security, api, deployment, model-card, decisions
docker/      MySQL init scripts
```
