"""Graded response tiers T0–T4."""

from __future__ import annotations

from typing import Literal

Tier = Literal["T0", "T1", "T2", "T3", "T4"]


def map_tier(
    membership_prob: float,
    n_independent_signals: int,
    *,
    is_lookalike_like: bool = False,
    strong_device_link: bool = False,
) -> Tier:
    """
    Tune on dev seeds later. Lookalike-like profiles cap at T2 unless strong device-link evidence.
    """
    if membership_prob < 0.25:
        return "T0"
    if membership_prob < 0.4 or n_independent_signals < 1:
        return "T1"

    if is_lookalike_like and not strong_device_link:
        if membership_prob >= 0.55 and n_independent_signals >= 2:
            return "T2"
        return "T1"

    if membership_prob >= 0.75 and n_independent_signals >= 3:
        return "T4"
    if membership_prob >= 0.6 and n_independent_signals >= 2:
        return "T3"
    if membership_prob >= 0.45:
        return "T2"
    return "T1"
