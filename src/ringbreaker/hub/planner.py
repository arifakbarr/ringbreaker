"""Interception planner: maximise expected stopped money − λ · false-freeze cost."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any

from ringbreaker.hub.graph import TokenGraph
from ringbreaker.hub.rings import CandidateRing
from ringbreaker.hub.tiers import Tier, map_tier


@dataclass
class FreezePlanItem:
    rank: int
    token: str
    bank: str
    tier: Tier
    expected_stopped_myr: float
    false_freeze_risk: float
    rationale_codes: list[str]
    membership_prob: float


@dataclass
class FreezePlan:
    ring_id: str
    items: list[FreezePlanItem]
    expected_stopped_total: float
    k: int

    def by_bank(self) -> dict[str, list[FreezePlanItem]]:
        out: dict[str, list[FreezePlanItem]] = {}
        for it in self.items:
            out.setdefault(it.bank, []).append(it)
        return out


def _account_features(
    graph: TokenGraph,
    token: str,
    ring: CandidateRing,
) -> dict[str, Any]:
    ns = graph.nodes.get(token)
    score = ns.score if ns else 0.0
    balance = float(ns.balance_myr_rounded if ns else 0)
    banks = list(ns.banks) if ns else []
    bank = banks[0] if banks else "?"
    age_bucket = (ns.coarse or {}).get("account_age_bucket", "under_30") if ns else "under_30"
    lookalike_like = age_bucket == "over_180"
    # Predicted additional inflow: sum of incoming edge amounts from ring members (heuristic)
    pred_in = 0.0
    for u, v, data in graph.g.edges(data=True):
        if v == token and u in ring.members:
            pred_in += 0.3 * float(data.get("amount", 0))
    return {
        "score": score,
        "balance": balance,
        "bank": bank,
        "lookalike_like": lookalike_like,
        "pred_in": pred_in,
        "membership_prob": min(1.0, 0.5 * score + 0.5 * ring.score),
    }


def plan_freezes(
    graph: TokenGraph,
    ring: CandidateRing,
    *,
    k: int = 6,
    lambda_ff: float = 5_000.0,
    strong_device: set[str] | None = None,
) -> FreezePlan:
    strong_device = strong_device or set()
    candidates: list[dict[str, Any]] = []
    for token in ring.members:
        if token.startswith("EXT"):
            continue
        feat = _account_features(graph, token, ring)
        if feat["bank"] in ("?", "EXT"):
            continue
        n_signals = sum(
            [
                1 if feat["score"] >= 0.4 else 0,
                1 if ring.components.get("flow_through", 0) >= 0.5 else 0,
                1 if ring.components.get("cross_bank_span", 0) >= 0.5 else 0,
                1 if token in strong_device else 0,
            ]
        )
        tier = map_tier(
            feat["membership_prob"],
            n_signals,
            is_lookalike_like=feat["lookalike_like"],
            strong_device_link=token in strong_device,
        )
        if tier in ("T0", "T1"):
            continue
        ff_cost = 8_000.0 if feat["lookalike_like"] else (3_000.0 if feat.get("age") else 1_500.0)
        if feat["lookalike_like"]:
            ff_cost = 12_000.0
        exp_stop = feat["membership_prob"] * (feat["balance"] + feat["pred_in"])
        ff_risk = (1.0 - feat["membership_prob"]) * (1.5 if feat["lookalike_like"] else 0.4)
        utility = exp_stop - lambda_ff * ff_risk
        rationale = []
        if feat["score"] >= 0.4:
            rationale.append("HIGH_NODE_SCORE")
        if ring.components.get("flow_through", 0) >= 0.5:
            rationale.append("FAST_PASSTHROUGH")
        if ring.components.get("cross_bank_span", 0) >= 0.5:
            rationale.append("CROSS_BANK")
        if feat["lookalike_like"]:
            rationale.append("LOOKALIKE_CAP")
        candidates.append(
            {
                "token": token,
                "bank": feat["bank"],
                "tier": tier,
                "expected_stopped_myr": round(exp_stop, 2),
                "false_freeze_risk": round(ff_risk, 3),
                "utility": utility,
                "rationale_codes": rationale,
                "membership_prob": feat["membership_prob"],
            }
        )

    # Prefer upstream: lower balance rank among high utility (chokepoints often mid-balance)
    candidates.sort(key=lambda c: (-c["utility"], c["bank"], c["token"]))

    n = len(candidates)
    best_set: list[dict[str, Any]] = []
    best_u = float("-inf")
    if n == 0:
        return FreezePlan(ring_id=ring.ring_id, items=[], expected_stopped_total=0.0, k=k)
    if n <= 14:
        for r in range(1, min(k, n) + 1):
            for combo in combinations(range(n), r):
                subset = [candidates[i] for i in combo]
                u = sum(c["utility"] for c in subset)
                if u > best_u:
                    best_u = u
                    best_set = subset
    else:
        best_set = candidates[:k]

    # Order: upstream chokepoint heuristic — higher membership first, then expected stopped
    best_set = sorted(best_set, key=lambda c: (-c["membership_prob"], -c["expected_stopped_myr"]))[
        :k
    ]

    items = [
        FreezePlanItem(
            rank=i + 1,
            token=c["token"],
            bank=c["bank"],
            tier=c["tier"],
            expected_stopped_myr=c["expected_stopped_myr"],
            false_freeze_risk=c["false_freeze_risk"],
            rationale_codes=c["rationale_codes"],
            membership_prob=c["membership_prob"],
        )
        for i, c in enumerate(best_set)
    ]
    return FreezePlan(
        ring_id=ring.ring_id,
        items=items,
        expected_stopped_total=round(sum(i.expected_stopped_myr for i in items), 2),
        k=k,
    )
