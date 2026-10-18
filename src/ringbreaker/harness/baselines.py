"""Dev-seed baseline rows: local-only vs federated+graph (G1)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from ringbreaker import SYNTHETIC_BADGE
from ringbreaker.config import get_settings
from ringbreaker.features.local_features import compute_account_features
from ringbreaker.fed.models import threshold_at_fpr, train_local_logreg
from ringbreaker.pipeline import run_hero
from ringbreaker.sim.world import simulate


def _local_only_ring_hit(seed: int, accounts_per_bank: int = 400) -> dict[str, Any]:
    """Today world: per-bank mule flags at fixed FPR. Cross-bank ring alert is impossible."""
    settings = get_settings()
    sim = simulate(seed, scenario="hero", accounts_per_bank=accounts_per_bank)
    as_of = 12 * 60
    members = set(next(iter(sim.ground_truth.members.values())))
    bank_stats: dict[str, Any] = {}
    any_mule_flag = False
    for bank in "ABC":
        rows = compute_account_features(sim.accounts, sim.events_by_bank[bank], bank, as_of)
        if not rows:
            bank_stats[bank] = {"mule_flags": 0, "precision": None}
            continue
        X = np.vstack([r.values for r in rows.values()])
        y = np.array([r.label for r in rows.values()])
        model = train_local_logreg(X, y, seed=seed)
        scores = model.predict_proba(X)
        thr = threshold_at_fpr(scores, y, settings.account_fpr)
        flagged = {aid for aid, sc in zip(rows.keys(), scores) if sc >= thr}
        mule_flags = flagged & members
        any_mule_flag = any_mule_flag or len(mule_flags) > 0
        prec = len(mule_flags) / len(flagged) if flagged else None
        bank_stats[bank] = {
            "mule_flags": len(mule_flags),
            "flagged": len(flagged),
            "precision": prec,
        }
    return {
        "seed": seed,
        # Local banks never form a cross-bank ring alert (product thesis).
        "cross_bank_ring_alert": False,
        "any_mule_account_flag": any_mule_flag,
        "bank_stats": bank_stats,
        "cash_out_ts": sim.ground_truth.cash_out_complete_ts,
        "cashed_out_myr": sim.outcomes.cashed_out_myr,
    }


def run_dev_baselines(dev_seeds: list[int] | None = None, accounts_per_bank: int = 400) -> dict[str, Any]:
    settings = get_settings()
    seeds = dev_seeds or list(range(0, 5))  # short G1 pass; expand to 0-19 in full proof
    local_rows = [_local_only_ring_hit(s, accounts_per_bank) for s in seeds]
    fed_rows = []
    for s in seeds:
        h = run_hero(s, accounts_per_bank=accounts_per_bank, write_replay=False)
        fed_rows.append(
            {
                "seed": s,
                "ring_alerted": h.ring_alerted,
                "time_to_detect_s": h.time_to_detect_s,
                "stopped_myr": h.stopped_myr,
                "false_freezes": h.false_freezes,
            }
        )
    local_cross = float(np.mean([1.0 if r["cross_bank_ring_alert"] else 0.0 for r in local_rows]))
    local_mule = float(np.mean([1.0 if r["any_mule_account_flag"] else 0.0 for r in local_rows]))
    fed_hit_rate = float(np.mean([1.0 if r["ring_alerted"] else 0.0 for r in fed_rows]))
    detect_times = [r["time_to_detect_s"] for r in fed_rows if r["time_to_detect_s"] is not None]
    mean_stopped = float(np.mean([r["stopped_myr"] for r in fed_rows]))
    mean_cash_today = float(np.mean([r["cashed_out_myr"] for r in local_rows]))
    return {
        "schema_version": "baselines.dev.v1",
        "synthetic": True,
        "badge": SYNTHETIC_BADGE,
        "in_our_simulation": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seeds": seeds,
        "account_fpr": settings.account_fpr,
        "local_only": {
            "cross_bank_ring_alert_rate": local_cross,
            "any_mule_account_flag_rate": local_mule,
            "mean_cashed_out_myr": mean_cash_today,
            "n": len(seeds),
            "rows": local_rows,
        },
        "federated_plus_graph": {
            "cross_bank_ring_alert_rate": fed_hit_rate,
            "median_time_to_detect_s": float(np.median(detect_times)) if detect_times else None,
            "mean_stopped_myr": mean_stopped,
            "n": len(seeds),
            "rows": fed_rows,
        },
        "reading": (
            "In our simulation, local-only banks can flag individual mule-like accounts but never "
            "raise a cross-bank ring alert; money leaves (~mean cashed out). Federated+graph raises "
            "ring alerts and measures ringgit stopped via counterfactual replay."
        ),
    }


def main() -> int:
    blob = run_dev_baselines()
    path = Path("results/baselines_dev.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
    results = Path("results/results.json")
    if results.exists():
        data = json.loads(results.read_text(encoding="utf-8"))
    else:
        data = {"schema_version": "results.v1", "synthetic": True}
    data["baselines_dev"] = {
        "local_only_cross_bank_alert_rate": blob["local_only"]["cross_bank_ring_alert_rate"],
        "local_only_mule_flag_rate": blob["local_only"]["any_mule_account_flag_rate"],
        "local_only_mean_cashed_out_myr": blob["local_only"]["mean_cashed_out_myr"],
        "fed_graph_cross_bank_alert_rate": blob["federated_plus_graph"]["cross_bank_ring_alert_rate"],
        "fed_graph_median_ttd_s": blob["federated_plus_graph"]["median_time_to_detect_s"],
        "fed_graph_mean_stopped_myr": blob["federated_plus_graph"]["mean_stopped_myr"],
        "seeds": blob["seeds"],
        "n": blob["local_only"]["n"],
        "reading": blob["reading"],
    }
    results.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps(data["baselines_dev"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
