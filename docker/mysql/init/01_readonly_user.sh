#!/bin/bash
# =============================================================================
# Read-only MySQL user for the AI analytics / Text-to-SQL layer.
#
# Runs automatically on first container init (docker-entrypoint-initdb.d).
# The AI copilot NEVER connects with the app's read-write credentials — this
# user can only SELECT. It cannot INSERT, UPDATE, DELETE, or run any DDL.
#
# Defense in depth: this DB-level grant is the outer boundary. The app-layer
# SQL validator (backend/app/ai/sql_guard.py) additionally enforces a
# table/column allowlist, row limits, single-statement parsing, and query
# timeouts before any AI-generated SQL reaches this connection.
# See docs/security.md.
# =============================================================================
set -euo pipefail

mysql -u root -p"${MYSQL_ROOT_PASSWORD}" <<-EOSQL
    CREATE USER IF NOT EXISTS '${MYSQL_READONLY_USER}'@'%' IDENTIFIED BY '${MYSQL_READONLY_PASSWORD}';
    GRANT SELECT ON \`${MYSQL_DATABASE}\`.* TO '${MYSQL_READONLY_USER}'@'%';
    FLUSH PRIVILEGES;
EOSQL

echo "Created read-only MySQL user '${MYSQL_READONLY_USER}' with SELECT-only privileges on ${MYSQL_DATABASE}."
