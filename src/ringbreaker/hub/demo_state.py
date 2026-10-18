"""In-process demo state for hub APIs (hero case + replay)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ringbreaker.config import get_settings
from ringbreaker.hub.decisions import DecisionLog
from ringbreaker.hub.feedback import FeedbackStore
from ringbreaker.hub.payee import LiveRingEntry, LiveRingIndex
from ringbreaker.llm.agent import run_investigator
from ringbreaker.pipeline import run_hero
from ringbreaker.privacy.schemas import ReasonCode
from ringbreaker.privacy.tokens import Tokeniser


ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "results"
DEMO_PACK = RESULTS / "demo_pack.json"


@dataclass
class DemoState:
    cases: dict[str, dict[str, Any]] = field(default_factory=dict)
    replay: dict[str, Any] | None = None
    hero_metrics: dict[str, Any] = field(default_factory=dict)
    index: LiveRingIndex = field(default_factory=LiveRingIndex)
    decisions: DecisionLog = field(
        default_factory=lambda: DecisionLog(RESULTS / "decisions.jsonl")
    )
    feedback: FeedbackStore = field(
        default_factory=lambda: FeedbackStore(RESULTS / "feedback.jsonl")
    )
    ready: bool = False

    def load_or_build(self, force: bool = False) -> None:
        if self.ready and not force:
            return
        if DEMO_PACK.exists() and not force:
            pack = json.loads(DEMO_PACK.read_text(encoding="utf-8"))
            self.cases = {c["case_id"]: c for c in pack.get("cases", [])}
            self.replay = pack.get("replay")
            self.hero_metrics = pack.get("hero_metrics", {})
            for tok, entry in pack.get("payee_index", {}).items():
                self.index.upsert(
                    tok,
                    LiveRingEntry(
                        ring_ref=entry["ring_ref"],
                        tier=entry["tier"],
                        reason_codes=[ReasonCode(c) for c in entry.get("reason_codes", [])],
                        membership_prob=entry.get("membership_prob", 0.5),
                        state=entry.get("state", "ALERT"),
                    ),
                )
            self.ready = True
            return
        self.build_from_hero()

    def build_from_hero(self) -> None:
        settings = get_settings()
        hero = run_hero(settings.seed_hero, accounts_per_bank=400, write_replay=True)
        replay_path = RESULTS / "replay.json"
        replay = json.loads(replay_path.read_text(encoding="utf-8")) if replay_path.exists() else {}

        # Rebuild minimal graph path via pipeline internals is heavy; use template case from hero meta
        from ringbreaker.hub.graph import TokenGraph
        from ringbreaker.hub.rings import CandidateRing, RingState
        from ringbreaker.hub.score import score_ring
        from ringbreaker.sim.world import simulate
        from ringbreaker.bank.scoring import emit_beacons, emit_edges, score_bank_accounts
        from ringbreaker.pipeline import _train_models
        from ringbreaker.privacy.ledger import PrivacyLedger

        local_models, global_model, score_thr = _train_models(settings.seed_hero, 400, settings)
        share_threshold = max(settings.share_threshold, score_thr * 0.85)
        base = simulate(settings.seed_hero, scenario="hero", accounts_per_bank=400)
        tokeniser = Tokeniser(settings.hmac_key, settings.hmac_epoch)
        graph = TokenGraph()
        t_detect = hero.time_to_detect_s or 540
        events_to_t = [e for e in base.events if e.ts <= t_detect]
        for bank in "ABC":
            bank_events = [e for e in events_to_t if e.src_bank == bank or e.dst_bank == bank]
            scores = score_bank_accounts(base.accounts, bank_events, bank, global_model, t_detect)
            ledgers = PrivacyLedger(bank)
            for b in emit_beacons(
                bank_id=bank,
                accounts=base.accounts,
                scores=scores,
                tokeniser=tokeniser,
                share_threshold=share_threshold,
                model_version=global_model.version,
                window_end_ts=t_detect,
                ledger=ledgers,
            ):
                graph.ingest_beacon(b)
            for e in emit_edges(
                bank_id=bank,
                events=bank_events,
                scores=scores,
                tokeniser=tokeniser,
                share_threshold=share_threshold,
                ledger=ledgers,
                accounts=base.accounts,
            ):
                graph.ingest_edge(e)

        from ringbreaker.hub.rings import detect_communities

        rings = detect_communities(graph, share_threshold=share_threshold, seed=settings.seed_hero)
        alerted = None
        for r in rings:
            score_ring(graph, r)
            if r.score >= settings.alert_threshold:
                r.state = RingState.ALERT
                alerted = r
                break
        if alerted is None and rings:
            alerted = max(rings, key=lambda r: score_ring(graph, r).score)
            alerted.state = RingState.ALERT

        lookalike_toks = {
            tokeniser.account_token(a) for a in base.ground_truth.lookalikes if a in base.accounts
        }
        case = (
            run_investigator(
                graph,
                alerted,
                first_detection_s=t_detect,
                lookalike_tokens=lookalike_toks,
                settings=settings,
            )
            if alerted
            else {
                "case_id": "CASE-EMPTY",
                "mode": "template",
                "headline": "No ring alert in simulation",
                "freeze_priority": [],
                "per_bank_notices": {},
                "why_suspicious": [],
                "money_trail": [],
            }
        )
        # Apply analyst feedback demotions before baking the pack
        if case.get("freeze_priority"):
            case["freeze_priority"] = self.feedback.apply_to_plan(case["freeze_priority"])
            case["feedback_applied"] = sorted(self.feedback.suppressed_aliases)
        self.cases = {case["case_id"]: case}
        self.replay = replay
        self.hero_metrics = hero.to_dict()

        # Seed payee index for V2 payee
        if alerted:
            for tok in alerted.members:
                self.index.upsert(
                    tok,
                    LiveRingEntry(
                        ring_ref=alerted.ring_id,
                        tier=3,
                        reason_codes=[ReasonCode.RING_MEMBER_HIGH, ReasonCode.FLAGGED_AT_N_BANKS],
                        membership_prob=0.8,
                        state="ALERT",
                    ),
                )

        pack = {
            "synthetic": True,
            "cases": list(self.cases.values()),
            "replay": replay,
            "hero_metrics": self.hero_metrics,
            "payee_index": {
                tok: {
                    "ring_ref": e.ring_ref,
                    "tier": e.tier,
                    "reason_codes": [c.value for c in e.reason_codes],
                    "membership_prob": e.membership_prob,
                    "state": e.state,
                }
                for tok, e in self.index.by_token.items()
            },
        }
        RESULTS.mkdir(parents=True, exist_ok=True)
        DEMO_PACK.write_text(json.dumps(pack, indent=2), encoding="utf-8")
        self.ready = True


STATE = DemoState()
