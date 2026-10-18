"""Verify decision hash chain (T2.6)."""

from __future__ import annotations

import sys
from pathlib import Path

from ringbreaker.hub.decisions import DecisionLog


ROOT = Path(__file__).resolve().parents[3]


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    path = Path(args[0]) if args else ROOT / "results" / "decisions.jsonl"
    if not path.exists():
        print(f"missing {path} — approve a case once, or path is empty genesis", flush=True)
        log = DecisionLog(path)
        ok = log.verify()
        print(f"verified={ok} n={len(log.records)} path={path}", flush=True)
        return 0 if ok else 1
    log = DecisionLog(path)
    ok = log.verify()
    print(f"verified={ok} n={len(log.records)} path={path}", flush=True)
    if not ok:
        return 1
    if log.records:
        print(f"tip={log.records[-1].hash[:16]}… last={log.records[-1].decision_id}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
