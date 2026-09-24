# Security

## Authentication

JWT bearer tokens (`python-jose`, HS256). `POST /api/v1/auth/login` issues a
30-minute access token and a 7-day refresh token; `POST /api/v1/auth/refresh`
rotates both. Passwords hashed with bcrypt via passlib. The frontend stores
tokens in `localStorage` and transparently retries a request once after a
silent refresh on a 401.

## RBAC

Four roles, defined once in `app/auth/permissions.py` as an explicit lookup
table (`ROLE_PERMISSIONS: dict[Role, set[Permission]]`) rather than a rules
engine — with four roles and ~12 permission scopes, a static table is easier
to audit at a glance than a DSL:

| Role | Permissions |
|---|---|
| `admin` | Everything |
| `operations_manager` | Shipments (read/write), suppliers (read/write), alerts (read/write), analytics, AI, models (read), scenarios |
| `analyst` | Shipments/suppliers/alerts (read), analytics, AI, models (read), scenarios |
| `viewer` | Shipments/suppliers/alerts (read), analytics — no AI, no scenarios, no writes |

Enforced via a FastAPI dependency, `require_permission(Permission.X)`, on
every route that needs it — not ad hoc checks scattered through handler
bodies.

### Demo credentials (local development only)

`scripts/seed_database.py` creates:

| Email | Role |
|---|---|
| `admin@supplychain-demo.com` | admin |
| `ops@supplychain-demo.com` | operations_manager |
| `analyst@supplychain-demo.com` | analyst |
| `viewer@supplychain-demo.com` | viewer |

Password for all: `DemoPass123!`. These are seeded plainly for local
development — never reuse this pattern for a real deployment.

## Database access control

Two MySQL users, deliberately separate:

- **App user** (`MYSQL_USER`/`MYSQL_PASSWORD`): full read-write, used by the
  FastAPI backend for everything except AI-generated queries.
- **Read-only user** (`MYSQL_READONLY_USER`/`MYSQL_READONLY_PASSWORD`):
  `GRANT SELECT ON ai_supply_chain.*` only — no INSERT/UPDATE/DELETE/DDL,
  enforced at the database level (`docker/mysql/init/01_readonly_user.sh`).
  This is the **only** connection the AI's text-to-SQL tool uses. Verified
  directly: the read-only user throws `OperationalError` on `CREATE TABLE`.

See [ai-system.md](ai-system.md) for the full text-to-SQL validation layer
that sits in front of even this restricted connection.

## API security

- **CORS**: explicit origin allowlist (`CORS_ALLOWED_ORIGINS`), not `*`.
- **Rate limiting**: `slowapi`, global default (`RATE_LIMIT_PER_MINUTE`,
  120/min) plus a separate, tighter per-user limiter on `/ai/chat`
  (`AI_RATE_LIMIT_PER_MINUTE`, 20/min) since AI calls are far more expensive.
- **Request size limit**: 2MB cap enforced in `RequestContextMiddleware`
  before the body is even parsed.
- **Security headers**: `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy` set on every response.
- **Error sanitization**: the global exception handler
  (`app/common/exceptions.py`) never returns a stack trace or internal detail
  to the client — unhandled exceptions become a generic `INTERNAL_ERROR`
  with a request ID for server-side log correlation.
- **SQL injection**: all app queries go through SQLAlchemy's parameterized
  query builder — no string-formatted SQL anywhere in the application code
  path. The one place raw SQL text reaches the database (the AI's
  text-to-SQL tool) goes through the dedicated validation/allowlist layer
  described above.
- **Audit logging**: login/logout and alert acknowledge/resolve actions
  write to `audit_logs` with user id, action, entity, and details.

## Frontend security

- Tokens never sent to any origin except `NEXT_PUBLIC_API_BASE_URL`.
- No secrets in frontend code — `NEXT_PUBLIC_*` env vars are, by Next.js
  convention, the only ones bundled into client JS, and none of the
  server-side secrets (JWT secret, DB passwords, LLM API keys) use that
  prefix.
- Protected routes via `AuthGuard` (redirects to `/login` if no valid
  session); form validation via `zod` + `react-hook-form` before any
  request is sent.

## Secrets

`.env` is gitignored; `.env.example` documents every variable with no real
values. Docker Compose reads `.env` via `env_file:` — secrets never appear
in `docker-compose.yml` itself. JWT/app secrets in `.env` are generated with
`secrets.token_hex(32)`, not left as placeholder text.

## AI-specific security

Covered in depth in [ai-system.md](ai-system.md): tool allowlisting, safe
text-to-SQL, output schema validation, prompt-injection tripwires, and the
architectural rule that tool/RAG content is always passed to the LLM as data
rather than instructions.
