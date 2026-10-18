"""Freeze a judge-safe RECORDED pack into ui/public for offline UI fallback (T2.7)."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from ringbreaker.hub.demo_state import DEMO_PACK, STATE
from ringbreaker.hub.proof import load_proof


ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "ui" / "public" / "recorded"
RESULTS = ROOT / "results"


def main(argv: list[str] | None = None) -> int:
    force = "--force" in (argv or sys.argv[1:])
    STATE.load_or_build(force=force)
    if not DEMO_PACK.exists():
        print("demo_pack.json missing after build", flush=True)
        return 1

    pack = json.loads(DEMO_PACK.read_text(encoding="utf-8"))
    # Tag pack so UI can label RECORDED without inventing data
    pack["mode"] = "RECORDED"
    pack["synthetic"] = True

    PUBLIC.mkdir(parents=True, exist_ok=True)
    out = PUBLIC / "demo_pack.json"
    out.write_text(json.dumps(pack, indent=2), encoding="utf-8")

    # Slim companions (same truth as pack)
    cases = pack.get("cases") or []
    (PUBLIC / "case.json").write_text(
        json.dumps(cases[0] if cases else {}, indent=2), encoding="utf-8"
    )
    (PUBLIC / "hero.json").write_text(
        json.dumps({"hero": pack.get("hero_metrics", {})}, indent=2), encoding="utf-8"
    )
    (PUBLIC / "replay.json").write_text(
        json.dumps(pack.get("replay") or {}, indent=2), encoding="utf-8"
    )

    (PUBLIC / "proof.json").write_text(
        json.dumps(load_proof(), indent=2), encoding="utf-8"
    )

    # Keep results/replay mirror for RUNBOOK paths (demo_pack already lives in results/)
    RESULTS.mkdir(parents=True, exist_ok=True)
    dest_pack = RESULTS / "demo_pack.json"
    if DEMO_PACK.resolve() != dest_pack.resolve():
        shutil.copy2(DEMO_PACK, dest_pack)
    else:
        # Re-tag mode on the live pack used by the hub
        DEMO_PACK.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    if pack.get("replay"):
        (RESULTS / "replay.json").write_text(
            json.dumps(pack["replay"], indent=2), encoding="utf-8"
        )

    print(f"recorded -> {out} ({out.stat().st_size} bytes)", flush=True)
    print(f"cases={list(STATE.cases)} hero_seed={pack.get('hero_metrics', {}).get('seed')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
