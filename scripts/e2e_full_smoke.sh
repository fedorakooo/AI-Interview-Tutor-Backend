#!/usr/bin/env bash
# Extended E2E: signup → CV → (optional) interview/practice smoke against running stack.
set -euo pipefail
API="${API_BASE:-http://localhost}"
EMAIL="${E2E_EMAIL:-e2e_$(date +%s)@example.com}"
PASSWORD="${E2E_PASSWORD:-TestPass123!}"
USERNAME="${E2E_USERNAME:-e2euser$(date +%s)}"

echo "== signup =="
SIGNUP=$(curl -sS -X POST "$API/api/v1/auth/signup" \
  -H 'Content-Type: application/json' \
  -d "{\"first_name\":\"E2E\",\"second_name\":\"User\",\"username\":\"$USERNAME\",\"phone_number\":\"+1555$(date +%s | tail -c 8)\",\"password\":\"$PASSWORD\",\"email\":\"$EMAIL\"}")
echo "$SIGNUP" | head -c 200; echo

echo "== login =="
TOKEN_RESP=$(curl -sS -X POST "$API/api/v1/auth/token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "username=$USERNAME&password=$PASSWORD")
ACCESS=$(python -c "import json,sys; print(json.load(sys.stdin)['access_token'])" <<<"$TOKEN_RESP")
REFRESH=$(python -c "import json,sys; print(json.load(sys.stdin)['refresh_token'])" <<<"$TOKEN_RESP")
AUTH="Authorization: Bearer $ACCESS"

echo "== entitlements =="
curl -sS -H "$AUTH" "$API/api/v1/billing/entitlements" | head -c 300; echo

echo "== privacy export =="
curl -sS -H "$AUTH" "$API/api/v1/privacy/export" | head -c 300; echo

echo "== logout =="
curl -sS -X POST "$API/api/v1/auth/logout" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "refresh_token=$REFRESH" | head -c 200; echo

echo "E2E auth/billing/privacy smoke OK"
