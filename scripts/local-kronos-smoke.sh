#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8888}"
API_BASE="${2:-http://127.0.0.1:5000}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "==> Kronos local smoke check"
echo "Frontend: $BASE_URL"
echo "Backend:  $API_BASE"

curl --fail --silent --show-error "$BASE_URL/kronos-overview.html" > "$TMP_DIR/overview.html"
curl --fail --silent --show-error "$BASE_URL/xauusd-signal.html" > "$TMP_DIR/xau.html"
curl --fail --silent --show-error "$BASE_URL/btcusd-signal.html" > "$TMP_DIR/btc.html"
curl --fail --silent --show-error "$API_BASE/api/dashboard/public/xauusd-signal" > "$TMP_DIR/xau.json"
curl --fail --silent --show-error "$API_BASE/api/dashboard/public/btcusd-signal" > "$TMP_DIR/btc.json"

python3 - <<'PY' "$TMP_DIR/xau.json" "$TMP_DIR/btc.json"
import json
import sys
from pathlib import Path

for expected_symbol, path_str in [("XAUUSD", sys.argv[1]), ("BTCUSD", sys.argv[2])]:
    payload = json.loads(Path(path_str).read_text())
    assert payload["code"] == 1, f"{expected_symbol}: unexpected code"
    data = payload["data"]
    assert data["symbol"] == expected_symbol, f"{expected_symbol}: wrong symbol"
    assert "bias" in data and "risk" in data and "regime" in data, f"{expected_symbol}: incomplete payload"
    assert isinstance(data.get("recent_closes"), list) and data["recent_closes"], f"{expected_symbol}: missing chart data"
    assert isinstance(data.get("forecast_closes"), list) and data["forecast_closes"], f"{expected_symbol}: missing forecast chart data"
print("✓ JSON payloads validated")
PY

grep -q 'Kronos Overview' "$TMP_DIR/overview.html" || {
  echo "Overview page content check failed" >&2
  exit 1
}

grep -q 'Price Context' "$TMP_DIR/xau.html" || {
  echo "XAUUSD board missing chart section" >&2
  exit 1
}

grep -q 'Price Context' "$TMP_DIR/btc.html" || {
  echo "BTCUSD board missing chart section" >&2
  exit 1
}

echo "✓ Kronos local smoke check passed"
