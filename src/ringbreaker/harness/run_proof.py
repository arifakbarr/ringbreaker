"""Full proof pack — config freeze + E-A…E-G + median hero (Gate G2/G3)."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from ringbreaker import SYNTHETIC_BADGE, __version__
from ringbreaker.config import get_settings
from ringbreaker.harness.experiments import (
    run_eb_network,
    run_ec_delay,
    run_ed_evasion,
    run_ee_prevention,
    run_ef_agent,
    run_eg_ablations,
)
from ringbreaker.pipeline import run_hero


ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "results"


def _config_blob(settings: Any) -> dict[str, Any]:
    return {
        "seed_hero": settings.seed_hero,
        "analyst_delay_s": settings.analyst_delay_s,
        "freeze_budget_k": settings.freeze_budget_k,
        "account_fpr": settings.account_fpr,
        "share_threshold": settings.share_threshold,
        "watch_threshold": settings.watch_threshold,
        "alert_threshold": settings.alert_threshold,
        "lookalike_share": settings.lookalike_share,
        "compliance_rate": settings.compliance_rate,
        "prompt_version": settings.prompt_version,
        "hmac_epoch": settings.hmac_epoch,
    }


def _config_hash(cfg: dict[str, Any]) -> str:
    raw = json.dumps(cfg, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _parse_seeds(env: str, default: list[int]) -> list[int]:
    raw = os.getenv(env, "").strip()
    if not raw:
        return default
    return [int(x) for x in raw.split(",") if x.strip()]


def _bootstrap_ci(values: list[float], n_boot: int = 400, seed: int = 0) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "ci95_low": None, "ci95_high": None, "n": 0}
    arr = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = sorted(
        float(np.mean(rng.choice(arr, size=len(arr), replace=True))) for _ in range(n_boot)
    )
    return {
        "mean": float(np.mean(arr)),
        "ci95_low": means[int(0.025 * (n_boot - 1))],
        "ci95_high": means[int(0.975 * (n_boot - 1))],
        "n": len(values),
    }


def run_ea_scoreboard(
    seeds: list[int],
    *,
    accounts_per_bank: int,
    config_hash: str,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for s in seeds:
        print(f"[E-A] seed={s} …", flush=True)
        h = run_hero(s, accounts_per_bank=accounts_per_bank, write_replay=False)
        rows.append(
            {
                "seed": s,
                "ring_alerted": h.ring_alerted,
                "time_to_detect_s": h.time_to_detect_s,
                "stopped_myr": h.stopped_myr,
                "cashed_out_today_myr": h.cashed_out_today_myr,
                "cashed_out_rb_myr": h.cashed_out_rb_myr,
                "false_freezes": h.false_freezes,
                "lookalike_full_freezes": h.lookalike_full_freezes,
                "ring_score": h.ring_score,
            }
        )
    alert_rate = float(np.mean([1.0 if r["ring_alerted"] else 0.0 for r in rows]))
    ttds = [float(r["time_to_detect_s"]) for r in rows if r["time_to_detect_s"] is not None]
    stopped = [float(r["stopped_myr"]) for r in rows]
    false_fz = [float(r["false_freezes"]) for r in rows]
    # Median hero among alerted rows by stopped_myr (A13)
    alerted = [r for r in rows if r["ring_alerted"]]
    median_seed = None
    if alerted:
        alerted_sorted = sorted(alerted, key=lambda r: r["stopped_myr"])
        median_seed = alerted_sorted[len(alerted_sorted) // 2]["seed"]
    return {
        "status": "ok",
        "config_hash": config_hash,
        "seeds": seeds,
        "accounts_per_bank": accounts_per_bank,
        "alert_rate": alert_rate,
        "time_to_detect_s": _bootstrap_ci(ttds, seed=1),
        "stopped_myr": _bootstrap_ci(stopped, seed=2),
        "false_freezes": _bootstrap_ci(false_fz, seed=3),
        "median_hero_seed": median_seed,
        "rows": rows,
        "reading": (
            "E-A test-seed scoreboard (in our simulation). Numbers only from this harness; "
            "not predictions for real banks."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    cfg = _config_blob(settings)
    chash = _config_hash(cfg)
    apb = int(os.getenv("PROOF_ACCOUNTS_PER_BANK", "280"))
    quick = os.getenv("PROOF_QUICK", "").strip() in ("1", "true", "True")
    # Full G3: 100–119. Quick: 5 seeds. Override with PROOF_SEEDS.
    default_ea = list(range(100, 120)) if not quick else [100, 101, 105, 110, 115]
    test_seeds = _parse_seeds("PROOF_SEEDS", default_ea)
    sweep_seeds = _parse_seeds("PROOF_SWEEP_SEEDS", test_seeds[:3] if len(test_seeds) >= 3 else test_seeds)

    print(f"[ringbreaker] {SYNTHETIC_BADGE} proof config_hash={chash[:16]}…", flush=True)
    print(f"[ringbreaker] E-A seeds={test_seeds} accounts_per_bank={apb}", flush=True)
    ea = run_ea_scoreboard(test_seeds, accounts_per_bank=apb, config_hash=chash)

    median_seed = ea.get("median_hero_seed") or settings.seed_hero
    print(f"[ringbreaker] median hero seed={median_seed} (rewrite replay)", flush=True)
    hero = run_hero(int(median_seed), accounts_per_bank=apb, write_replay=True)

    print(f"[ringbreaker] E-B…E-G sweep_seeds={sweep_seeds}", flush=True)
    eb = run_eb_network(sweep_seeds, apb)
    ec = run_ec_delay(sweep_seeds, apb)
    ed = run_ed_evasion(sweep_seeds, apb)
    ee = run_ee_prevention(sweep_seeds, apb)
    ef = run_ef_agent(sweep_seeds, apb)
    eg = run_eg_ablations(sweep_seeds, apb)

    baselines_path = RESULTS / "baselines_dev.json"
    baselines_dev = None
    if baselines_path.exists():
        baselines_dev = json.loads(baselines_path.read_text(encoding="utf-8"))

    blob = {
        "schema_version": "results.v1",
        "synthetic": True,
        "badge": SYNTHETIC_BADGE,
        "in_our_simulation": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "package_version": __version__,
        "config": cfg,
        "config_hash": chash,
        "hero": hero.to_dict(),
        "median_hero_seed": median_seed,
        "experiments": {
            "E-A": ea,
            "E-B": eb,
            "E-C": ec,
            "E-D": ed,
            "E-E": ee,
            "E-F": ef,
            "E-G": eg,
        },
        "baselines_dev": baselines_dev,
        "limitations": "See LIMITATIONS.md — privacy by design on pseudonymised data; not compliance.",
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / "results.json"
    path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
    # Persist median seed hint for SEED_HERO / record
    (RESULTS / "median_hero.json").write_text(
        json.dumps({"seed": median_seed, "config_hash": chash}, indent=2),
        encoding="utf-8",
    )
    print(f"wrote {path}", flush=True)
    print(
        json.dumps(
            {
                "config_hash": chash,
                "median_hero_seed": median_seed,
                "hero_stopped_myr": hero.stopped_myr,
                "E-A_alert_rate": ea["alert_rate"],
                "E-A_mean_stopped": ea["stopped_myr"]["mean"],
                "E-B_ABC_alert": eb["by_participation"]["ABC"]["alert_rate"],
                "E-G_fed_alert": eg["federated_plus_graph"]["alert_rate"],
                "E-G_local_alert": eg["local_model_plus_graph"]["alert_rate"],
            },
            indent=2,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
