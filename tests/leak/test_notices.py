from ringbreaker.llm.notices import build_per_bank_notices


def test_notice_no_foreign_aliases():
    freeze = [
        {"alias": "ACC-01", "bank": "Bank A", "tier": "T4", "expected_stopped_myr": 1000, "false_freeze_risk": 0.1, "rank": 1},
        {"alias": "ACC-02", "bank": "Bank B", "tier": "T3", "expected_stopped_myr": 500, "false_freeze_risk": 0.2, "rank": 2},
    ]
    notices = build_per_bank_notices(freeze, n_banks=2)
    assert set(notices["Bank A"]["accounts"]) == {"ACC-01"}
    assert "ACC-02" not in notices["Bank A"]["accounts"]
    assert "Bank B" not in notices["Bank A"]["text"]
