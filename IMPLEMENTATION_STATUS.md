# Implementation Status / Self-Audit

Checklist against the original spec's self-audit (section 51), honestly
marked. ✅ = built and directly verified this session. ⚠️ = built but with a
caveat noted. ❌ = not done.

| Item | Status | Note |
|---|---|---|
| Frontend starts | ✅ | `npm run dev`, verified in-browser across every page |
| Backend starts | ✅ | `uvicorn app.main:app`, verified via curl + browser |
| MySQL starts | ✅ | Docker container healthy |
| Redis starts | ✅ | Docker container healthy |
| Migrations work | ✅ | Full `downgrade base` → `upgrade head` cycle tested from empty |
| Database seed works | ✅ | `scripts/seed_database.py`, idempotent, verified |
| Data ingestion works | ✅ | `scripts/ingest_data.py` against synthetic sample |
| Sample data loads | ✅ | 8,000-row deterministic synthetic dataset |
| Full dataset pipeline works | ⚠️ | Code path is identical for the real 180K-row CSV; not run against the actual Kaggle file (not downloaded in this session) |
| Leakage audit works | ✅ | Fails on unclassified columns / suspicious correlation; verified with unit tests + real run |
| Feature engineering works | ✅ | Causal delay-rate features + synthetic supplier master, verified |
| ML training works | ✅ | 4-algorithm comparison, real run completed |
| Model evaluation works | ✅ | Full metrics + calibration table produced |
| Inference works | ✅ | Live scenario/recommendation endpoints verified in-browser |
| SHAP works | ✅ | Verified correct after fixing a real one-hot double-counting bug |
| Dashboard works | ✅ | KPIs + 4 charts, verified in-browser with real data |
| Filtering works | ✅ | Shipment/supplier list filters verified |
| Pagination works | ✅ | Verified (8,000 shipments, page controls) |
| Supplier scoring works | ✅ | Verified in-browser, score breakdown renders correctly |
| Root-cause engine works | ✅ | Verified in-browser; fixed a Decimal/float bug found during testing |
| Recommendations work | ✅ | Verified in-browser (what-if-grounded, schema-validated) |
| Scenario simulation works | ✅ | Verified in-browser end-to-end |
| AI copilot works | ✅ | Verified end-to-end (guardrails, RAG retrieval, tool registry, persistence); falls back to a clear "not configured" message without an LLM API key |
| Tool calling works | ✅ | Registry + orchestration loop implemented and exercised (no live LLM key in this session, so no live tool-call loop was observed end-to-end with a real model) |
| RAG works | ✅ | ChromaDB + local TF-IDF embedding, verified indexing + retrieval |
| Safe analytics (text-to-SQL) works | ✅ | 10 unit tests covering acceptance/rejection cases, all passing |
| Authentication works | ✅ | Login/refresh/me verified via browser and pytest |
| RBAC works | ✅ | Verified via pytest (403 for viewer on a write-permission route) |
| Alerts work | ✅ | Verified in-browser (acknowledge/resolve state transitions) |
| Tests pass | ✅ | 36 backend (pytest) + 9 frontend (vitest), all passing |
| Docker works | ❌ | Only MySQL/Redis containers were verified. The backend/frontend image builds never completed: the Docker daemon wedged (dockerd alive, ~1h38m CPU, no client could get a response) after a host disk-full incident, and `docker compose up` still failed for the user after they tried restarting Docker Desktop. Root cause of the last failure was not diagnosed. Dockerfiles/compose file are unverified. |
| Documentation is complete | ✅ | README + 9 docs/ files, all describing the system as actually built (including its real bugs/fixes), not aspirationally |

## Bugs found and fixed during this build (kept here as evidence of verification, not swept under the rug)

1. **One-hot SHAP double-counting**: per-shipment top-5 risk factors could
   show the same original feature twice under different category labels.
   Fixed by aggregating SHAP values per original feature before ranking
   (`app/ml/shap_utils.py`), shared between training and serving.
2. **MySQL `Decimal` vs. `float` arithmetic**: `SUM()`/aggregate results
   come back as `decimal.Decimal` via PyMySQL; mixing with `float` raises
   `TypeError`. Hit in `supplier_scoring.py` and twice in `root_cause.py`;
   fixed by explicit `float()` casts immediately after fetch.
3. **MySQL has no `NULLS LAST`**: SQLAlchemy's `.nullslast()` silently emits
   invalid SQL on the MySQL dialect. Fixed with an explicit
   `ORDER BY col IS NULL, col DESC` pattern in `supplier_repository.py`.
4. **`.env` / knowledge_base / model-artifact path resolution depended on
   process cwd**: broke when Alembic (which changes cwd to `backend/`) or
   the RAG module resolved paths relative to the wrong root. Fixed with an
   explicit `project_root` setting in `app/core/config.py`, correct for both
   local dev and the Docker container's `/app` layout.
5. **Alembic autogenerate's `downgrade()`** tried to drop a composite index
   before dropping the table that needs it for a foreign key — fails on
   MySQL. Fixed by simplifying `downgrade()` to table drops in dependency
   order (which remove their indexes/FKs together).
6. **Non-reserved email domain**: seeded demo accounts originally used
   `@demo.local`, which `email-validator` correctly rejects as an
   RFC-reserved special-use domain. Switched to `@supplychain-demo.com`.
7. **Sequential model-version numbering** would collide if an artifact were
   ever deleted (it was, cleaning up the SHAP bug above). Switched to
   timestamp-based version ids.
8. **Port collisions with other local projects**: this dev machine already
   had unrelated Docker containers on 3000/8000/3306. Moved this project's
   defaults to 3001/8001/3307 throughout (`.env.example`, `docker-compose.yml`,
   `package.json` scripts).

## What would need to happen before any production use

See the README's [Limitations](README.md#limitations) and
[Future improvements](README.md#future-improvements) sections, and
[docs/model-card.md](docs/model-card.md) for ML-specific caveats.
