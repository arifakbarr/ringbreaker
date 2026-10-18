"""Simulator hero invariants."""

from ringbreaker.sim.world import simulate


def test_hero_deterministic():
    a = simulate(101, scenario="hero", accounts_per_bank=200)
    b = simulate(101, scenario="hero", accounts_per_bank=200)
    assert [e.edge_id for e in a.events] == [e.edge_id for e in b.events]
    assert a.ground_truth.members.keys() == b.ground_truth.members.keys()


def test_hero_has_ring_and_lookalikes():
    r = simulate(101, scenario="hero", accounts_per_bank=300)
    members = next(iter(r.ground_truth.members.values()))
    assert len(members) >= 6
    assert len(r.ground_truth.lookalikes) >= 1
    assert r.ground_truth.victim_transfers[0]["amount"] == 40_000.0


def test_hero_cash_out_around_38_min():
    r = simulate(101, scenario="hero", accounts_per_bank=300)
    ts = r.ground_truth.cash_out_complete_ts
    assert ts is not None
    # Soft bound: between 15 and 90 minutes in non-adaptive baseline
    assert 15 * 60 <= ts <= 90 * 60
    assert r.outcomes.cashed_out_myr > 0
