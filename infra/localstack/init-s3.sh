#!/bin/bash
set -euo pipefail

BUCKET_NAME="${S3_BUCKET_NAME:-cv-uploads}"
REGION="${S3_REGION_NAME:-us-east-1}"

echo "Creating S3 bucket: ${BUCKET_NAME} in ${REGION}"
awslocal s3 mb "s3://${BUCKET_NAME}" --region "${REGION}" 2>/dev/null || true
