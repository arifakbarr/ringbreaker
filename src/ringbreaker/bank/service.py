"""Bank FastAPI service — partition-local console + control endpoints."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ringbreaker import SYNTHETIC_BADGE, __version__
from ringbreaker.config import get_settings
from ringbreaker.privacy.ledger import PrivacyLedger

settings = get_settings()
BANK_ID = os.getenv("BANK_ID", settings.bank_id)
REQUIRE_AUTH = os.getenv("REQUIRE_BANK_AUTH", "0") == "1"

app = FastAPI(title=f"Ringbreaker Bank {BANK_ID}", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

ledger = PrivacyLedger(BANK_ID)
_state: dict = {
    "accounts_visible": 0,
    "last_beacon": None,
    "freezes_applied": [],
}


def _check_write_auth(authorization: str | None) -> None:
    if not REQUIRE_AUTH:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="service-to-service token required")


@app.get("/health")
@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "badge": SYNTHETIC_BADGE, "role": "bank", "bank_id": BANK_ID}


@app.get("/readyz")
def readyz() -> dict:
    return {"status": "ready", "badge": SYNTHETIC_BADGE, "bank_id": BANK_ID}


@app.get("/console")
def console() -> dict:
    """Read-only console: own data + privacy ledger only."""
    return {
        "badge": SYNTHETIC_BADGE,
        "synthetic": True,
        "bank_id": BANK_ID,
        "ledger": ledger.snapshot(),
        "accounts_visible": _state["accounts_visible"],
        "last_beacon": _state["last_beacon"],
        "freezes_applied": _state["freezes_applied"],
        "ts": datetime.now(timezone.utc).isoformat(),
        "note": "This bank sees only its own partition. Hub never holds the HMAC key.",
    }


@app.post("/v1/control/reset")
def reset(authorization: str | None = Header(default=None)) -> dict:
    _check_write_auth(authorization)
    _state["accounts_visible"] = 0
    _state["last_beacon"] = None
    _state["freezes_applied"] = []
    return {"ok": True, "bank_id": BANK_ID}


@app.post("/v1/freeze")
def apply_freeze(body: dict, authorization: str | None = Header(default=None)) -> dict:
    _check_write_auth(authorization)
    _state["freezes_applied"].append({**body, "applied_at": datetime.now(timezone.utc).isoformat()})
    return {"ok": True, "bank_id": BANK_ID, "note": "simulated freeze; analyst-approved path only"}


def create_app() -> FastAPI:
    return app
