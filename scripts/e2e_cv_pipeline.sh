#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
UMS_URL="${UMS_URL:-${BASE_URL}/api/v1}"
POLL_TIMEOUT_SECONDS="${POLL_TIMEOUT_SECONDS:-120}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-3}"
FIXTURE_PDF="${FIXTURE_PDF:-analyze-service/tests/fixtures/cv_samples/cv.pdf}"

if [[ ! -f "${FIXTURE_PDF}" ]]; then
  echo "Fixture PDF not found at ${FIXTURE_PDF}"
  echo "Create a minimal PDF or set FIXTURE_PDF to an existing file."
  exit 1
fi

RANDOM_SUFFIX="$(date +%s)"
EMAIL="cv-e2e-${RANDOM_SUFFIX}@example.com"
PASSWORD="Password123!"
USERNAME="cvuser${RANDOM_SUFFIX}"

echo "Registering user ${EMAIL}"
curl -fsS -X POST "${UMS_URL}/auth/signup" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\",\"username\":\"${USERNAME}\",\"first_name\":\"CV\",\"second_name\":\"E2E\",\"phone_number\":\"+1000${RANDOM_SUFFIX}\"}" >/dev/null

echo "Logging in"
TOKEN_RESPONSE="$(curl -fsS -X POST "${UMS_URL}/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=${EMAIL}&password=${PASSWORD}")"
ACCESS_TOKEN="$(python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])" <<<"${TOKEN_RESPONSE}")"

echo "Uploading CV"
UPLOAD_RESPONSE="$(curl -fsS -X POST "${UMS_URL}/user/me/cv/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -F "file=@${FIXTURE_PDF};type=application/pdf")"
CORRELATION_ID="$(python3 -c "import json,sys; print(json.load(sys.stdin)['correlation_id'])" <<<"${UPLOAD_RESPONSE}")"
echo "Upload accepted, correlation_id=${CORRELATION_ID}"

echo "Polling CV status"
DEADLINE=$((SECONDS + POLL_TIMEOUT_SECONDS))
STATUS="pending"
while (( SECONDS < DEADLINE )); do
  STATUS_RESPONSE="$(curl -fsS "${UMS_URL}/user/me/cv/status?correlation_id=${CORRELATION_ID}" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}")"
  STATUS="$(python3 -c "import json,sys; print(json.load(sys.stdin)['status'])" <<<"${STATUS_RESPONSE}")"
  echo "Current status: ${STATUS}"
  if [[ "${STATUS}" == "completed" ]]; then
    break
  fi
  if [[ "${STATUS}" == "failed" ]]; then
    echo "CV analysis failed: ${STATUS_RESPONSE}"
    exit 1
  fi
  sleep "${POLL_INTERVAL_SECONDS}"
done

if [[ "${STATUS}" != "completed" ]]; then
  echo "Timed out waiting for CV analysis to complete"
  exit 1
fi

echo "E2E CV pipeline completed successfully"
