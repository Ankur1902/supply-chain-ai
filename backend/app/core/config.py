from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolved relative to this file (backend/app/core/config.py) rather than the
# process's cwd, so `.env` at the repo root is found whether the app/scripts
# are launched from the repo root, from backend/, or via alembic (which
# changes cwd to backend/). Real environment variables (e.g. those injected
# by docker-compose) still take precedence over anything in this file.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_REPO_ROOT_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_REPO_ROOT_ENV_FILE, extra="ignore")

    # --- Application ---
    app_env: Literal["development", "test", "production"] = "development"
    app_debug: bool = True
    app_secret_key: str = "dev-secret-change-me"

    # --- MySQL ---
    database_url: str = "mysql+pymysql://supply_chain_app:change-me@localhost:3306/ai_supply_chain"
    readonly_database_url: str = (
        "mysql+pymysql://supply_chain_ai_ro:change-me-ro@localhost:3306/ai_supply_chain"
    )

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl_seconds: int = 300

    # --- Auth ---
    jwt_secret: str = "dev-jwt-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # --- LLM ---
    llm_provider: Literal["anthropic", "google", "none"] = "none"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    google_api_key: str = ""
    google_model: str = "gemini-2.0-flash"

    # --- AI safety limits ---
    ai_max_tokens_per_request: int = 4096
    ai_tool_call_timeout_seconds: int = 15
    ai_sql_row_limit: int = 500
    ai_sql_timeout_seconds: int = 5
    ai_max_tool_calls_per_turn: int = 6

    # --- ML ---
    model_path: str = "ml/artifacts"
    model_registry_active_version: str = "latest"

    # --- Vector DB ---
    vector_db_path: str = "knowledge_base/chroma_db"
    vector_db_collection: str = "supply_chain_kb"

    # --- CORS ---
    cors_allowed_origins: str = "http://localhost:3000"

    # --- Rate limiting ---
    rate_limit_per_minute: int = 120
    ai_rate_limit_per_minute: int = 20

    # Base directory that relative paths above (model_path, vector_db_path,
    # and the knowledge_base/ markdown corpus) are resolved against.
    # Defaults to the actual repo root for local/non-Docker runs (correct
    # regardless of whether the process's cwd is the repo root or backend/,
    # e.g. when alembic changes cwd). The backend's docker-compose service
    # overrides this to /app, matching how ./knowledge_base, ./data, and
    # ./ml are volume-mounted there. See docs/decisions.md.
    project_root: str = str(_REPO_ROOT)

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    def resolve_path(self, relative_or_absolute: str) -> Path:
        # Paths persisted in the DB (e.g. model_versions.artifact_path) may have
        # been written on Windows with backslashes; normalize so they resolve
        # on Linux (Docker) too.
        p = Path(relative_or_absolute.replace("\\", "/"))
        return p if p.is_absolute() else Path(self.project_root) / p

    @property
    def resolved_model_path(self) -> Path:
        return self.resolve_path(self.model_path)

    @property
    def resolved_vector_db_path(self) -> Path:
        return self.resolve_path(self.vector_db_path)

    @property
    def resolved_knowledge_base_dir(self) -> Path:
        return self.resolve_path("knowledge_base")


@lru_cache
def get_settings() -> Settings:
    return Settings()
