#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
COMPOSE_CMD=(docker compose)

log() { printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
fail() { printf '\n❌ %s\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

show_logs() {
  log "Recent Docker logs"
  "${COMPOSE_CMD[@]}" logs --no-color --tail 80 api frontend || true
}

on_error() {
  local rc=$?
  printf '\n❌ Setup failed. Showing diagnostics.\n' >&2
  if command -v docker >/dev/null 2>&1; then
    (cd "$ROOT_DIR" && "${COMPOSE_CMD[@]}" ps) || true
    show_logs
  fi
  exit "$rc"
}

trap on_error ERR

cd "$ROOT_DIR"

need_cmd docker
need_cmd python3
need_cmd curl

docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required"

if [[ ! -f ".env" ]]; then
  fail ".env is missing. Create it before running this script."
fi

grep -q '^DATABASE_URL=' .env || fail ".env must define DATABASE_URL"
grep -q '^ITR_DATA_DIR=' .env || fail ".env must define ITR_DATA_DIR"

log "Validating local Python environment"
if [[ ! -d ".venv" ]]; then
  log "Creating Python virtual environment"
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel >/dev/null
python -m pip install -r backend/requirements.txt >/dev/null
python -m py_compile backend/app/main.py

if find "$ROOT_DIR" -path "$ROOT_DIR/frontend/node_modules" -prune -o \( -name 'test_*.py' -o -name '*_test.py' \) -print | grep -q .; then
  log "Running Python tests"
  python -m pytest -q
else
  log "No Python tests found"
fi

log "Validating frontend dependencies"
if [[ ! -d "frontend/node_modules" ]]; then
  log "Installing frontend dependencies"
  if [[ -f "frontend/package-lock.json" ]]; then
    (cd "$FRONTEND_DIR" && npm ci --no-fund --no-audit)
  else
    (cd "$FRONTEND_DIR" && npm install --no-fund --no-audit)
  fi
fi

log "Building frontend"
(cd "$FRONTEND_DIR" && npm run build)

# The frontend container runs Next.js in dev mode. A production .next from npm build
# can conflict with dev chunks when source is bind-mounted into the container.
rm -rf "$FRONTEND_DIR/.next"

log "Resetting Docker stack"
"${COMPOSE_CMD[@]}" down --remove-orphans >/dev/null 2>&1 || true

log "Building and starting Docker stack"
"${COMPOSE_CMD[@]}" up -d --build --remove-orphans

wait_for_http() {
  local url="$1"
  local label="$2"
  local attempts=60
  local delay=2
  local i=1
  while (( i <= attempts )); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      log "$label is responding"
      return 0
    fi
    sleep "$delay"
    i=$((i + 1))
  done
  fail "$label did not become ready"
}

log "Waiting for services"
wait_for_http "http://localhost:8000/health" "Backend health"
wait_for_http "http://localhost:3000" "Frontend"

log "Verifying Docker processes"
running_services="$("${COMPOSE_CMD[@]}" ps --services --filter status=running | tr -d '\r')"
grep -qx 'api' <<<"$running_services" || fail "API container is not running"
grep -qx 'frontend' <<<"$running_services" || fail "Frontend container is not running"

log "Running backend smoke checks"
python3 - <<'PY'
import json
import sys
from urllib.request import urlopen
from urllib.error import HTTPError

checks = [
    ("http://localhost:8000/health", lambda d: d.get("status") == "ok", False),
    ("http://localhost:8000/api/cases/1", lambda d: d.get("ok") is True and "case" in d, False),
    ("http://localhost:8000/api/documents/case/1", lambda d: d.get("ok") is True and "documents" in d, False),
    ("http://localhost:8000/api/cases/1/progress", lambda d: d.get("ok") is True and "progress" in d, False),
    ("http://localhost:8000/api/cases/1/review-checks", lambda d: d.get("ok") is True and "checks" in d, False),
    ("http://localhost:8000/api/cases/1/residency", lambda d: d.get("ok") is True and "residency" in d, False),
    ("http://localhost:8000/api/cases/1/tax-credits", lambda d: d.get("ok") is True and "credits" in d, False),
    ("http://localhost:8000/api/cases/1/tasks", lambda d: d.get("ok") is True and "tasks" in d, False),
    ("http://localhost:8000/api/cases/1/properties", lambda d: d.get("ok") is True and "properties" in d, False),
    ("http://localhost:8000/api/cases/1/audit-history", lambda d: d.get("ok") is True and "history" in d, False),
    ("http://localhost:8000/api/cases/1/reconciliation", lambda d: d.get("ok") is True and "reconciliation" in d, False),
    ("http://localhost:8000/api/cases/1/reports/calculation", lambda d: d.get("ok") is True and "report" in d, False),
    ("http://localhost:8000/api/cases/1/reports/form-summary", lambda d: d.get("ok") is True and "report" in d, False),
    ("http://localhost:8000/api/portal/export?case_id=1&format=json", lambda d: d.get("ok") is True, True),
]

for url, predicate, optional in checks:
    try:
        with urlopen(url, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        if optional and e.code == 404:
            print(f"optional endpoint unavailable (skipped): {url}")
            continue
        raise
    if not predicate(payload):
        raise SystemExit(f"Smoke check failed for {url}: {payload}")

print("backend smoke checks passed")
PY

log "Validating database access from API container"
"${COMPOSE_CMD[@]}" exec -T api python - <<'PY'
from sqlalchemy import text
from backend.app.main import SessionLocal, TaxCase

if SessionLocal is None:
    raise SystemExit("SessionLocal is not configured")

with SessionLocal() as session:
    session.execute(text("SELECT 1"))
    count = session.query(TaxCase).count()
    print(f"tax_cases={count}")
PY

log "Checking logs for startup errors"
if "${COMPOSE_CMD[@]}" logs --no-color --since 5m api frontend | grep -E 'Traceback|ModuleNotFoundError|No inspection system|Internal Server Error|UnhandledPromiseRejection|FATAL|panic' >/dev/null; then
  fail "Error patterns found in Docker logs"
fi

log "All validation checks passed"
printf '\n✅ Application is up and healthy\n'
printf '   Frontend: http://localhost:3000\n'
printf '   Backend:  http://localhost:8000\n'
printf '   Docs:     http://localhost:8000/docs\n'
