"""Investigator agent — tools first; LLM optional; template always valid (I7)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ringbreaker.config import Settings, get_settings
from ringbreaker.hub.graph import TokenGraph
from ringbreaker.hub.rings import CandidateRing
from ringbreaker.llm.aliases import AliasMap
from ringbreaker.llm.grounding import validate_case_file
from ringbreaker.llm.notices import build_per_bank_notices
from ringbreaker.llm.templates import build_template_case
from ringbreaker.llm.tools import EvidenceStore, InvestigatorTools


def gather_evidence(
    graph: TokenGraph,
    ring: CandidateRing,
    *,
    first_detection_s: int | None = None,
    lookalike_tokens: set[str] | None = None,
    k: int = 6,
) -> tuple[InvestigatorTools, dict[str, Any]]:
    aliases = AliasMap(ring.ring_id)
    tools = InvestigatorTools(
        graph,
        ring,
        aliases,
        EvidenceStore(),
        lookalikes=lookalike_tokens or set(),
        first_detection_s=first_detection_s,
    )
    overview = tools.get_ring_overview()
    subgraph = tools.get_ring_subgraph()
    plan = tools.plan_freeze(k=k)
    sensitivity = []
    for sig in ("link_density", "flow_through", "cross_bank_span"):
        sensitivity.append(tools.counterfactual_score(sig))
    lookalikes = []
    for node in subgraph.get("nodes", []):
        if node.get("coarse", {}).get("account_age_bucket") == "over_180":
            lookalikes.append(tools.lookalike_check(node["alias"]))
    return tools, {
        "overview": overview,
        "subgraph": subgraph,
        "plan": plan,
        "sensitivity": sensitivity,
        "lookalikes": lookalikes,
    }


def build_case_from_tools(
    tools: InvestigatorTools,
    gathered: dict[str, Any],
    *,
    settings: Settings | None = None,
    mode: str = "template",
    model_id: str = "template",
) -> dict[str, Any]:
    settings = settings or get_settings()
    overview = gathered["overview"]
    subgraph = gathered["subgraph"]
    plan_items = gathered["plan"]["plan"]
    banks = overview.get("banks", [])
    why = [
        {
            "claim": f"Ring score {overview['ring_score']} across {overview['member_count']} accounts",
            "evidence_ids": [overview["evidence_id"]],
        },
        {
            "claim": f"Activity spans {', '.join(banks)}",
            "evidence_ids": [overview["evidence_id"]],
        },
    ]
    if overview.get("components", {}).get("flow_through", 0) >= 0.5:
        why.append(
            {
                "claim": "High pass-through of funds within a short horizon",
                "evidence_ids": [overview["evidence_id"]],
            }
        )
    money_trail = []
    for e in subgraph.get("edges", [])[:12]:
        money_trail.append(
            {
                "from_alias": e["from_alias"],
                "to_alias": e["to_alias"],
                "amount_myr": e["amount_myr"],
                "ts": e["ts"],
                "evidence_id": e["evidence_id"],
            }
        )
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
    counter = []
    for ll in gathered.get("lookalikes", []):
        if ll.get("lookalike"):
            counter.append(
                {
                    "claim": f"{ll['alias']} resembles a stable long-history profile",
                    "evidence_ids": [ll["evidence_id"]],
                }
            )
    notices = build_per_bank_notices(
        freeze_priority,
        risk_tier="high" if overview["ring_score"] >= 0.7 else "medium",
        n_banks=len(banks),
    )
    case = build_template_case(
        ring_ref=overview["ring_id"],
        ring_score=float(overview["ring_score"]),
        banks=banks,
        freeze_priority=freeze_priority,
        why=why,
        money_trail=money_trail,
        prompt_version=settings.prompt_version,
    )
    case["mode"] = mode
    case["model_id"] = model_id
    case["per_bank_notices"] = notices
    case["counter_evidence"] = counter
    case["signal_sensitivity"] = [
        {
            "signal": s["signal"],
            "score_without": s["score_without"],
            "delta": s["delta"],
            "evidence_id": s["evidence_id"],
        }
        for s in gathered.get("sensitivity", [])
    ]
    case["generated_at"] = datetime.now(timezone.utc).isoformat()
    return case


def run_investigator(
    graph: TokenGraph,
    ring: CandidateRing,
    *,
    first_detection_s: int | None = None,
    lookalike_tokens: set[str] | None = None,
    settings: Settings | None = None,
    prefer_llm: bool = False,
) -> dict[str, Any]:
    """Always returns a grounded case file; falls back to template on LLM/validation failure."""
    settings = settings or get_settings()
    tools, gathered = gather_evidence(
        graph,
        ring,
        first_detection_s=first_detection_s,
        lookalike_tokens=lookalike_tokens,
    )
    case = build_case_from_tools(tools, gathered, settings=settings, mode="template", model_id="template")

    # Optional LLM when GEMINI_API_KEY set (AI Studio free tier ok). I7: validate → template.
    if settings.gemini_api_key or prefer_llm:
        if settings.gemini_api_key:
            try:
                from ringbreaker.llm.client import try_llm_case

                llm_case = try_llm_case(tools, gathered, settings)
                if llm_case:
                    case = llm_case
            except Exception:
                case["mode"] = "template"
                case["model_id"] = "template"

    aliases = {n["alias"] for n in gathered["subgraph"]["nodes"]}
    bank_to_aliases: dict[str, set[str]] = {}
    for n in gathered["subgraph"]["nodes"]:
        bank_to_aliases.setdefault(n["bank"], set()).add(n["alias"])
    planner_order = [
        {"alias": p["alias"], "tier": p["tier"]} for p in gathered["plan"]["plan"]
    ]
    tool_amounts = {float(e["amount_myr"]) for e in gathered["subgraph"]["edges"] if e.get("amount_myr") is not None}
    errors = validate_case_file(
        case,
        evidence_ids=tools.evidence.ids(),
        aliases=aliases,
        planner_order=planner_order,
        tool_amounts=tool_amounts,
        bank_to_aliases=bank_to_aliases,
    )
    if errors:
        # repair once via fresh template
        case = build_case_from_tools(
            tools, gathered, settings=settings, mode="template", model_id="template"
        )
        case["_validation_repaired"] = errors
    case["_evidence_ids"] = sorted(tools.evidence.ids())
    case["_aliases"] = tools.aliases.snapshot()
    return case
