# PRIVACY.md

**SYNTHETIC DATA · SIMULATION** · Privacy by design on pseudonymised data — not a compliance claim.

## Boundaries (enforced in code)

| Boundary | Rule |
|----------|------|
| B1 Bank | Raw transactions/IDs never leave. Outbound: model updates, beacons, edge events only. `extra=forbid` + pattern scan. |
| B2 Key | HMAC key in Secret Manager; bank SAs only. Hub SA cannot read it. |
| B3 Gemini | Allowlisted aliased fields only (`ACC-01`…). Tool outputs structured. |
| B4 Human | Freeze/hold only after analyst decision recorded. |

## Tokenisation

`token = base32(HMAC-SHA256(K, epoch || 0x1F || type || 0x1F || normalised_value))[:22]`

Types: `account`, `device`, `ip`, `phone`. Hub never holds `K`.

## Privacy ledger

Per bank: messages/bytes by type, tokens sent, raw fields sent (**must be 0**).

## Limits

- Shared-key HMAC ≠ PSI. Colluding member + hub could brute-force low-entropy IDs.
- Production: OPRF PSI + secure aggregation, neutral operator, legal review.
- Tokenised IDs remain personal data under PDPA/GDPR.
