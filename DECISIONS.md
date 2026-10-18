# DECISIONS.md

Product and engineering choices that differ from brief defaults. Measure before merge when possible.

| Date | Decision | Reason | Measured effect |
|------|----------|--------|-----------------|
| 2026-10-14 | Library-first monorepo `src/ringbreaker` with thin FastAPI wrappers | Matches section 4.1; enables in-process harness | Architecture |
| 2026-10-14 | Four-service Docker layout (hub + banks A/B/C) | Flush IAM/region early (section 18) | Matches preferred topology |
| 2026-10-14 | Hero seed = 103 (median stopped among test seeds 100–119) | A13 after config freeze + E-A | RECORDED pack + default `SEED_HERO` |
| 2026-10-14 | Decision log = JSONL file | Firestore optional stretch (A07) | Local-first persistence |
| 2026-10-14 | `networkx.louvain_communities(seed=…)` instead of python-louvain | Avoid `community` package name clash; matches brief §5 | Stable seeded communities |
| 2026-10-14 | Default `accounts_per_bank=600` for hero | Laptop runtime; scaleable in proof | Hero ~14s wall clock |
| 2026-10-14 | `google-genai` optional extra `[gemini]` | Keep images slim; template path first (I7) | Template always available |
| 2026-10-14 | **FREE_MODE=1** default; Cloud Run gated | Prefer local compose; opt-in cloud spend | `deploy/docker-compose.free.yml` |
| 2026-10-14 | GCP project `ringbreaker-aether-2026` | Demo project in `asia-southeast1` | Public hub live |
| 2026-10-14 | Vite/React replay UI | Judges score UX 10%; motion + brand | Split clock + graph |
| 2026-10-14 | React Bits (BlurText, CountUp, FadeContent, Magnet) | Quiet motion primitives | Wordmark / MYR / Approve affordances |
| 2026-10-14 | Custom SVG wordmark + drafting type system | Avoid generic webfont stacks | Drawn glyphs + ring seal |
| 2026-10-14 | HMAC via env, not Secret Manager | Simpler free/local path | No SM dependency |
| 2026-10-14 | Gemini = template/RECORDED; optional AI Studio key | Offline demo never-cut (I7) | Template always validates |
| 2026-10-14 | Cloud Run `min-instances=0` | Scale-to-zero cost profile | Cold starts accepted |
| 2026-10-14 | RECORDED baked pack + 3s live timeout | Offline demo path | `/?mode=RECORDED` |
| 2026-10-14 | Proof E-A default 5 test seeds (100,101,105,110,115) | Laptop ≤15m; full 100–119 via env | Expand for final deck numbers |
| 2026-10-14 | Gemini runs when `GEMINI_API_KEY` set | AI Studio optional; template fallback | Grounded client with repair |
| 2026-10-14 | Crack demo + feedback + CF UI + E-B…E-G | Finish plan before code freeze | `?crack=1`; full proof harness |
| 2026-10-14 | E-G reports fed≈local+graph when true | Honest PLAN risk #4 | Ablation in `results.json` |
| 2026-10-14 | `deploy.sh` implements gcloud run (gated) | Opt-in cloud deploy | Requires `FREE_MODE=0` |
| 2026-10-17 | Billing budget alert **RM 0**/mo | Cost visibility without hard lock | Alert thresholds only |
| 2026-10-18 | Hub revision with judges' guide + `/v1/proof` + RECORDED | Demo surface complete | Smoke 200 on health/proof/recorded |
