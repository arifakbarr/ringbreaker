from ringbreaker.llm.grounding import validate_case_file


def test_validator_rejects_fake_evidence():
    case = {
        "mode": "llm",
        "why_suspicious": [{"claim": "x", "evidence_ids": ["EV-FAKE"]}],
        "money_trail": [],
        "freeze_priority": [],
        "per_bank_notices": {},
    }
    errs = validate_case_file(
        case,
        evidence_ids={"EV-1"},
        aliases={"ACC-01"},
        planner_order=[],
        tool_amounts=set(),
        bank_to_aliases={},
    )
    assert any("EV-FAKE" in e for e in errs)


def test_validator_bans_guaranteed():
    case = {
        "mode": "template",
        "why_suspicious": [{"claim": "guaranteed fraud", "evidence_ids": ["EV-1"]}],
        "money_trail": [],
        "freeze_priority": [{"rank": 1, "alias": "ACC-01", "tier": "T4"}],
        "per_bank_notices": {"Bank A": {"accounts": ["ACC-01"]}},
    }
    errs = validate_case_file(
        case,
        evidence_ids={"EV-1"},
        aliases={"ACC-01"},
        planner_order=[{"alias": "ACC-01", "tier": "T4"}],
        tool_amounts=set(),
        bank_to_aliases={"Bank A": {"ACC-01"}},
    )
    assert any("banned" in e for e in errs)
