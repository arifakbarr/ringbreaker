# RUNBOOK.md

## Local

```bash
pip install -e ".[dev]"
make test
make hero
uvicorn ringbreaker.hub.service:app --port 8080
```

## Deterministic reset

Set `SEED_HERO` (default **103**, median hero). In UI kiosk mode, `R` resets. Harness uses fixed seeds only.

## Fallbacks (I7)

1. **RECORDED mode** — UI loads `/recorded/demo_pack.json` if live APIs fail or exceed 3s. Force with `?mode=RECORDED`. Rebuild via `make record` (also runs before `make ui-build`).
2. **Template case file** — if Gemini fails validation; UI shows `template` / `llm` / `RECORDED` tag.
3. **Decision chain** — `make verify-decisions` after approve.
4. Smoke: `bash scripts/smoke.sh https://<hub-url>`

## Crack demo (≤2 min)

1. Open `http://127.0.0.1:8080/?crack=1` (or press **C**).
2. Autoplays at 30× to detection → opens case → approves → shows stopped MYR toast.
3. **R** resets. Works with `?mode=RECORDED` offline.

## Judges' guide

First visit opens a guide (what we're building · how it works · evidence · limits · controls) and holds the replay until **Start the replay**. Reopen with **?** or the *What is this?* / *Evidence* buttons. `?intro=0` skips it, `?intro=1` forces it. Evidence numbers come from `GET /v1/proof` (a slim copy of `results/results.json`); RECORDED mode reads `/recorded/proof.json`.

Playback stops at the hub alert so the analyst step is never skipped. The replay carries two timelines: `events` (with the freeze applied) and `today_events` (no intervention). Regenerate both with `python -m ringbreaker.harness.record_demo --force`; packs recorded before `today_events` existed render "Today" without cash-outs.

## Docker

`docker compose -f deploy/docker-compose.free.yml up --build` builds the UI inside the hub image (multi-stage `deploy/Dockerfile.hub`), so http://localhost:8080/ serves the app.

## Proof

```bash
# Full test seeds 100–119 + E-B…E-G (laptop ~minutes)
make proof

# Faster iterate
PROOF_QUICK=1 make proof
```

Deck/video numbers **only** from `results/results.json`.

## Deploy

See `deploy/cloudrun.md`. Requires `GCP_PROJECT`, billing, IAM. Hub public; banks: HMAC secret on bank SA only.

## Known failure modes

| Symptom | Fix |
|---------|-----|
| Cold start / empty state | min=max instances 1; avoid multi-instance |
| Gemini timeout | template fallback; cache by ring version |
| Model ID missing | change `GEMINI_MODEL`; never use 2.5 (I9) |
| Region model unavailable | fall back `GEMINI_LOCATION=global` |
