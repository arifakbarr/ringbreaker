#!/usr/bin/env bash
set -euo pipefail

# Refuse paid Cloud Run while FREE_MODE is on (default).
FREE_MODE="${FREE_MODE:-1}"
if [[ "${FREE_MODE}" != "0" ]]; then
  echo "FREE_MODE=${FREE_MODE}: refusing Cloud Run deploy (zero-spend policy)."
  echo "Use: docker compose -f deploy/docker-compose.free.yml up --build"
  echo "To allow GCP deploy after billing+\$0 budget: FREE_MODE=0 ALLOW_CLOUD_RUN=1 bash deploy/deploy.sh"
  exit 0
fi

if [[ "${ALLOW_CLOUD_RUN:-0}" != "1" ]]; then
  echo "Set ALLOW_CLOUD_RUN=1 after confirming open billing and a \$0 budget alert."
  exit 2
fi

PROJECT="${GCP_PROJECT:-ringbreaker-aether-2026}"
REGION="${REGION:-asia-southeast1}"
IMAGE_HUB="${IMAGE_HUB:-asia-southeast1-docker.pkg.dev/${PROJECT}/ringbreaker/hub:0.1.0}"
IMAGE_BANK="${IMAGE_BANK:-asia-southeast1-docker.pkg.dev/${PROJECT}/ringbreaker/bank:0.1.0}"

echo "Deploying scale-to-zero to ${PROJECT} / ${REGION}"

gcloud config set project "${PROJECT}"

# Build (Cloud Build) — requires APIs enabled
gcloud builds submit --config=deploy/cloudbuild.hub.yaml --substitutions=_IMAGE="${IMAGE_HUB}" || {
  echo "Hub Cloud Build failed — ensure image ${IMAGE_HUB} exists"
}
gcloud builds submit --config=deploy/cloudbuild.bank.yaml --substitutions=_IMAGE="${IMAGE_BANK}" || {
  echo "Bank Cloud Build failed — ensure image ${IMAGE_BANK} exists"
}

HMAC_SECRET="${RINGBREAKER_HMAC_KEY:-SYNTHETIC-DEV-KEY-NOT-FOR-PRODUCTION}"

# Hub — public UI + APIs
gcloud run deploy ringbreaker-hub \
  --image "${IMAGE_HUB}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=2 \
  --memory=1Gi \
  --cpu=1 \
  --set-env-vars="FREE_MODE=0,SERVICE_ROLE=hub,GCP_PROJECT=${PROJECT}" \
  --quiet

HUB_URL="$(gcloud run services describe ringbreaker-hub --region "${REGION}" --format='value(status.url)')"
echo "HUB_URL=${HUB_URL}"

for BANK in A B C; do
  bank_lc=$(echo "${BANK}" | tr '[:upper:]' '[:lower:]')
  gcloud run deploy "ringbreaker-bank-${bank_lc}" \
    --image "${IMAGE_BANK}" \
    --region "${REGION}" \
    --platform managed \
    --no-allow-unauthenticated \
    --min-instances=0 \
    --max-instances=1 \
    --memory=512Mi \
    --set-env-vars="FREE_MODE=0,SERVICE_ROLE=bank,BANK_ID=${BANK},RINGBREAKER_HMAC_KEY=${HMAC_SECRET},HUB_URL=${HUB_URL}" \
    --quiet || echo "bank ${BANK} deploy skipped/failed"
done

echo "Smoke: curl -s ${HUB_URL}/readyz"
curl -sf "${HUB_URL}/readyz" || curl -sf "${HUB_URL}/healthz" || curl -sf "${HUB_URL}/health" || true
echo
echo "Done. UI: ${HUB_URL}/  RECORDED: ${HUB_URL}/?mode=RECORDED  crack: ${HUB_URL}/?crack=1"
