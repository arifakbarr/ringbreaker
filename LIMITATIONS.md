# LIMITATIONS.md

Honest limits for README, UI footer, deck, and video.

## Privacy (by design, not compliance)

- Shared-key HMAC tokens are **pseudonymised**, not anonymous. They remain personal data under PDPA/GDPR.
- This is **not** private set intersection. A colluding consortium member plus the hub could brute-force low-entropy identifiers.
- Production roadmap: OPRF-based PSI, secure aggregation for model updates, neutral operator, legal review.
- We claim **privacy by design on pseudonymised data**. Never: GDPR/PDPA compliant, anonymous, unbreakable, secure by default.

## Simulation

- All data is **synthetic**. Numbers are from a seeded simulator, not predictions for real banks.
- No real bank integrations. Banks D/E do not participate in the hub.
- Lookalike accounts exist by design (~1.5%); false freezes are measured and reported.

## Product

- Freezes/holds require **human analyst approval** (recommends, never automatically freezes).
- Gemini path always has a validated **template fallback** and **RECORDED** UI mode.
- Federated learning may add little beyond the token graph; report scoreboard honestly.
- Optional DP is an ablation with parameters, not a formal privacy guarantee unless an accountant is implemented.
