"""Headless hero run — `make hero` / `python -m ringbreaker.harness.run_hero`."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from ringbreaker import SYNTHETIC_BADGE, __version__
from ringbreaker.config import get_settings
from ringbreaker.pipeline import run_hero


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    print(f"[ringbreaker] {SYNTHETIC_BADGE} hero seed={settings.seed_hero}", flush=True)
    result = run_hero(settings.seed_hero, accounts_per_bank=600, write_replay=True)

    out = {
        "schema_version": "results.hero.v1",
        "synthetic": True,
        "badge": SYNTHETIC_BADGE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "package_version": __version__,
        "seed": result.seed,
        "in_our_simulation": True,
        "hero": result.to_dict(),
        "note": "Numbers are from the seeded simulator only; not predictions for real banks.",
    }
    path = Path("results/hero.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    # Merge stub into results.json until full proof exists
    results_path = Path("results/results.json")
    if results_path.exists():
        try:
            blob = json.loads(results_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            blob = {}
    else:
        blob = {"schema_version": "results.v1", "synthetic": True}
    blob["hero"] = out["hero"]
    blob["generated_at"] = out["generated_at"]
    blob["badge"] = SYNTHETIC_BADGE
    results_path.write_text(json.dumps(blob, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "ring_alerted": result.ring_alerted,
                "time_to_detect_s": result.time_to_detect_s,
                "stopped_myr": result.stopped_myr,
                "cashed_out_today_myr": result.cashed_out_today_myr,
                "false_freezes": result.false_freezes,
                "payee_p95_ms": result.payee_p95_ms,
                "wrote": str(path),
            },
            indent=2,
        ),
        flush=True,
    )
    return 0 if result.ring_alerted else 1


if __name__ == "__main__":
    sys.exit(main())
