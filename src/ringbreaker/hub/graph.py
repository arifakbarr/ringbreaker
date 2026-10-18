"""Incremental token graph from beacons and edge events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import networkx as nx

from ringbreaker.privacy.schemas import BeaconV1, EdgeEventV1


@dataclass
class NodeState:
    token: str
    score: float = 0.0
    banks: set[str] = field(default_factory=set)
    coarse: dict[str, Any] = field(default_factory=dict)
    balance_myr_rounded: int = 0
    last_ts: str = ""


class TokenGraph:
    def __init__(self, window_s: int = 6 * 3600) -> None:
        self.window_s = window_s
        self.g = nx.MultiDiGraph()
        self.nodes: dict[str, NodeState] = {}
        self.link_g = nx.Graph()  # undirected rarity-weighted links
        self._link_counts: dict[str, int] = {}  # link token -> how many accounts

    def ingest_beacon(self, b: BeaconV1) -> None:
        ns = self.nodes.get(b.token) or NodeState(token=b.token)
        ns.score = max(ns.score, float(b.score))
        ns.banks.add(b.bank_id)
        ns.coarse = b.coarse.model_dump()
        ns.balance_myr_rounded = b.balance_myr_rounded
        ns.last_ts = b.window_end
        self.nodes[b.token] = ns
        if b.token not in self.g:
            self.g.add_node(b.token)
        self.g.nodes[b.token].update(
            {
                "score": ns.score,
                "banks": list(ns.banks),
                "balance": ns.balance_myr_rounded,
            }
        )
        # Linkage edges
        for kind, tokens in (
            ("device", b.linkage.device),
            ("phone", b.linkage.phone),
            ("ip", b.linkage.ip),
        ):
            for lt in tokens:
                self._link_counts[lt] = self._link_counts.get(lt, 0) + 1
                # Connect this account token to others sharing lt via a bipartite hop:
                # store link-token as meta; connect accounts that share same lt lazily
                key = f"{kind}:{lt}"
                if not hasattr(self, "_link_members"):
                    self._link_members = {}
                members = self._link_members.setdefault(key, set())
                for other in list(members):
                    if other == b.token:
                        continue
                    rarity = 1.0 / max(1, len(members) + 1)
                    weight = rarity * (1.0 if kind == "device" else 0.7 if kind == "phone" else 0.2)
                    if self.link_g.has_edge(b.token, other):
                        self.link_g[b.token][other]["weight"] = max(
                            self.link_g[b.token][other].get("weight", 0), weight
                        )
                        self.link_g[b.token][other]["kinds"] = list(
                            set(self.link_g[b.token][other].get("kinds", []) + [kind])
                        )
                    else:
                        self.link_g.add_edge(b.token, other, weight=weight, kinds=[kind])
                members.add(b.token)

    def ingest_edge(self, e: EdgeEventV1) -> None:
        self.g.add_edge(
            e.src_token,
            e.dst_token,
            key=e.edge_id,
            amount=e.amount_myr,
            ts=e.ts,
            channel=e.channel,
            src_bank=e.src_bank,
            dst_bank=e.dst_bank,
        )
        for t, bank in ((e.src_token, e.src_bank), (e.dst_token, e.dst_bank)):
            if t not in self.nodes:
                self.nodes[t] = NodeState(token=t)
            if bank not in ("EXT",):
                self.nodes[t].banks.add(str(bank))

    def suspicion_nodes(self, share_threshold: float) -> set[str]:
        seeds = {t for t, ns in self.nodes.items() if ns.score >= share_threshold}
        expanded = set(seeds)
        for t in seeds:
            if t in self.g:
                expanded.update(self.g.successors(t))
                expanded.update(self.g.predecessors(t))
            if t in self.link_g:
                expanded.update(self.link_g.neighbors(t))
        return expanded

    def undirected_projection(self, nodes: set[str]) -> nx.Graph:
        ug = nx.Graph()
        ug.add_nodes_from(nodes)
        for u, v, data in self.g.edges(data=True):
            if u in nodes and v in nodes:
                w = ug[u][v]["weight"] if ug.has_edge(u, v) else 0.0
                ug.add_edge(u, v, weight=w + 1.0 + float(data.get("amount", 0)) / 10_000.0)
        for u, v, data in self.link_g.edges(data=True):
            if u in nodes and v in nodes:
                w = ug[u][v]["weight"] if ug.has_edge(u, v) else 0.0
                ug.add_edge(u, v, weight=w + float(data.get("weight", 0.1)) * 5)
        return ug
