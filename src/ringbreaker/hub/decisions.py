"""Analyst decision log with hash chain."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

Action = Literal["approve", "reject", "modify_tier"]
Reason = Literal["LOOKS_LEGIT", "INSUFFICIENT_EVIDENCE", "KNOWN_CUSTOMER", "DUPLICATE", "OTHER"]


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass
class AccountDecision:
    alias: str
    action: Action
    tier: str | None = None
    reason_code: Reason | None = None
    note: str = ""


@dataclass
class DecisionRecord:
    decision_id: str
    case_id: str
    ring_version: int
    model_id: str
    prompt_version: str
    evidence_hash: str
    analyst_id: str
    ts: str
    accounts: list[dict[str, Any]]
    prev_hash: str
    hash: str = ""


@dataclass
class DecisionLog:
    path: Path
    records: list[DecisionRecord] = field(default_factory=list)
    _prev: str = "GENESIS"

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                raw = json.loads(line)
                self.records.append(DecisionRecord(**raw))
                self._prev = raw.get("hash", self._prev)

    def append(
        self,
        *,
        case_id: str,
        ring_version: int,
        model_id: str,
        prompt_version: str,
        evidence_ids: list[str],
        accounts: list[AccountDecision],
        analyst_id: str = "demo-analyst",
    ) -> DecisionRecord:
        evidence_hash = hashlib.sha256(_canonical(sorted(evidence_ids)).encode()).hexdigest()[:16]
        n = len(self.records) + 1
        body = {
            "decision_id": f"DEC-{n:04d}",
            "case_id": case_id,
            "ring_version": ring_version,
            "model_id": model_id,
            "prompt_version": prompt_version,
            "evidence_hash": evidence_hash,
            "analyst_id": analyst_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "accounts": [asdict(a) for a in accounts],
            "prev_hash": self._prev,
        }
        h = hashlib.sha256((self._prev + _canonical(body)).encode()).hexdigest()
        body["hash"] = h
        rec = DecisionRecord(**body)
        self.records.append(rec)
        self._prev = h
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(rec), ensure_ascii=True) + "\n")
        return rec

    def verify(self) -> bool:
        prev = "GENESIS"
        for rec in self.records:
            body = asdict(rec)
            got = body.pop("hash")
            if body["prev_hash"] != prev:
                return False
            expect = hashlib.sha256((prev + _canonical(body)).encode()).hexdigest()
            if expect != got:
                return False
            prev = got
        return True

    def export(self) -> list[dict[str, Any]]:
        return [asdict(r) for r in self.records]
