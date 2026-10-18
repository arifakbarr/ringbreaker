"""Deterministic read-only investigator tools (structured outputs only)."""

from __future__ import annotations

from typing import Any

from ringbreaker.hub.graph import TokenGraph
from ringbreaker.hub.planner import FreezePlan, plan_freezes
from ringbreaker.hub.rings import CandidateRing
from ringbreaker.hub.score import score_ring
from ringbreaker.llm.aliases import AliasMap, redact


class EvidenceStore:
    def __init__(self) -> None:
        self.items: dict[str, Any] = {}
        self._n = 0

    def add(self, kind: str, payload: dict) -> str:
        self._n += 1
        eid = f"EV-{kind}-{self._n:03d}"
        self.items[eid] = payload
        return eid

    def ids(self) -> set[str]:
        return set(self.items.keys())


class InvestigatorTools:
    def __init__(
        self,
        graph: TokenGraph,
        ring: CandidateRing,
        aliases: AliasMap,
        evidence: EvidenceStore | None = None,
        lookalikes: set[str] | None = None,
        first_detection_s: int | None = None,
    ) -> None:
        self.graph = graph
        self.ring = ring
        self.aliases = aliases
        self.evidence = evidence or EvidenceStore()
        self.lookalikes = lookalikes or set()
        self.first_detection_s = first_detection_s
        for t in ring.members:
            self.aliases.alias_for(t)

    def get_ring_overview(self) -> dict:
        score_ring(self.graph, self.ring)
        payload = redact(
            {
                "ring_id": self.ring.ring_id,
                "ring_score": round(self.ring.score, 4),
                "components": self.ring.components,
                "banks": [self.aliases.bank_label(b) for b in self.ring.banks],
                "member_count": len(self.ring.members),
                "first_detection_s": self.first_detection_s,
            }
        )
        eid = self.evidence.add("overview", payload)
        return {**payload, "evidence_id": eid}

    def get_ring_subgraph(self) -> dict:
        nodes = []
        for tok in self.ring.members:
            ns = self.graph.nodes.get(tok)
            alias = self.aliases.alias_for(tok)
            bank = sorted(ns.banks)[0] if ns and ns.banks else "?"
            nodes.append(
                {
                    "alias": alias,
                    "bank": self.aliases.bank_label(bank),
                    "score": ns.score if ns else 0.0,
                    "coarse": ns.coarse if ns else {},
                    "balance_myr_rounded": ns.balance_myr_rounded if ns else 0,
                }
            )
        edges = []
        for u, v, data in self.graph.g.edges(data=True):
            if u in self.ring.members and v in self.ring.members:
                eid = self.evidence.add(
                    "edge",
                    {
                        "from_alias": self.aliases.alias_for(u),
                        "to_alias": self.aliases.alias_for(v),
                        "amount_myr": data.get("amount"),
                        "ts": data.get("ts"),
                        "channel": data.get("channel"),
                    },
                )
                edges.append(
                    {
                        "from_alias": self.aliases.alias_for(u),
                        "to_alias": self.aliases.alias_for(v),
                        "amount_myr": data.get("amount"),
                        "ts": data.get("ts"),
                        "channel": data.get("channel"),
                        "evidence_id": eid,
                    }
                )
        links = []
        for u, v, data in self.graph.link_g.edges(data=True):
            if u in self.ring.members and v in self.ring.members:
                links.append(
                    {
                        "from_alias": self.aliases.alias_for(u),
                        "to_alias": self.aliases.alias_for(v),
                        "kinds": data.get("kinds", []),
                        "weight": data.get("weight"),
                    }
                )
        payload = {"nodes": nodes, "edges": edges, "links": links}
        eid = self.evidence.add("subgraph", {"n_nodes": len(nodes), "n_edges": len(edges)})
        return {**payload, "evidence_id": eid}

    def plan_freeze(self, k: int = 6, delay_s: int = 120) -> dict:
        plan: FreezePlan = plan_freezes(self.graph, self.ring, k=k)
        items = []
        for it in plan.items:
            items.append(
                {
                    "rank": it.rank,
                    "alias": self.aliases.alias_for(it.token),
                    "bank": self.aliases.bank_label(it.bank),
                    "tier": it.tier,
                    "expected_stopped_myr": it.expected_stopped_myr,
                    "false_freeze_risk": it.false_freeze_risk,
                    "rationale": it.rationale_codes,
                    "membership_prob": it.membership_prob,
                }
            )
        payload = {"plan": items, "expected_stopped_total": plan.expected_stopped_total, "k": k}
        eid = self.evidence.add("plan", payload)
        return {**payload, "evidence_id": eid}

    def counterfactual_score(self, drop_signal: str) -> dict:
        scored = score_ring(self.graph, self.ring)
        base = float(scored.score)
        tmp = CandidateRing(
            ring_id=self.ring.ring_id,
            version=self.ring.version,
            members=list(self.ring.members),
            banks=list(self.ring.banks),
        )
        dropped = float(score_ring(self.graph, tmp, drop_signal=drop_signal).score)
        score_ring(self.graph, self.ring)
        payload = {
            "signal": drop_signal,
            "score_without": round(dropped, 4),
            "delta": round(base - dropped, 4),
        }
        eid = self.evidence.add("cf", payload)
        return {**payload, "evidence_id": eid}

    def lookalike_check(self, alias: str) -> dict:
        tok = self.aliases.token_for(alias)
        ns = self.graph.nodes.get(tok) if tok else None
        age = (ns.coarse or {}).get("account_age_bucket", "under_30") if ns else "under_30"
        is_ll = bool(tok and tok in self.lookalikes) or age == "over_180"
        payload = {
            "alias": alias,
            "lookalike": is_ll,
            "account_age_bucket": age,
            "counterparty_diversity": "high" if is_ll else "low",
        }
        eid = self.evidence.add("lookalike", payload)
        return {**payload, "evidence_id": eid}
