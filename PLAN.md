# Ringbreaker — Build Plan

**Brief:** AI Builder Cup 2026 · BFSI · v1 · Oct 14, 2026  
**Code freeze:** morning of Oct 17 · **Submit:** evening Oct 17 · **Buffer:** Oct 18 only

## Ordered tasks (Tier 1 → Gate G1)

| ID | Task | Depends on | Acceptance |
|----|------|------------|------------|
| T1.1 | Repo, tooling, Makefile, Docker, hello Cloud Run (4 services) | — | `make test` skeleton green; four images build; hello deploy attempted |
| T1.2 | Simulator: world, rings, hero, interventions, counterfactual | T1.1 | Seeded `simulate()`; hero money out ~T+38m; lookalikes present |
| T1.3 | Features, local LR, FedAvg, baseline rows 1/2/3/5 | T1.2 | Dev-seed metrics; same FPR operating point |
| T1.4 | Tokenisation, schemas (`extra=forbid`), bank services + ledger | T1.2 | Contract scan: zero raw IDs outbound |
| T1.5 | Hub graph, Louvain candidates, ring score + components | T1.3, T1.4 | Hero ring ALERT; components stored |
| T1.6 | Planner (≤k) + graded tiers T0–T4 | T1.5 | Expectation vs simulator actual logged |
| T1.7 | Payee-risk O(1) + live_ring_index | T1.5 | p95 instrumented; no LLM in path |
| T1.8 | `make hero` headless + deploy | T1.6, T1.7 | Ringgit stopped + time-to-detect in output |

**Gate G1 (end Oct 15):** headless hero metrics; local-only vs fed+graph on dev; all services deployed.

### Status (G1)

- T1.2–T1.8 library path green: `make test`, `make hero` → ring alert, stopped MYR logged, payee p95 ≪ 100ms.
- Docker images `ringbreaker-hub:0.1.0` / `ringbreaker-bank:0.1.0` build.
- Active GCP project: `ringbreaker-aether-2026` (asia-southeast1).
- **FREE_MODE=1** by default — local compose; Cloud Run only when `FREE_MODE=0 ALLOW_CLOUD_RUN=1`.

## Tier 2 (only after G1) — Gate G2 end Oct 16

T2.1 Gemini investigator + grounding + template · T2.2 notices + leak test · T2.3 UI replay/case/approve · T2.4 victim warning · T2.5 full `make proof` · T2.6 decision hash chain · T2.7 RECORDED mode + backup recording.

### Status (G2)

- T2.1–T2.7 complete: template/Gemini investigator, notices, UI replay/approve, victim warnings, proof harness, decision hash chain, RECORDED fallback.

## Tier 3 (only after G2) — morning Oct 17

Privacy polish, crack demo, BM polish, counterfactual UI, feedback loop → tag `demo-freeze`.

### Status (G3)

- Privacy footer + `/v1/privacy`; crack demo (`?crack=1`); BM templates (A16 sign-off before video); counterfactual UI; feedback loop; E-A…E-G proof; median hero **103**; tag `demo-freeze`.
- Remaining for submit: public hub smoke, deck/video assets (held outside the repo).

## Cut order (if behind)

crack demo → feedback loop → Malay polish → E4/adaptive → network-effect → hash verify script → victim UI (keep payee-risk).

**Never cut:** hero replay, grounded case+fallback, planner/ringgit stopped, scoreboard, SYNTHETIC badge, RECORDED mode.

## Top risks

1. **Time** — Strict tier gates; library-first single package.
2. **Gemini unavailability** — Template fallback + RECORDED from day one of Tier 2 (I7).
3. **Fed adds little beyond graph** — Report honestly; credit graph (section 21).
4. **Cold starts / state** — Cloud Run scale-to-zero; asia-southeast1.

## Working rules

- Invariants I1–I10 fixed; latitude logged in DECISIONS.md.
- Numbers for deck/video only from `results/results.json`.
- Main always deployable.
