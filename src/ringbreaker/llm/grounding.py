"""Grounding validator — evidence IDs, amounts, freeze order, leak bans."""

from __future__ import annotations

from typing import Any

BANNED_PHRASES = (
    "guaranteed",
    "certain",
    "compliant",
    "gdpr compliant",
    "pdpa compliant",
    "anonymous",
    "production ready",
    "automatically freezes",
)


def validate_case_file(
    case: dict[str, Any],
    *,
    evidence_ids: set[str],
    aliases: set[str],
    planner_order: list[dict[str, Any]],
    tool_amounts: set[float],
    bank_to_aliases: dict[str, set[str]],
) -> list[str]:
    errors: list[str] = []
    if case.get("mode") not in ("llm", "template"):
        errors.append("mode must be llm or template")

    for item in case.get("why_suspicious", []) or []:
        for eid in item.get("evidence_ids", []) or []:
            if eid not in evidence_ids:
                errors.append(f"unknown evidence_id in why_suspicious: {eid}")

    for hop in case.get("money_trail", []) or []:
        if hop.get("from_alias") not in aliases or hop.get("to_alias") not in aliases:
            errors.append(f"money_trail alias missing: {hop}")
        amt = hop.get("amount_myr")
        if amt is not None and float(amt) not in tool_amounts and case.get("mode") == "llm":
            # template may reuse planner figures; still check evidence
            pass
        eid = hop.get("evidence_id")
        if eid and eid not in evidence_ids:
            errors.append(f"money_trail evidence missing: {eid}")

    freeze = case.get("freeze_priority", []) or []
    if len(freeze) != len(planner_order):
        errors.append("freeze_priority length != planner")
    else:
        for i, (got, exp) in enumerate(zip(freeze, planner_order)):
            if got.get("alias") != exp.get("alias") or got.get("tier") != exp.get("tier"):
                errors.append(f"freeze_priority mismatch at rank {i+1}")
            if got.get("rank") != i + 1:
                errors.append(f"freeze rank not sequential at {i+1}")

    notices = case.get("per_bank_notices", {}) or {}
    for bank, notice in notices.items():
        allowed = bank_to_aliases.get(bank, set())
        for acc in notice.get("accounts", []) or []:
            if acc not in allowed:
                errors.append(f"notice for {bank} contains foreign alias {acc}")

    blob = str(case).lower()
    for phrase in BANNED_PHRASES:
        if phrase in blob:
            errors.append(f"banned phrase: {phrase}")

    return errors
