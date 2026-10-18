"""Deterministic template case file (mode=template) — always available."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_template_case(
    *,
    ring_ref: str,
    ring_score: float,
    banks: list[str],
    freeze_priority: list[dict[str, Any]],
    why: list[dict[str, Any]],
    money_trail: list[dict[str, Any]],
    prompt_version: str = "v1",
) -> dict[str, Any]:
    return {
        "case_id": f"CASE-TPL-{ring_ref}",
        "ring_ref": ring_ref,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_id": "template",
        "prompt_version": prompt_version,
        "mode": "template",
        "headline": f"Suspected mule ring across {len(banks)} banks (score {ring_score:.2f})",
        "risk_level": "high" if ring_score >= 0.7 else "medium",
        "confidence": "medium",
        "confidence_basis": ["deterministic_tools", "template_fallback"],
        "why_suspicious": why,
        "money_trail": money_trail,
        "freeze_priority": freeze_priority,
        "counter_evidence": [],
        "uncertainties": ["Synthetic simulation; analyst must confirm."],
        "signal_sensitivity": [],
        "per_bank_notices": {},
        "analyst_questions": ["Any known-customer exemptions on the freeze list?"],
    }
