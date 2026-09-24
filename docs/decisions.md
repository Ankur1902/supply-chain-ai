# Architecture Decision Records

Short-form ADRs — decision, why, and the main tradeoff accepted.

## Why MySQL (not PostgreSQL)

Specified by the project requirements. MySQL 8 is a fully capable choice for
this workload (JSON columns, window functions, decent indexing). Tradeoff
accepted: no `NULLS LAST` syntax (worked around with an explicit
`ORDER BY col IS NULL, col DESC`), and aggregate query results come back as
`decimal.Decimal` via PyMySQL rather than `float`, requiring explicit casts
before mixing with float arithmetic — both documented in
[database.md](database.md) as real bugs this project hit and fixed, not
hypothetical concerns.

## Why FastAPI

Async-capable, Pydantic-native request/response validation, automatic
OpenAPI docs, and a dependency-injection system that makes RBAC
(`require_permission(...)`) a one-line addition per route rather than
boilerplate repeated in every handler.

## Why Next.js (App Router)

Server/client component split, file-based routing that maps cleanly onto
the app's page structure, and first-class TypeScript support. The App
Router's route groups (`(app)/`) made it straightforward to apply one
`AuthGuard` + shell layout to every authenticated page without repeating it.

## Why XGBoost/Random Forest as candidates (and why the winner isn't hardcoded)

The spec calls for XGBoost/LightGBM as the preferred algorithm family. This
project implements genuine comparison across four algorithms and a
tiebreak-only preference for XGBoost (within 1% PR-AUC of the leader) — on
the actual training run, Random Forest won outright and was selected. Faking
a predetermined winner would defeat the point of demonstrating real model
comparison; see [ml-system.md](ml-system.md) for the actual numbers.

## Why SHAP

`TreeExplainer` gives exact (not approximate) attributions for tree-based
models in reasonable time, and works identically across Random Forest,
Gradient Boosting, and XGBoost via one shared code path
(`app/ml/shap_utils.py`), with `LinearExplainer` as the fallback for
Logistic Regression. The alternative (LIME, or a model-specific importance
metric) would either be less faithful to the actual model or not generalize
across the four candidate algorithms this project actually compares.

## Why Redis

Used for the app's cache layer and rate-limit state. At current scale (a
single backend instance) this is somewhat optional, but it demonstrates the
correct extension point for horizontal scaling — a second backend instance
would share rate-limit/cache state through Redis rather than in-process
memory (the `/ai/chat` per-user rate limiter is currently in-process and
explicitly documented as the thing that would need to move to Redis first
in a multi-instance deployment).

## Why ChromaDB (and a local TF-IDF embedding, not the default)

Specified for local RAG. Chroma's default embedding function is
ONNX-based (`onnxruntime`), which conflicts with `xgboost`'s native runtime
on Windows when both are imported into the same process — see "Windows
import-order conflict" below. Rather than accept that fragility, the RAG
layer uses a local TF-IDF embedding (`app/ai/rag.py`), which is dependency-light,
fully deterministic, and adequate for a knowledge base of a few short
internal documents.

## Why a modular monolith, not microservices

One primary datastore, one small codebase, no component that independently
needs 10x the scale of the others. Microservices would add network calls,
distributed transaction concerns, and deployment overhead without a
corresponding benefit at this scale. Internal module boundaries
(`api/services/repositories/analytics/ml/ai/auth`) are enforced by import
discipline instead.

## Why tool-based AI instead of an unrestricted agent

An LLM given raw database credentials or shell access is a prompt-injection
and hallucination risk multiplied by whatever that access can do. Every
factual answer the copilot gives is backed by a call into
`app/ai/tools.py`'s allowlisted registry, which in turn calls the same
deterministic repository/analytics code the REST API uses — the LLM narrates
and reasons over real numbers, it never invents them. The one open-ended
capability (`run_sql_analytics`) is deliberately the most heavily
constrained (parsed, table/column-allowlisted, row-limited, timed out,
executed on a database user that physically cannot write).

## Why chronological (not random) train/test validation

A random split would let the model train on shipments that happened
chronologically *after* ones in its test set — an unrealistic advantage no
production model would have, since you can only ever predict forward in
time. The chronological split makes the reported metrics an honest estimate
of forward-looking performance.

## Windows import-order conflict: chromadb vs. xgboost

Discovered directly while building this project (not a hypothetical): on
this Windows dev environment, `import xgboost` followed by `import chromadb`
in the same process crashes with `ImportError: DLL load failed while
importing onnxruntime_pybind11_state` — xgboost's bundled native runtime and
onnxruntime's (pulled in by chromadb's default embedding function, evaluated
eagerly at class-definition time regardless of which embedding function you
actually configure) conflict. Reversing the import order
(`import chromadb` first) avoids the crash entirely, since Python caches the
first successful load. `app/main.py` imports `chromadb` as its literal first
statement to guarantee this regardless of which router or request runs
first in the process. Documented here because it's exactly the kind of
environment-specific gotcha that's easy to reintroduce by accident (e.g. by
adding an eager top-level `import xgboost` somewhere) without this note.

## Why timestamp-based model versioning (not a sequential counter)

The first implementation used `len(glob("model_v*.joblib")) + 1` to name new
model versions. Deleting an old artifact (which happened during development,
cleaning up a buggy training run) made the next training run reuse an
existing version number, silently overwriting a different model's metadata
association. Switched to a timestamp-based version id
(`{YYYYMMDD_HHMMSS}_{algorithm}`), which is collision-free regardless of
what's been deleted.
