from pathlib import Path

from ringbreaker.hub.decisions import AccountDecision, DecisionLog


def test_hash_chain(tmp_path: Path):
    log = DecisionLog(tmp_path / "d.jsonl")
    r1 = log.append(
        case_id="C1",
        ring_version=1,
        model_id="template",
        prompt_version="v1",
        evidence_ids=["EV-1"],
        accounts=[AccountDecision(alias="ACC-01", action="approve", tier="T4")],
    )
    r2 = log.append(
        case_id="C1",
        ring_version=1,
        model_id="template",
        prompt_version="v1",
        evidence_ids=["EV-1"],
        accounts=[AccountDecision(alias="ACC-01", action="reject", reason_code="LOOKS_LEGIT")],
    )
    assert r2.prev_hash == r1.hash
    assert log.verify()
