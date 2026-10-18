"""Intervention helpers for freezes and payee blocks."""

from __future__ import annotations

from ringbreaker.sim.types import Freeze, FreezeKind, Intervention, PayeeBlock


def freeze_set(interventions: list[Intervention], at_ts: int) -> dict[str, FreezeKind]:
    """Accounts frozen/held at or before at_ts."""
    out: dict[str, FreezeKind] = {}
    for iv in interventions:
        if isinstance(iv, Freeze) and iv.at_ts <= at_ts:
            out[iv.account_id] = iv.kind
    return out


def is_payee_blocked(
    interventions: list[Intervention],
    account_id: str,
    at_ts: int,
    rng_u: float,
) -> bool:
    """Return True if a PayeeBlock applies and victim complies (rng_u < compliance)."""
    for iv in interventions:
        if isinstance(iv, PayeeBlock) and iv.account_id == account_id and iv.from_ts <= at_ts:
            return rng_u < iv.compliance_rate
    return False
