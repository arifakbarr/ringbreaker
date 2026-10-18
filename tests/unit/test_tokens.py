from ringbreaker.privacy.tokens import Tokeniser


def test_token_deterministic_and_typed():
    t = Tokeniser("SYNTHETIC-DEV-KEY", "e1")
    a1 = t.account_token("A8800000001")
    a2 = t.account_token("A8800000001")
    assert a1 == a2
    assert len(a1) == 22
    # Type scoping: same value different types differ
    phone = "+60121234567"
    assert t.phone_token(phone) != t.token(phone, "account")


def test_phone_normalisation():
    t = Tokeniser("k", "e1")
    assert t.phone_token("012-3456789") == t.phone_token("+60123456789")
