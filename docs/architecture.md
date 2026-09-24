# Architecture

## System Overview

```
Browser
  │
  ▼
Next.js 14 (App Router, TypeScript, Tailwind, TanStack Query)
  │  REST (JSON), JWT bearer auth
  ▼
FastAPI backend (modular monolith)
  │
  ├─▶ MySQL 8            — system of record (shipments, suppliers, predictions, alerts, users…)
  ├─▶ Redis               — cache / rate-limit state
  ├─▶ ML inference (app/ml)     — loads the active model artifact, scores shipments, computes SHAP
  ├─▶ AI layer (app/ai)         — LLM abstraction, tool-calling loop, RAG (ChromaDB), safe SQL guard
  └─▶ Analytics (app/analytics) — KPI definitions, root-cause engine, supplier scoring

Offline (not request-time):
  scripts/*.py  — data pipeline (ingest → validate → clean → leakage audit → feature engineering → load)
  ml/training/train.py — trains/evaluates candidate models, registers the winner, scores every shipment
```

## Why a modular monolith

Microservices buy you independent scaling and deployment at the cost of network
calls, distributed transactions, and operational overhead. This platform has
one primary datastore, one team-sized codebase, and no component that
independently needs to scale 10x past the others. A modular monolith —
strict internal module boundaries (`api/`, `services/`, `repositories/`,
`analytics/`, `ml/`, `ai/`, `auth/`) enforced by import discipline rather
than network boundaries — gets the maintainability benefits of separation
without the operational cost. See [decisions.md](decisions.md) for the full
ADR.

## Backend module layout

```
backend/app/
  api/v1/        FastAPI routers — HTTP concerns only, no business logic
  core/          config, database engines, logging, middleware
  models/        SQLAlchemy ORM models (the schema)
  schemas/       Pydantic request/response contracts
  services/      cross-cutting business logic (prediction lookup, recommendations, scenarios)
  repositories/  query building — the only layer that constructs SQLAlchemy Select() statements
  analytics/     KPI definitions, root-cause engine, supplier scoring
  ml/            online inference: loads the trained artifact, runs SHAP, builds feature rows
  ai/            LLM abstraction, tool registry, safe text-to-SQL, RAG, guardrails, chat orchestration
  auth/          JWT issuance/verification, RBAC permission table
  alerts/        deterministic alert rules
```

Request flow for a typical read: `api/v1/*.py` → `repositories/*.py` (builds
the query) → SQLAlchemy → MySQL. Services sit above repositories when a
response needs to combine multiple sources (e.g. a shipment plus its latest
prediction plus its recommendations).

## Data flow: from raw CSV to a risk score in the UI

1. `scripts/ingest_data.py` reads the raw DataCo CSV (or the synthetic
   sample), renames columns, does minimal type coercion.
2. `scripts/validate_data.py` runs schema/quality checks, drops hard
   failures, writes a data-quality report.
3. `scripts/clean_data.py` normalizes strings, derives `shipment_code`.
4. `scripts/check_data_leakage.py` classifies every column and fails the
   pipeline if anything is unclassified or suspiciously correlated with the
   target — see [ml-system.md](ml-system.md).
5. `scripts/feature_engineering.py` computes causal (as-of-order-date) delay
   rate features and generates the synthetic supplier master.
6. `scripts/load_database.py` bulk-upserts everything into MySQL.
7. `ml/training/train.py` trains/compares candidate models on a
   chronological split, registers the winner in `model_versions`, and scores
   every shipment (writing `shipment_predictions` + `shipment_risk_factors`,
   and denormalizing `risk_score`/`risk_level` onto `shipments` for fast
   filtering).
8. The FastAPI backend serves all of this read-only at request time; new
   predictions for a hypothetical scenario are computed live via
   `app/ml/inference.py` using the same trained artifact.

## AI copilot request flow

```
User question
  → app/ai/chat_service.py
      → app/ai/guardrails.py     (sanitize input, injection tripwire, system prompt)
      → app/ai/rag.py            (retrieve relevant knowledge_base/*.md chunks)
      → app/ai/llm_provider.py   (Anthropic/Google/Null — the only place that calls an LLM SDK)
      → LLM requests a tool call
          → app/ai/tools.py TOOL_REGISTRY (allowlisted only)
              → deterministic analytics/repositories code, OR
              → app/ai/sql_guard.py (validated SELECT) → read-only MySQL connection
      → tool result fed back to the LLM as data, never as instructions
  → final answer + tool-call trace returned to the UI
```

See [ai-system.md](ai-system.md) and [security.md](security.md) for the full
guardrail stack.

## Windows-specific import-order note

`chromadb` (used for RAG) and `xgboost`/`shap` (used for ML) conflict at the
native-library level on Windows when xgboost is imported into the process
first — see [decisions.md](decisions.md). `app/main.py` imports `chromadb`
as its very first statement to guarantee correct load order regardless of
which router or request runs first.
