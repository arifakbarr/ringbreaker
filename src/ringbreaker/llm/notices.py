"""Per-bank notices — only that bank's aliases (leak-tested). EN + BM."""

from __future__ import annotations

from typing import Any, Literal

Lang = Literal["en", "ms"]


_ACTION_EN = {
    "T4": "full freeze recommendation",
    "T3": "partial hold recommendation",
    "other": "step-up verification",
}
_ACTION_MS = {
    "T4": "cadangan pembekuan penuh",
    "T3": "cadangan penahanan separa",
    "other": "pengesahan tambahan",
}


def _action_key(tiers: set[str]) -> str:
    if "T4" in tiers:
        return "T4"
    if "T3" in tiers:
        return "T3"
    return "other"


def build_per_bank_notices(
    freeze_priority: list[dict[str, Any]],
    *,
    risk_tier: str = "high",
    n_banks: int = 3,
    lang: Lang = "en",
) -> dict[str, dict[str, Any]]:
    by_bank: dict[str, list[dict[str, Any]]] = {}
    for item in freeze_priority:
        bank = item.get("bank", "Bank ?")
        by_bank.setdefault(bank, []).append(item)

    notices: dict[str, dict[str, Any]] = {}
    for bank, items in by_bank.items():
        accounts = [i["alias"] for i in items]
        tiers = {i["tier"] for i in items}
        key = _action_key(tiers)
        if lang == "ms":
            action = _ACTION_MS[key]
            text = (
                f"Ringbreaker mencadangkan {action} ke atas {len(accounts)} akaun di bank anda. "
                f"Rangkaian merentas {n_banks} bank (risiko {risk_tier}). "
                f"Kelulusan penganalisis diperlukan. Simulasi sintetik sahaja."
            )
        else:
            action = _ACTION_EN[key]
            text = (
                f"Ringbreaker recommends {action} on {len(accounts)} account(s) in your bank. "
                f"Cross-bank ring spans {n_banks} banks (risk {risk_tier}). "
                f"Analyst approval required before enforcement. Synthetic simulation only."
            )
        notices[bank] = {
            "accounts": accounts,
            "recommended_action": action,
            "text": text,
            "text_en": (
                f"Ringbreaker recommends {_ACTION_EN[key]} on {len(accounts)} account(s) "
                f"in your bank. Cross-bank ring spans {n_banks} banks (risk {risk_tier}). "
                f"Analyst approval required before enforcement. Synthetic simulation only."
            ),
            "text_ms": (
                f"Ringbreaker mencadangkan {_ACTION_MS[key]} ke atas {len(accounts)} akaun "
                f"di bank anda. Rangkaian merentas {n_banks} bank (risiko {risk_tier}). "
                f"Kelulusan penganalisis diperlukan. Simulasi sintetik sahaja."
            ),
            "lang": lang,
        }
    return notices
