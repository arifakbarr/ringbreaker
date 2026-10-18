"""Slim, judge-facing summary of results/results.json (no new numbers are computed here)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
RESULTS_JSON = ROOT / "results" / "results.json"


def _stat(block: dict[str, Any] | None) -> dict[str, float | int] | None:
    if not block or "mean" not in block:
        return None
    return {
        "mean": block["mean"],
        "ci95_low": block.get("ci95_low", block["mean"]),
        "ci95_high": block.get("ci95_high", block["mean"]),
        "n": block.get("n", 0),
    }


def proof_summary(results: dict[str, Any]) -> dict[str, Any]:
    """Pick the experiments a reviewer needs; every figure is copied from the harness output."""
    exp = results.get("experiments", {})
    e_a = exp.get("E-A", {})
    e_b = exp.get("E-B", {}).get("by_participation", {})
    e_d = exp.get("E-D", {}).get("by_evasion", {})
    base = results.get("baselines_dev", {})
    local = base.get("local_only", {})
    fed = base.get("federated_plus_graph", {})

    return {
        "synthetic": True,
        "in_our_simulation": True,
        "generated_at": results.get("generated_at"),
        "config_hash": results.get("config_hash"),
        "scoreboard": {
            "seeds": e_a.get("seeds", []),
            "alert_rate": e_a.get("alert_rate"),
            "time_to_detect_s": _stat(e_a.get("time_to_detect_s")),
            "stopped_myr": _stat(e_a.get("stopped_myr")),
            "false_freezes": _stat(e_a.get("false_freezes")),
        },
        "network_effect": [
            {
                "banks": key,
                "alert_rate": row.get("alert_rate"),
                "stopped_myr": _stat(row.get("stopped_myr")),
                "n": row.get("n"),
            }
            for key, row in sorted(e_b.items(), key=lambda kv: len(kv[0]))
        ],
        "evasion": [
            {
                "level": key,
                "alert_rate": row.get("alert_rate"),
                "stopped_myr": _stat(row.get("stopped_myr")),
                "time_to_detect_s": _stat(row.get("time_to_detect_s")),
                "n": row.get("n"),
            }
            for key, row in sorted(e_d.items())
        ],
        "baseline": {
            "seeds": base.get("seeds", []),
            "local_only_ring_alert_rate": local.get("cross_bank_ring_alert_rate"),
            "local_only_mean_cashed_out_myr": local.get("mean_cashed_out_myr"),
            "federated_ring_alert_rate": fed.get("cross_bank_ring_alert_rate"),
            "federated_mean_stopped_myr": fed.get("mean_stopped_myr"),
            "n": local.get("n"),
        },
    }


def load_proof(path: Path = RESULTS_JSON) -> dict[str, Any]:
    if not path.exists():
        return {"synthetic": True, "available": False}
    return proof_summary(json.loads(path.read_text(encoding="utf-8")))
