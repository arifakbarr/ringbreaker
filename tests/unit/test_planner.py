from ringbreaker.hub.graph import TokenGraph
from ringbreaker.hub.planner import plan_freezes
from ringbreaker.hub.rings import CandidateRing
from ringbreaker.hub.score import score_ring
from ringbreaker.privacy.schemas import BeaconV1, CoarseFeaturesV1, EdgeEventV1, LinkageV1


def _beacon(token: str, bank: str, score: float, bal: int = 5000) -> BeaconV1:
    return BeaconV1(
        bank_id=bank,  # type: ignore[arg-type]
        token=token,
        score=score,
        model_version="t",
        window_end="2026-01-01T00:00:00Z",
        linkage=LinkageV1(device=["DEVSHARED000000000001"]),
        coarse=CoarseFeaturesV1(
            pass_through_bucket="high",
            median_dwell_bucket="fast",
            account_age_bucket="under_30",
        ),
        balance_myr_rounded=bal,
    )


def test_planner_respects_k():
    g = TokenGraph()
    tokens = [f"TOK{i:020d}"[:22] for i in range(8)]
    banks = ["A", "B", "C", "A", "B", "C", "A", "B"]
    for tok, bank in zip(tokens, banks):
        g.ingest_beacon(_beacon(tok, bank, 0.8, bal=8000))
    for i in range(len(tokens) - 1):
        g.ingest_edge(
            EdgeEventV1(
                edge_id=f"E{i}",
                src_token=tokens[i],
                dst_token=tokens[i + 1],
                src_bank=banks[i],  # type: ignore[arg-type]
                dst_bank=banks[i + 1],  # type: ignore[arg-type]
                amount_myr=1000,
                ts=str(i * 60),
                channel="duitnow_transfer",
            )
        )
    ring = CandidateRing(ring_id="R1", version=1, members=tokens, banks=["A", "B", "C"])
    score_ring(g, ring)
    plan = plan_freezes(g, ring, k=3)
    assert len(plan.items) <= 3
    assert all(it.bank in {"A", "B", "C"} for it in plan.items)
