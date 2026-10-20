#!/usr/bin/env bash
# Fail fast when this stack's host ports are already taken by another process.
#
# Why this exists: compose.dev.yml binds PROJECT_N3_WEB_API_PORT with a default
# of 8001, and Docker Compose *merges* that ports list with the
# compose.testing.yml override instead of replacing it. With the variable unset,
# the api is asked to bind 8001 and 8002 at once. When the main project stack
# already owns 8001 the create fails with "Bind for 0.0.0.0:8001 failed: port is
# already allocated" — and it fails *after* the container object is created, so
# the stack is left down with a confusing half-created state.
#
# Usage: check-ports.sh <port>:<VAR_NAME> [<port>:<VAR_NAME> ...]
set -euo pipefail

failed=0

for spec in "$@"; do
  port="${spec%%:*"
  variable="${spec#*:}"

  # A listener owned by this stack is not a conflict; `up -d` is idempotent.
  if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -q "LISTEN.*:${port} "; then
    echo "ERROR: host port ${port} is already in use by another process."
    echo "       Set ${variable} in .env (see the port note there) or free the port."
    ss -ltnp 2>/dev/null | grep "LISTEN.*:${port} " | sed 's/^/       /' || true
    failed=1
  fi
done

if [ "$failed" -ne 0 ]; then
  exit 1
fi
