# EVAL.md

## Seeds

- **Dev:** 0–19 (all tuning)
- **Test:** 100–119 (untouched until final `make proof`)
- **Hero:** median ring-level result among test seeds (programmatic). Current hero seed: **103** (see ASSUMPTIONS A13).

Freeze config by hash before test seeds; record hash in `results/results.json`.

## Reproduce

```bash
make proof   # ≤15 minutes target on a laptop
```

Deterministic sections must be bit-identical across runs for the same seed/config.

## Experiments

E-A scoreboard · E-B network effect · E-C analyst delay · E-D robustness E0–E4 · E-E prevention · E-F agent · E-G ablations.

Report mean ± 95% bootstrap CI, n for every number, negative findings, no cherry-picking.
