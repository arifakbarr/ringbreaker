# ASSUMPTIONS.md

Defaults taken for the build. Update when humans confirm.

| ID | Assumption | Default | Status |
|----|------------|---------|--------|
| A01 | Submission deadline | Evening Oct 17, 2026 (official site Oct 18; Oct 18 buffer only) | Assumed |
| A02 | Cost policy | **FREE_MODE=1** — minimize spend; **RM 0** budget alert; Cloud Run scale-to-zero | Confirmed |
| A03 | Gemini 4 Argon | Unavailable for default path; optional deep-review only if smoke passes | Assumed |
| A04 | Default Gemini model | `gemini-3.8-flash` via config `GEMINI_MODEL` (I9: never 2.5) | Assumed |
| A05 | Gemini location | Prefer `asia-southeast1`, fall back to `global` | Assumed |
| A05b | Gemini access while free | Template + RECORDED (RM 0). Optional Google AI Studio free `GEMINI_API_KEY` — not Vertex | Confirmed |
| A06 | Product name / branding | Ringbreaker | Assumed |
| A07 | Decision persistence | Local JSONL file — Firestore off in FREE_MODE | Confirmed |
| A08 | Analyst delay (harness default) | 120 s | Per brief |
| A09 | Freeze budget k | 6 | Per brief |
| A10 | Victim compliance rate (prevention) | 70% | Per brief |
| A11 | Account-level FPR operating point | 0.5% on dev seeds | Per brief |
| A12 | HMAC key | Env `RINGBREAKER_HMAC_KEY` only while free (no Secret Manager) | Confirmed |
| A13 | Hero seed | Median rule over test seeds after config freeze; interim seed was 101, now **103** | Confirmed |
| A14 | Banks D/E | Exist in world; never send events to hub | Per brief |
| A15 | GCP project | `ringbreaker-aether-2026` (asia-southeast1) | Confirmed |
| A16 | Malay warning review | Templates EN/MS polished + rubric tests; video/PPT done — BM copy accepted for submit | Confirmed |
| A17 | National fraud initiatives | Not cited until human verifies | Open for humans |
| A18 | Service topology | Four Cloud Run services preferred; local compose fallback | Confirmed |
| A19 | gcloud CLI | Installed and authenticated for the demo project | Confirmed |
| A20 | Billing | Budget alert **RM 0**/mo on the demo project (alerts only — not a hard spend lock) | Confirmed |

## Optional

- Free [Google AI Studio](https://aistudio.google.com/apikey) key → `GEMINI_API_KEY` (template fallback works without it).