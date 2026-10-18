"""Runtime configuration (env-driven; no secrets in code)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    free_mode: bool = field(
        default_factory=lambda: os.getenv("FREE_MODE", "1").strip() not in ("0", "false", "False")
    )
    gcp_project: str = field(
        default_factory=lambda: os.getenv("GCP_PROJECT", "ringbreaker-aether-2026")
    )
    gemini_api_key: str = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "")
    )  # Google AI Studio free key; empty → template only
    gemini_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    )
    gemini_model_deep: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL_DEEP", "")
    )
    gemini_location: str = field(
        default_factory=lambda: os.getenv("GEMINI_LOCATION", "asia-southeast1")
    )
    prompt_version: str = field(
        default_factory=lambda: os.getenv("PROMPT_VERSION", "v1")
    )
    hmac_key: str = field(
        default_factory=lambda: os.getenv(
            "RINGBREAKER_HMAC_KEY", "SYNTHETIC-DEV-KEY-NOT-FOR-PRODUCTION"
        )
    )
    hmac_epoch: str = field(default_factory=lambda: os.getenv("HMAC_EPOCH", "e1"))
    hub_url: str = field(default_factory=lambda: os.getenv("HUB_URL", "http://localhost:8080"))
    bank_urls: str = field(
        default_factory=lambda: os.getenv(
            "BANK_URLS",
            "A=http://localhost:8081,B=http://localhost:8082,C=http://localhost:8083",
        )
    )
    seed_hero: int = field(
        default_factory=lambda: int(os.getenv("SEED_HERO", "103"))
    )
    mode: str = field(default_factory=lambda: os.getenv("MODE", "LIVE"))
    service_role: str = field(
        default_factory=lambda: os.getenv("SERVICE_ROLE", "hub")
    )  # hub | bank
    bank_id: str = field(default_factory=lambda: os.getenv("BANK_ID", "A"))
    analyst_delay_s: int = 120
    freeze_budget_k: int = 6
    share_threshold: float = 0.35
    watch_threshold: float = 0.45
    alert_threshold: float = 0.62
    account_fpr: float = 0.005
    lookalike_share: float = 0.015
    accounts_per_bank: int = 4000
    graph_window_s: int = 6 * 3600
    compliance_rate: float = 0.70


def get_settings() -> Settings:
    return Settings()
