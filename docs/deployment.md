# Deployment / Local Setup

## Quick start (Docker)

```bash
cp .env.example .env        # then fill in secrets — see below
docker compose up
```

This starts MySQL 8, Redis, the FastAPI backend (waits for MySQL's
healthcheck before running `alembic upgrade head` and starting uvicorn), and
the Next.js frontend. Once healthy:

- Frontend: http://localhost:3001
- Backend API docs: http://localhost:8001/api/docs

Then, in a separate shell, seed and load data (these run on the host against
the containerized MySQL, since they're one-off scripts, not long-running
services):

```bash
python scripts/generate_sample_data.py --rows 8000
python scripts/run_pipeline.py --sample
python ml/training/train.py
python scripts/seed_database.py
```

### Why non-default ports (3001/8001/3307, not 3000/8000/3306)

Chosen defensively: 3000, 8000, and 3306 are extremely common defaults for
other local projects (this repo's own dev machine had unrelated Dockerized
apps already bound to all three). `docker-compose.yml` and `.env.example`
use `FRONTEND_PORT=3001`, `BACKEND_PORT=8001`, `MYSQL_PORT=3307` so
`docker compose up` doesn't collide with whatever else might be running.
Override any of them in `.env` if they conflict with *your* setup instead.

## Local setup without Docker

Requires Python 3.11+, Node 20+, and a MySQL 8 instance you manage yourself.

```bash
# Backend
cd backend
python -m venv .venv
.venv/Scripts/activate        # or source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8001

# Frontend (separate shell)
cd frontend
npm install
npm run dev   # runs on port 3001 (see package.json)
```

Set `MYSQL_READONLY_USER`/`MYSQL_READONLY_PASSWORD` in `.env` and run
`scripts/sql/create_readonly_user.sql` against your MySQL instance manually
(the Docker path does this automatically via
`docker/mysql/init/01_readonly_user.sh`).

## Environment configuration

See `.env.example` for the full list. Key variables:

- `DATABASE_URL` / `READONLY_DATABASE_URL` — MySQL connection strings (the
  read-only one MUST point at a SELECT-only grant — see
  [security.md](security.md)).
- `JWT_SECRET`, `APP_SECRET_KEY` — generate with
  `python -c "import secrets; print(secrets.token_hex(32))"`, never commit
  real values.
- `LLM_PROVIDER` — `anthropic` | `google` | `none`. Without an API key, the
  AI copilot still runs (tool registry, RAG, guardrails, persistence all
  exercised) but returns a "not configured" message instead of a real LLM
  response — see [ai-system.md](ai-system.md).
- `PROJECT_ROOT` — only needs to be set explicitly inside the Docker backend
  container (`/app`, matching how `knowledge_base/`, `data/`, and `ml/` are
  volume-mounted there); local runs auto-detect the repo root regardless of
  current working directory.

## Health checks

- `GET /health` on the backend — used by the Docker healthcheck.
- MySQL and Redis have their own Docker healthchecks; the backend service
  depends on both being healthy before it starts.

## Rebuilding after a schema change

```bash
cd backend
alembic revision --autogenerate -m "description"
# review the generated migration — autogenerate's downgrade() can need
# manual fixes for FK-backed composite indexes on MySQL, see database.md
alembic upgrade head
```

## Retraining the model

```bash
python ml/training/train.py
```

Registers a new active model version (archiving the previous one) and
re-scores every shipment currently in the database. Takes a few minutes on
an 8K-row sample; SHAP explanation compute time scales with row count and,
for Random Forest specifically, with tree count — see
[ml-system.md](ml-system.md) for why XGBoost is preferred for very large
datasets despite Random Forest sometimes winning on raw metrics at smaller
scale.
