"""UI-ready replay.json builder from a SimulationResult (+ optional hub timeline)."""

from __future__ import annotations

from typing import Any

from ringbreaker.sim.types import SimulationResult


def _events_payload(result: SimulationResult) -> list[dict[str, Any]]:
    return [
        {
            "edge_id": e.edge_id,
            "src": e.src_account,
            "dst": e.dst_account,
            "src_bank": e.src_bank,
            "dst_bank": e.dst_bank,
            "amount_myr": e.amount_myr,
            "ts": e.ts,
            "channel": e.channel,
            "is_ring": e.is_ring,
            "victim_id": e.victim_id,
        }
        for e in result.events
    ]


def build_replay(
    result: SimulationResult,
    hub_timeline: list[dict[str, Any]] | None = None,
    today_outcomes: dict[str, Any] | None = None,
    rb_outcomes: dict[str, Any] | None = None,
    today_result: SimulationResult | None = None,
) -> dict[str, Any]:
    """Time-ordered UI payload. Ground truth is optional reveal-only.

    ``events`` is the world *with* Ringbreaker interventions applied (frozen accounts stop
    moving money, so cash-out exits are blocked). ``today_events`` is the same seed with no
    interventions, i.e. what happens today. The UI needs both for the split replay.
    """
    payload: dict[str, Any] = {
        "schema_version": "replay.v1",
        "synthetic": True,
        "badge": "SYNTHETIC DATA · SIMULATION",
        "seed": result.seed,
        "scenario": result.scenario,
        "live_window_start": result.live_window_start,
        "live_window_end": result.live_window_end,
        "events": _events_payload(result),
        "hub_timeline": hub_timeline or [],
        "today_outcomes": today_outcomes or {
            "cashed_out_myr": result.outcomes.cashed_out_myr,
            "stuck_myr": result.outcomes.stuck_myr,
        },
        "ringbreaker_outcomes": rb_outcomes or {},
        "ground_truth_reveal": {
            "ring_ids": result.ground_truth.ring_ids,
            "members": result.ground_truth.members,
            "lookalikes": result.ground_truth.lookalikes,
            "cash_out_complete_ts": result.ground_truth.cash_out_complete_ts,
        },
    }
    if today_result is not None:
        payload["today_events"] = _events_payload(today_result)
    return payload
