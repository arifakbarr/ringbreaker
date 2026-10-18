# Ringbreaker

**SYNTHETIC DATA · SIMULATION**

Privacy-preserving hub for authorised push payment (APP) mule-ring detection across banks — Google Cloud AI Builder Cup 2026 · BFSI track.

Mule money is a race measured in minutes. Ringbreaker answers two moments in the golden hour: **prevention** (deterministic payee-risk lookup) and **interception** (cross-bank graph + planner + Gemini investigator with human approval). The hub never holds the HMAC key; Gemini never sees raw identifiers; nothing freezes without an analyst.

> All figures are **in our simulation**. We claim **privacy by design on pseudonymised data**, not legal compliance. Not production-ready.

## Quick start (local)

```bash
python -m pip install -e ".[dev]"
make test
make hero          # writes results/hero.json + results/replay.json
uvicorn ringbreaker.hub.service:app --port 8080
```

Or Docker (builds UI inside the hub image):

```bash
docker compose -f deploy/docker-compose.free.yml up --build
```

Then open:

| URL | Purpose |
|-----|---------|
| http://127.0.0.1:8080/ | Live demo (first visit shows judges' guide) |
| http://127.0.0.1:8080/?crack=1 | ≤2 min autoplay demo |
| http://127.0.0.1:8080/?mode=RECORDED | Offline baked pack |
| http://127.0.0.1:8080/?intro=0 | Skip guide |

Public hub (scale-to-zero): https://ringbreaker-hub-798018504108.asia-southeast1.run.app

## Architecture

Four Cloud Run services preferred (`hub`, `bank-a`, `bank-b`, `bank-c`) wrapping one Python package `ringbreaker`. The harness runs the same library in-process.

See `PLAN.md`, `ASSUMPTIONS.md`, `DECISIONS.md`, `LIMITATIONS.md`, `PRIVACY.md`, `EVAL.md`, `RUNBOOK.md`.

## Results

Numbers for the deck/video **only** from `results/results.json` (or `GET /v1/proof`). Never hand-type metrics.

## License

Apache-2.0
