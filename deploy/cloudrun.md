# Cloud Run deploy notes

Region: `asia-southeast1` (Singapore).

## Local substitute (no Cloud Run)

```bash
docker compose -f deploy/docker-compose.free.yml up --build
```

## Deploy (scale-to-zero)

Public demo hub: https://ringbreaker-hub-798018504108.asia-southeast1.run.app

```bash
# Prefer Artifact Registry image after Cloud Build
gcloud run deploy ringbreaker-hub \
  --project ringbreaker-aether-2026 \
  --region asia-southeast1 \
  --image asia-southeast1-docker.pkg.dev/ringbreaker-aether-2026/ringbreaker/hub:0.1.0 \
  --min-instances 0 --max-instances 2 \
  --cpu 1 --memory 1Gi \
  --timeout 300 \
  --allow-unauthenticated \
  --set-env-vars SERVICE_ROLE=hub,GCP_PROJECT=ringbreaker-aether-2026,SEED_HERO=103
```

HMAC: env `RINGBREAKER_HMAC_KEY` on bank services; Secret Manager optional.

## Services (when deploying)

| Service | Image | Auth | Secrets |
|---------|-------|------|---------|
| hub | Dockerfile.hub | `--allow-unauthenticated` | none (no HMAC) |
| bank-a/b/c | Dockerfile.bank | public GET `/console` | HMAC via env (free) or Secret Manager (later) |
