"""Ring score: logistic combination of explainable components."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ringbreaker.hub.graph import TokenGraph
from ringbreaker.hub.rings import CandidateRing


@dataclass
class RingScoreWeights:
    """Frozen after fit on dev seeds."""

    intercept: float = -2.2
    node_score: float = 2.4
    flow_through: float = 1.8
    cross_bank_span: float = 1.2
    link_density: float = 1.5
    temporal_compactness: float = 0.9
    inflow_anomaly: float = 1.1

    def as_dict(self) -> dict[str, float]:
        return {
            "intercept": self.intercept,
            "node_score": self.node_score,
            "flow_through": self.flow_through,
            "cross_bank_span": self.cross_bank_span,
            "link_density": self.link_density,
            "temporal_compactness": self.temporal_compactness,
            "inflow_anomaly": self.inflow_anomaly,
        }


DEFAULT_WEIGHTS = RingScoreWeights()


def _sigmoid(z: float) -> float:
    return float(1.0 / (1.0 + np.exp(-np.clip(z, -50, 50))))


def compute_components(graph: TokenGraph, ring: CandidateRing, top_k: int = 5) -> dict[str, float]:
    members = ring.members
    scores = sorted((graph.nodes[m].score for m in members if m in graph.nodes), reverse=True)
    node_score = float(np.mean(scores[:top_k])) if scores else 0.0

    # Flow-through: share of member outflow vs inflow on money edges
    inflow = 0.0
    outflow = 0.0
    timestamps: list[float] = []
    for u, v, data in graph.g.edges(data=True):
        if v in members:
            inflow += float(data.get("amount", 0))
            ts = data.get("ts")
            if isinstance(ts, str):
                # ISO or int-as-str
                try:
                    timestamps.append(float(ts))
                except ValueError:
                    pass
            elif isinstance(ts, (int, float)):
                timestamps.append(float(ts))
        if u in members:
            outflow += float(data.get("amount", 0))
    flow_through = min(1.0, outflow / inflow) if inflow > 0 else 0.0

    banks = set()
    for m in members:
        ns = graph.nodes.get(m)
        if ns:
            banks |= ns.banks
    cross_bank_span = min(1.0, len(banks) / 4.0)

    # Link density: mean rarity-weighted link edges inside community
    link_w = 0.0
    n_links = 0
    for u, v, data in graph.link_g.edges(data=True):
        if u in members and v in members:
            link_w += float(data.get("weight", 0))
            n_links += 1
    link_density = min(1.0, link_w / max(1, len(members)))

    if len(timestamps) >= 2:
        span = max(timestamps) - min(timestamps)
        temporal_compactness = float(np.exp(-span / (90 * 60)))  # tighter = higher
    else:
        temporal_compactness = 0.3

    # Inflow anomaly: large rounded balances + high scores
    bal = [graph.nodes[m].balance_myr_rounded for m in members if m in graph.nodes]
    inflow_anomaly = min(1.0, (max(bal) if bal else 0) / 40_000.0)

    return {
        "node_score": node_score,
        "flow_through": flow_through,
        "cross_bank_span": cross_bank_span,
        "link_density": link_density,
        "temporal_compactness": temporal_compactness,
        "inflow_anomaly": inflow_anomaly,
    }


def score_ring(
    graph: TokenGraph,
    ring: CandidateRing,
    weights: RingScoreWeights | None = None,
    drop_signal: str | None = None,
) -> CandidateRing:
    w = weights or DEFAULT_WEIGHTS
    comps = compute_components(graph, ring)
    if drop_signal and drop_signal in comps:
        comps = {**comps, drop_signal: 0.0}
    z = (
        w.intercept
        + w.node_score * comps["node_score"]
        + w.flow_through * comps["flow_through"]
        + w.cross_bank_span * comps["cross_bank_span"]
        + w.link_density * comps["link_density"]
        + w.temporal_compactness * comps["temporal_compactness"]
        + w.inflow_anomaly * comps["inflow_anomaly"]
    )
    ring.components = comps
    ring.score = _sigmoid(z)
    return ring
