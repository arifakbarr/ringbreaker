"""Hub FastAPI service — public UI + APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ringbreaker import SYNTHETIC_BADGE, __version__
from ringbreaker.config import get_settings
from ringbreaker.hub.decisions import AccountDecision
from ringbreaker.hub.demo_state import STATE
from ringbreaker.hub.payee import lookup_payee
from ringbreaker.hub.proof import load_proof
from ringbreaker.llm.warnings import victim_warning
from ringbreaker.privacy.schemas import PayeeRiskRequestV1, PayeeRiskResponseV1

settings = get_settings()
app = FastAPI(title="Ringbreaker Hub", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_gemini_ok: bool | None = None
_ready_detail = "starting"


@app.on_event("startup")
def _startup() -> None:
    global _gemini_ok, _ready_detail
    _gemini_ok = False
    try:
        STATE.load_or_build(force=False)
        _ready_detail = "demo_pack_loaded" if STATE.ready else "demo_pack_pending"
    except Exception as exc:  # noqa: BLE001
        _ready_detail = f"demo_pack_error:{type(exc).__name__}"
    if not settings.gemini_api_key:
        _ready_detail += ";template_fallback_ok"


def _health_payload() -> dict:
    return {"status": "ok", "badge": SYNTHETIC_BADGE, "role": "hub"}


@app.get("/health")
@app.get("/healthz")
def healthz() -> dict:
    return _health_payload()


@app.get("/readyz")
def readyz() -> dict:
    return {
        "status": "ready" if STATE.ready or _ready_detail.startswith("demo_pack") else "degraded",
        "badge": SYNTHETIC_BADGE,
        "free_mode": settings.free_mode,
        "gemini_smoke": _gemini_ok,
        "gemini_api_key_set": bool(settings.gemini_api_key),
        "detail": _ready_detail,
        "model": settings.gemini_model,
        "location": settings.gemini_location,
        "gcp_project": settings.gcp_project,
        "cases": len(STATE.cases),
    }


@app.post("/v1/payee-risk", response_model=PayeeRiskResponseV1)
def payee_risk(req: PayeeRiskRequestV1) -> PayeeRiskResponseV1:
    STATE.load_or_build()
    return lookup_payee(STATE.index, req)


@app.get("/v1/meta")
def meta() -> dict:
    return {
        "badge": SYNTHETIC_BADGE,
        "version": __version__,
        "mode": settings.mode,
        "seed_hero": settings.seed_hero,
        "synthetic": True,
        "privacy": "privacy by design on pseudonymised data",
        "free_mode": settings.free_mode,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/v1/replay")
def get_replay() -> dict:
    STATE.load_or_build()
    if not STATE.replay:
        raise HTTPException(404, "replay not ready")
    return STATE.replay


@app.get("/v1/hero")
def get_hero() -> dict:
    STATE.load_or_build()
    return {"synthetic": True, "badge": SYNTHETIC_BADGE, "hero": STATE.hero_metrics}


@app.get("/cases")
def list_cases() -> dict:
    STATE.load_or_build()
    return {
        "badge": SYNTHETIC_BADGE,
        "cases": [
            {
                "case_id": c["case_id"],
                "headline": c.get("headline"),
                "mode": c.get("mode"),
                "risk_level": c.get("risk_level"),
            }
            for c in STATE.cases.values()
        ],
    }


@app.get("/cases/{case_id}")
def get_case(case_id: str) -> dict:
    STATE.load_or_build()
    case = STATE.cases.get(case_id)
    if not case:
        # single-case demo: return the only case
        if len(STATE.cases) == 1:
            case = next(iter(STATE.cases.values()))
        else:
            raise HTTPException(404, "case not found")
    # Live-apply feedback demotions for UI without forcing rebuild
    out = dict(case)
    if out.get("freeze_priority") and STATE.feedback.suppressed_aliases:
        out["freeze_priority"] = STATE.feedback.apply_to_plan(list(out["freeze_priority"]))
        out["feedback_applied"] = sorted(STATE.feedback.suppressed_aliases)
    return out


class DecisionBody(BaseModel):
    accounts: list[dict[str, Any]] = Field(default_factory=list)
    analyst_id: str = "demo-analyst"
    feedback: list[dict[str, Any]] = Field(default_factory=list)


@app.post("/cases/{case_id}/decision")
def post_decision(case_id: str, body: DecisionBody) -> dict:
    STATE.load_or_build()
    case = STATE.cases.get(case_id) or (
        next(iter(STATE.cases.values())) if STATE.cases else None
    )
    if not case:
        raise HTTPException(404, "case not found")
    accounts = [
        AccountDecision(
            alias=a["alias"],
            action=a.get("action", "approve"),
            tier=a.get("tier"),
            reason_code=a.get("reason_code"),
            note=a.get("note", ""),
        )
        for a in body.accounts
    ]
    if not accounts:
        accounts = [
            AccountDecision(alias=fp["alias"], action="approve", tier=fp.get("tier"))
            for fp in case.get("freeze_priority", [])
        ]
    # Feedback loop: LOOKS_LEGIT / reject → suppress alias on next plan
    feedback_events = []
    for fb in body.feedback:
        alias = fb.get("alias")
        if not alias:
            continue
        action = fb.get("action", "suppress")
        reason = fb.get("reason_code") or fb.get("reason") or "LOOKS_LEGIT"
        feedback_events.append(
            STATE.feedback.record(
                case_id=case["case_id"],
                alias=alias,
                action=action,
                reason=reason,
                note=fb.get("note", ""),
            )
        )
    for a in accounts:
        if a.action == "reject" or a.reason_code == "LOOKS_LEGIT":
            feedback_events.append(
                STATE.feedback.record(
                    case_id=case["case_id"],
                    alias=a.alias,
                    action="suppress",
                    reason=a.reason_code or "LOOKS_LEGIT",
                    note=a.note,
                )
            )
    rec = STATE.decisions.append(
        case_id=case["case_id"],
        ring_version=1,
        model_id=case.get("model_id", "template"),
        prompt_version=case.get("prompt_version", settings.prompt_version),
        evidence_ids=case.get("_evidence_ids", []),
        accounts=accounts,
        analyst_id=body.analyst_id,
    )
    notices = case.get("per_bank_notices", {})
    return {
        "ok": True,
        "decision": {
            "decision_id": rec.decision_id,
            "hash": rec.hash,
            "prev_hash": rec.prev_hash,
        },
        "notices": notices,
        "feedback": feedback_events,
        "feedback_summary": STATE.feedback.summary(),
        "badge": SYNTHETIC_BADGE,
        "note": "Analyst approved — banks apply simulated freezes. Not autonomous.",
    }


@app.get("/v1/feedback")
def get_feedback() -> dict:
    STATE.load_or_build()
    return STATE.feedback.summary()


@app.get("/v1/privacy")
def get_privacy() -> dict:
    STATE.load_or_build()
    ledgers = (STATE.hero_metrics or {}).get("meta", {}).get("ledger", {})
    raw_total = sum(int(v.get("raw_fields_sent", 0)) for v in ledgers.values())
    return {
        "synthetic": True,
        "claim": "privacy by design on pseudonymised data",
        "not_a_compliance_claim": True,
        "raw_fields_sent_total": raw_total,
        "ledgers": ledgers,
        "badge": SYNTHETIC_BADGE,
    }


@app.get("/v1/proof")
def get_proof() -> dict:
    """Judge-facing scoreboard, copied from results/results.json (never hand-typed)."""
    return {**load_proof(), "badge": SYNTHETIC_BADGE}


@app.get("/v1/decisions/export")
def export_decisions() -> dict:
    return {
        "synthetic": True,
        "verified": STATE.decisions.verify(),
        "records": STATE.decisions.export(),
    }


@app.get("/v1/warnings/victim")
def warning(tier: int = 3, lang: str = "en") -> dict:
    return victim_warning(tier, lang=lang if lang in ("en", "ms") else "en")  # type: ignore[arg-type]


@app.post("/v1/demo/rebuild")
def rebuild_demo() -> dict:
    """Expensive — rebuilds demo_pack from seed (local/admin)."""
    STATE.load_or_build(force=True)
    return {"ok": True, "cases": list(STATE.cases.keys()), "badge": SYNTHETIC_BADGE}


UI_DIR = Path(__file__).resolve().parents[3] / "ui" / "dist"
RECORDED_DIR = UI_DIR / "recorded"
# Dev fallback: Vite public copy before dist rebuild
RECORDED_PUBLIC = Path(__file__).resolve().parents[3] / "ui" / "public" / "recorded"


@app.get("/", response_model=None)
def root():
    index = UI_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return HTMLResponse(
        "<!doctype html><meta charset=utf-8><title>Ringbreaker</title>"
        "<p>UI not built. Run <code>cd ui && npm ci && npm run build</code>.</p>"
    )


if UI_DIR.exists():
    assets = UI_DIR / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

_recorded_serve = RECORDED_DIR if RECORDED_DIR.exists() else RECORDED_PUBLIC
if _recorded_serve.exists():
    app.mount("/recorded", StaticFiles(directory=_recorded_serve), name="recorded")
