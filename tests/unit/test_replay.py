from ringbreaker.sim.replay import build_replay
from ringbreaker.sim.world import counterfactual_stopped


def test_replay_carries_both_timelines():
    """The UI's 'Today' panel needs the untreated world, which still contains cash-outs."""
    base, treated, _ = counterfactual_stopped(103, [], scenario="hero", accounts_per_bank=60)
    replay = build_replay(treated, today_result=base)
    today = replay["today_events"]
    assert len(today) == len(base.events)
    cashed = sum(e["amount_myr"] for e in today if e["channel"] == "cash_out_exit")
    assert round(cashed, 2) == round(base.outcomes.cashed_out_myr, 2)
    assert cashed > 0


def test_replay_without_today_result_is_backward_compatible():
    base, _, _ = counterfactual_stopped(103, [], scenario="hero", accounts_per_bank=60)
    assert "today_events" not in build_replay(base)
