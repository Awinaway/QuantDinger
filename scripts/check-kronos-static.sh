#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_ROUTE="$ROOT_DIR/backend_api_python/app/routes/dashboard.py"

required_files=(
  "$ROOT_DIR/frontend/dist/xauusd-signal.html"
  "$ROOT_DIR/frontend/dist/btcusd-signal.html"
  "$ROOT_DIR/frontend/dist/kronos-overview.html"
  "$ROOT_DIR/frontend/dist/index.html"
  "$BACKEND_ROUTE"
)

echo "==> Kronos static smoke check"

for file in "${required_files[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "Missing required file: $file" >&2
    exit 1
  fi
done

grep -q '/api/dashboard/public/xauusd-signal' "$ROOT_DIR/frontend/dist/xauusd-signal.html" || {
  echo "XAUUSD board is missing its public API hook" >&2
  exit 1
}

grep -q '/api/dashboard/public/btcusd-signal' "$ROOT_DIR/frontend/dist/btcusd-signal.html" || {
  echo "BTCUSD board is missing its public API hook" >&2
  exit 1
}

grep -q '/api/dashboard/public/xauusd-signal' "$ROOT_DIR/frontend/dist/kronos-overview.html" || {
  echo "Overview is missing XAUUSD API usage" >&2
  exit 1
}

grep -q '/api/dashboard/public/btcusd-signal' "$ROOT_DIR/frontend/dist/kronos-overview.html" || {
  echo "Overview is missing BTCUSD API usage" >&2
  exit 1
}

grep -q '@dashboard_bp.route("/public/xauusd-signal"' "$BACKEND_ROUTE" || {
  echo "Backend route for public XAUUSD signal is missing" >&2
  exit 1
}

grep -q '@dashboard_bp.route("/public/btcusd-signal"' "$BACKEND_ROUTE" || {
  echo "Backend route for public BTCUSD signal is missing" >&2
  exit 1
}

echo "✓ Kronos static smoke check passed"
