# API

Full interactive OpenAPI docs are served at `/api/docs` (Swagger UI) and
`/api/openapi.json` (raw schema) whenever the backend is running — that is
the authoritative, always-up-to-date reference. This document covers the
conventions that apply across every endpoint.

## Base URL and versioning

All endpoints are under `/api/v1/`. A future breaking change would ship as
`/api/v2/` alongside it rather than mutating v1's contract.

## Response envelope

Success:

```json
{ "data": { ... }, "meta": { "page": 1, "page_size": 25, "total": 8000, "total_pages": 320 } }
```

`meta` is omitted for non-paginated responses.

Error:

```json
{ "error": { "code": "SHIPMENT_NOT_FOUND", "message": "Shipment 999999 not found" } }
```

Every error has a stable machine-readable `code` in addition to a
human-readable `message` — the frontend and any script consuming this API
should branch on `code`, not on parsing `message`. Codes in active use
include `NOT_AUTHENTICATED`, `FORBIDDEN`, `VALIDATION_ERROR`,
`SHIPMENT_NOT_FOUND`, `SUPPLIER_NOT_FOUND`, `MODEL_UNAVAILABLE`,
`AI_RATE_LIMIT_EXCEEDED`, `INTERNAL_ERROR`.

## Authentication

`Authorization: Bearer <access_token>` on every request except
`/auth/login` and `/auth/refresh`. A 401 on any other endpoint means the
access token is missing/expired — the frontend's API client automatically
attempts one silent refresh before surfacing the failure.

## Endpoint groups

| Prefix | Purpose |
|---|---|
| `/auth` | login, refresh, me, logout |
| `/dashboard` | KPIs + chart data for the executive overview |
| `/shipments` | list (paginated/filtered), detail, prediction, recommendations |
| `/suppliers` | list, detail, comparison |
| `/analytics` | delays, routes, products, risk (incl. root-cause), kpi-definitions |
| `/alerts` | list, acknowledge, resolve |
| `/scenarios` | what-if simulation |
| `/ai` | copilot chat |
| `/models` | model registry (list, active) |

## Pagination

Query params `page` (1-indexed) and `page_size` (capped at 200 for
shipments, 200 for suppliers). The shipment/supplier list endpoints never
return the full table — the frontend never loads more than one page of
~180K shipments into the browser at once.

## Filtering

Shipment list: `search`, `region`, `market`, `shipping_mode`, `supplier_id`,
`product_category`, `risk_level`, `status`, `date_from`, `date_to`,
`sort_by`, `sort_dir`. Analytics endpoints accept the same
date/region/market/shipping_mode/supplier/category filter set via a shared
`AnalyticsFilters` object, so a filtered dashboard view and a filtered
analytics query stay consistent.

## Errors are never leaked internals

A 500-class failure always returns the generic `INTERNAL_ERROR` envelope —
never a Python traceback or SQL error text. Server-side, the full exception
is logged with a `request_id` that also appears in the `X-Request-ID`
response header, for correlating a user-reported error with server logs.
