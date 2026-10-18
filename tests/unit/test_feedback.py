from __future__ import annotations

from pathlib import Path

from ringbreaker.hub.feedback import FeedbackStore


def test_feedback_demotes_lookalike(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path / "feedback.jsonl")
    store.record(case_id="CASE-1", alias="ACC-03", action="suppress", reason="LOOKS_LEGIT")
    plan = [
        {"rank": 1, "alias": "ACC-01", "tier": "T4", "false_freeze_risk": 0.1},
        {"rank": 2, "alias": "ACC-03", "tier": "T4", "false_freeze_risk": 0.05},
    ]
    out = store.apply_to_plan(plan)
    demoted = next(r for r in out if r["alias"] == "ACC-03")
    assert demoted["tier"] == "T2"
    assert demoted["feedback_demoted"] is True
    store2 = FeedbackStore(tmp_path / "feedback.jsonl")
    assert "ACC-03" in store2.suppressed_aliases
