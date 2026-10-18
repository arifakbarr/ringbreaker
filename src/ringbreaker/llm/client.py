"""Optional Gemini client — never required for demo path (I7)."""

from __future__ import annotations

import json
import re
from typing import Any

from ringbreaker.config import Settings
from ringbreaker.llm.templates import build_template_case


_SYSTEM = """You are Ringbreaker's fraud investigator for a SYNTHETIC bank simulation.
Return ONLY valid JSON for a case file. Every claim must cite evidence_ids from the tool dump.
Never invent amounts, aliases, or banks. Never claim GDPR/PDPA compliance or anonymity.
Banned phrases: "guaranteed", "definitely criminal", "anonymous", "GDPR compliant".
"""


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None


def try_llm_case(tools: Any, gathered: dict[str, Any], settings: Settings) -> dict[str, Any] | None:
    """
    Call Google AI Studio (GEMINI_API_KEY) for a grounded case draft.
    Returns None when key/SDK missing or the model fails — caller keeps template.
    """
    if not settings.gemini_api_key:
        return None
    try:
        from google import genai
    except ImportError:
        return None

    overview = gathered["overview"]
    plan_items = gathered["plan"]["plan"]
    banks = overview.get("banks", [])
    freeze_priority = [
        {
            "rank": p["rank"],
            "alias": p["alias"],
            "bank": p["bank"],
            "tier": p["tier"],
            "expected_stopped_myr": p["expected_stopped_myr"],
            "false_freeze_risk": p["false_freeze_risk"],
            "rationale": ", ".join(p.get("rationale") or []),
            "evidence_ids": [gathered["plan"]["evidence_id"]],
        }
        for p in plan_items
    ]
    # Start from template skeleton so schema stays close
    skeleton = build_template_case(
        ring_ref=overview["ring_id"],
        ring_score=float(overview["ring_score"]),
        banks=banks,
        freeze_priority=freeze_priority,
        why=[
            {
                "claim": f"Ring score {overview['ring_score']} across {overview['member_count']} accounts",
                "evidence_ids": [overview["evidence_id"]],
            }
        ],
        money_trail=[
            {
                "from_alias": e["from_alias"],
                "to_alias": e["to_alias"],
                "amount_myr": e["amount_myr"],
                "ts": e["ts"],
                "evidence_id": e["evidence_id"],
            }
            for e in gathered["subgraph"].get("edges", [])[:12]
        ],
        prompt_version=settings.prompt_version,
    )

    payload = {
        "tools": {
            "overview": overview,
            "subgraph": gathered["subgraph"],
            "plan": gathered["plan"],
            "sensitivity": gathered.get("sensitivity"),
            "lookalikes": gathered.get("lookalikes"),
        },
        "skeleton": skeleton,
        "instructions": (
            "Rewrite headline and why_suspicious using ONLY tool facts. "
            "Keep freeze_priority order and aliases identical to skeleton. "
            "Keep money_trail amounts identical. Set mode to llm."
        ),
    }

    client = genai.Client(api_key=settings.gemini_api_key)
    model = settings.gemini_model or "gemini-2.0-flash"
    try:
        resp = client.models.generate_content(
            model=model,
            contents=f"{_SYSTEM}\n\nINPUT:\n{json.dumps(payload, ensure_ascii=True)[:120000]}",
        )
        text = getattr(resp, "text", None) or ""
        if not text and getattr(resp, "candidates", None):
            parts = resp.candidates[0].content.parts
            text = "".join(getattr(p, "text", "") or "" for p in parts)
        draft = _extract_json(text)
        if not draft:
            return None
        # Preserve hard fields from skeleton
        draft["freeze_priority"] = skeleton["freeze_priority"]
        draft["money_trail"] = skeleton["money_trail"]
        draft["ring_ref"] = skeleton.get("ring_ref", overview["ring_id"])
        draft["case_id"] = skeleton.get("case_id", draft.get("case_id"))
        draft["mode"] = "llm"
        draft["model_id"] = model
        draft["prompt_version"] = settings.prompt_version
        draft["confidence_basis"] = list(
            dict.fromkeys((draft.get("confidence_basis") or []) + ["gemini", "tool_grounded"])
        )
        return draft
    except Exception:
        return None
