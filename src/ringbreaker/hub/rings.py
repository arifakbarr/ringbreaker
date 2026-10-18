"""Candidate ring extraction via seeded weighted Louvain."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import networkx as nx
from networkx.algorithms.community import louvain_communities

from ringbreaker.hub.graph import TokenGraph


class RingState(str, Enum):
    WATCH = "WATCH"
    ALERT = "ALERT"
    CASE_OPEN = "CASE_OPEN"
    DECIDED = "DECIDED"
    CLOSED = "CLOSED"


@dataclass
class CandidateRing:
    ring_id: str
    version: int
    members: list[str]
    banks: list[str]
    score: float = 0.0
    components: dict[str, float] = field(default_factory=dict)
    state: RingState = RingState.WATCH
    first_detection_ts: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)


def detect_communities(
    graph: TokenGraph,
    share_threshold: float,
    seed: int = 0,
    min_nodes: int = 3,
    min_banks: int = 2,
) -> list[CandidateRing]:
    nodes = graph.suspicion_nodes(share_threshold)
    if len(nodes) < min_nodes:
        return []
    ug = graph.undirected_projection(nodes)
    if ug.number_of_edges() == 0:
        sub = graph.g.subgraph(nodes).to_undirected()
        comps = [list(c) for c in nx.connected_components(sub) if len(c) >= min_nodes]
        rings: list[CandidateRing] = []
        for i, members in enumerate(comps):
            banks_set: set[str] = set()
            for m in members:
                ns = graph.nodes.get(m)
                if ns:
                    banks_set |= ns.banks
            if len(banks_set) < min_banks:
                continue
            rings.append(
                CandidateRing(
                    ring_id=f"CAND-{seed}-{i}",
                    version=1,
                    members=sorted(members),
                    banks=sorted(banks_set),
                )
            )
        return rings

    communities = louvain_communities(ug, weight="weight", seed=seed)
    rings = []
    for i, members_set in enumerate(communities):
        members = list(members_set)
        if len(members) < min_nodes:
            continue
        banks_set: set[str] = set()
        for m in members:
            ns = graph.nodes.get(m)
            if ns:
                banks_set |= ns.banks
        if len(banks_set) < min_banks:
            continue
        rings.append(
            CandidateRing(
                ring_id=f"CAND-{seed}-{i}",
                version=1,
                members=sorted(members),
                banks=sorted(banks_set),
            )
        )
    return rings
