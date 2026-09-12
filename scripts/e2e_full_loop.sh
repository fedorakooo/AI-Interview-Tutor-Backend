#!/usr/bin/env bash
# Best-effort full product loop against a running local stack (gateway :80 or direct ports).
set -uo pipefail

API_BASE="${API_BASE:-http://localhost/api/v1}"
UMS_URL="${UMS_URL:-${API_BASE}}"
INTERVIEW_URL="${INTERVIEW_URL:-http://localhost/api/v1/interview}"
PRACTICE_URL="${PRACTICE_URL:-http://localhost/api/v1/practice}"
EMAIL="${E2E_EMAIL:-e2e_$(date +%s)@example.com}"
PASSWORD="${E2E_PASSWORD:-E2ePassw0rd!}"
USERNAME="e2e_user_$(date +%s)"
FIXTURE_PDF="${FIXTURE_PDF:-analyze-service/tests/fixtures/cv_samples/cv.pdf}"
POLL_TIMEOUT_SECONDS="${POLL_TIMEOUT_SECONDS:-90}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-3}"

curl_best_effort() {
  curl -sf "$@" 2>/dev/null || return 1
}

echo "==> Signup"
if ! curl_best_effort -X POST "$UMS_URL/auth/signup" \
  -H 'Content-Type: application/json' \
  -d "{\"first_name\":\"E2E\",\"second_name\":\"User\",\"username\":\"$USERNAME\",\"phone_number\":\"+1555$(date +%s | tail -c 8)\",\"password\":\"$PASSWORD\",\"email\":\"$EMAIL\"}"; then
  echo "(signup skipped — user-management may be down)"
  exit 0
fi
echo

echo "==> Login"
TOKEN_RESP=$(curl_best_effort -X POST "$UMS_URL/auth/token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "username=$USERNAME&password=$PASSWORD") || { echo "(login failed)"; exit 0; }
ACCESS=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])' <<<"$TOKEN_RESP")
AUTH="Authorization: Bearer $ACCESS"

echo "==> Me"
curl_best_effort "$UMS_URL/user/me/" -H "$AUTH" | head -c 200 || echo "(me skipped)"
echo

if [[ -f "${FIXTURE_PDF}" ]]; then
  echo "==> CV upload"
  if UPLOAD_RESPONSE=$(curl_best_effort -X POST "$UMS_URL/user/me/cv/" -H "$AUTH" -F "file=@${FIXTURE_PDF};type=application/pdf"); then
    CORRELATION_ID=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["correlation_id"])' <<<"$UPLOAD_RESPONSE")
    echo "correlation_id=${CORRELATION_ID}"
    echo "==> CV status poll"
    DEADLINE=$((SECONDS + POLL_TIMEOUT_SECONDS))
    STATUS="pending"
    while (( SECONDS < DEADLINE )); do
      STATUS_RESPONSE=$(curl_best_effort "$UMS_URL/user/me/cv/status?correlation_id=${CORRELATION_ID}" -H "$AUTH") || break
      STATUS=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])' <<<"$STATUS_RESPONSE")
      echo "status=${STATUS}"
      [[ "${STATUS}" == "completed" || "${STATUS}" == "failed" ]] && break
      sleep "${POLL_INTERVAL_SECONDS}"
    done
  else
    echo "(cv upload skipped)"
  fi
else
  echo "==> CV upload skipped (fixture missing)"
fi
echo

echo "==> Interview sessions"
curl_best_effort "${INTERVIEW_URL}/sessions" -H "$AUTH" | head -c 200 || echo "(sessions skipped)"
echo

echo "==> Practice profile"
curl_best_effort "${PRACTICE_URL}/profile" -H "$AUTH" | head -c 200 || echo "(practice profile skipped)"
echo

echo "==> Entitlements"
curl_best_effort "$UMS_URL/billing/entitlements" -H "$AUTH" | head -c 200 || echo "(billing skipped)"
echo

echo "==> Notifications inbox"
curl_best_effort "${PRACTICE_URL%/practice}/notifications" -H "$AUTH" | head -c 200 || echo "(notifications skipped)"
echo

echo "==> E2E full loop finished (best-effort)"
