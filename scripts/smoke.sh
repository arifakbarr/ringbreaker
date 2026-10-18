#!/usr/bin/env bash
# Smoke test against public hub URL. Exit non-zero on any failure.
set -euo pipefail

BASE_URL="${1:-${HUB_URL:-http://127.0.0.1:8080}}"
echo "smoke against ${BASE_URL}"

# Prefer /readyz + /health — some Google edges 404 bare /healthz
curl -fsS "${BASE_URL}/readyz" | grep -q ready
curl -fsS "${BASE_URL}/health" | grep -q '"status"'
curl -fsS "${BASE_URL}/" >/dev/null

# Payee-risk deterministic path
curl -fsS -X POST "${BASE_URL}/v1/payee-risk" \
  -H 'content-type: application/json' \
  -d '{"schema_version":"payee.v1","payer_bank":"B","payee_token":"TESTTOKEN000000000000","amount_myr":100,"ts":"0"}' \
  | grep -q tier

# Cases + decision (RECORDED/template path)
CASE_ID=$(curl -fsS "${BASE_URL}/cases" | python -c "import sys,json; d=json.load(sys.stdin); print(d['cases'][0]['case_id'] if d.get('cases') else '')")
if [[ -n "${CASE_ID}" ]]; then
  curl -fsS "${BASE_URL}/cases/${CASE_ID}" | grep -q case_id
  curl -fsS -X POST "${BASE_URL}/cases/${CASE_ID}/decision" \
    -H 'content-type: application/json' \
    -d '{"analyst_id":"smoke","accounts":[]}' | grep -q decision
fi

curl -fsS "${BASE_URL}/v1/hero" | grep -q hero
echo "smoke ok"
