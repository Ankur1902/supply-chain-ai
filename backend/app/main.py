"""
FastAPI application entrypoint.

IMPORT ORDER WARNING (Windows-specific — see docs/decisions.md):
`chromadb` must be imported before `xgboost`/`shap` anywhere in this
process. Chromadb (used by app/ai/rag.py) eagerly touches an
onnxruntime-backed default embedding function at import time, and
onnxruntime's bundled native runtime conflicts with xgboost's on Windows
if xgboost is loaded into the process first — the second import then
crashes with a DLL initialization error. We never hit this in practice
(app/ml/inference.py imports shap/xgboost lazily, inside functions, not at
module load time) but importing chromadb first here removes any doubt,
regardless of which router happens to run first.
"""

import chromadb  # noqa: F401,E402 — see module docstring; must precede any xgboost/shap import

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError

from app.api.v1 import ai, alerts, analytics, auth, dashboard, models, scenarios, shipments, suppliers
from app.common.exceptions import (
    AppError,
    app_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware

settings = get_settings()
configure_logging(settings.app_debug)

limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.rate_limit_per_minute}/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="AI Supply Chain Intelligence Platform API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(dashboard.router, prefix=API_PREFIX)
app.include_router(shipments.router, prefix=API_PREFIX)
app.include_router(suppliers.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)
app.include_router(alerts.router, prefix=API_PREFIX)
app.include_router(scenarios.router, prefix=API_PREFIX)
app.include_router(ai.router, prefix=API_PREFIX)
app.include_router(models.router, prefix=API_PREFIX)


@app.get("/health")
def health():
    return {"status": "ok"}
