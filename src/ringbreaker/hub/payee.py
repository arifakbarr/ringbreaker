"""Deterministic O(1) payee-risk lookup — no LLM, no graph compute on path."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from ringbreaker.privacy.schemas import PayeeRiskRequestV1, PayeeRiskResponseV1, ReasonCode


@dataclass
class LiveRingEntry:
    ring_ref: str
    tier: Literal[0, 1, 2, 3]
    reason_codes: list[ReasonCode]
    membership_prob: float = 0.0
    state: str = "WATCH"


@dataclass
class LiveRingIndex:
    """token → risk entry; updated when ring states change."""

    by_token: dict[str, LiveRingEntry] = field(default_factory=dict)
    latencies_ms: list[float] = field(default_factory=list)

    def upsert(self, token: str, entry: LiveRingEntry) -> None:
        self.by_token[token] = entry

    def clear(self) -> None:
        self.by_token.clear()

    def p95_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        xs = sorted(self.latencies_ms)
        idx = min(len(xs) - 1, int(0.95 * (len(xs) - 1)))
        return float(xs[idx])


def lookup_payee(index: LiveRingIndex, req: PayeeRiskRequestV1) -> PayeeRiskResponseV1:
    t0 = time.perf_counter()
    entry = index.by_token.get(req.payee_token)
    if entry is None:
        tier: Literal[0, 1, 2, 3] = 0
        codes: list[ReasonCode] = []
        ring_ref = None
    else:
        tier = entry.tier
        codes = list(entry.reason_codes)
        ring_ref = entry.ring_ref
    latency = (time.perf_counter() - t0) * 1000.0
    index.latencies_ms.append(latency)
    return PayeeRiskResponseV1(
        tier=tier,
        reason_codes=codes,
        ring_ref=ring_ref,
        evaluated_at=datetime.now(timezone.utc).isoformat(),
        latency_ms=round(latency, 4),
    )
