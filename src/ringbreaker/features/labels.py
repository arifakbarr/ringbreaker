"""Label helpers: ring member during window; train/test rings disjoint."""

from __future__ import annotations

from ringbreaker.sim.types import Account


def label_account(acct: Account) -> int:
    return 1 if acct.is_ring and acct.archetype == "mule" else 0
