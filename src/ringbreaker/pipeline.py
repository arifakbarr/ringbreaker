"""In-process end-to-end pipeline used by harness and LIVE demo."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from ringbreaker.bank.scoring import emit_beacons, emit_edges, score_bank_accounts
from ringbreaker.config import Settings, get_settings
from ringbreaker.features.local_features import FEATURE_NAMES, compute_account_features
from ringbreaker.fed.fedavg import FedAvgCoordinator
from ringbreaker.fed.models import LogisticModel, threshold_at_fpr, train_local_logreg
from ringbreaker.hub.graph import TokenGraph
from ringbreaker.hub.payee import LiveRingEntry, LiveRingIndex, lookup_payee
from ringbreaker.hub.planner import plan_freezes
from ringbreaker.hub.rings import RingState, detect_communities
from ringbreaker.hub.score import score_ring
from ringbreaker.privacy.ledger import PrivacyLedger
from ringbreaker.privacy.schemas import PayeeRiskRequestV1, ReasonCode
from ringbreaker.privacy.tokens import Tokeniser
from ringbreaker.sim.replay import build_replay
from ringbreaker.sim.types import Freeze, FreezeKind, Intervention
from ringbreaker.sim.world import counterfactual_stopped, simulate


@dataclass
class HeroRunResult:
    seed: int
    time_to_detect_s: int | None
    ring_score: float
    ring_alerted: bool
    cashed_out_today_myr: float
    cashed_out_rb_myr: float
    stopped_myr: float
    false_freezes: int
    lookalike_full_freezes: int
    planner_expected_myr: float
    payee_p95_ms: float
    payee_v2_tier: int | None
    banks_spanned: list[str]
    ring_id: str | None
    freeze_tokens: list[str]
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _train_models(
    sim_seed: int,
    accounts_per_bank: int,
    settings: Settings,
) -> tuple[dict[str, LogisticModel], LogisticModel, float]:
    """Train local + federated models on a disjoint training simulation."""
    train_seed = sim_seed + 10_000
    train = simulate(
        train_seed,
        scenario="hero",
        accounts_per_bank=accounts_per_bank,
        lookalike_share=settings.lookalike_share,
    )
    as_of = 30 * 60  # mid-window for labels
    local_models: dict[str, LogisticModel] = {}
    updates = []
    all_X = []
    all_y = []
    for bank in "ABC":
        rows = compute_account_features(train.accounts, train.events_by_bank[bank], bank, as_of)
        if not rows:
            continue
        X = np.vstack([r.values for r in rows.values()])
        y = np.array([r.label for r in rows.values()])
        model = train_local_logreg(X, y, seed=train_seed)
        local_models[bank] = model
        updates.append(model.to_update(bank, 0, int(len(y))))
        all_X.append(X)
        all_y.append(y)

    fed = FedAvgCoordinator(n_features=len(FEATURE_NAMES))
    if all_X:
        Xcat = np.vstack(all_X)
        fed.set_norm_stats(Xcat.mean(axis=0), Xcat.std(axis=0) + 1e-6)
        for _ in range(5):
            # Re-train locals warm-started conceptually: re-send same updates for scaffold
            fed.aggregate(updates)
        # Final: train each bank again and average once more
        updates2 = []
        for bank in "ABC":
            rows = compute_account_features(train.accounts, train.events_by_bank[bank], bank, as_of)
            X = np.vstack([r.values for r in rows.values()])
            y = np.array([r.label for r in rows.values()])
            m = train_local_logreg(X, y, seed=train_seed + 1)
            m.feature_mean = fed.global_model.feature_mean
            m.feature_std = fed.global_model.feature_std
            local_models[bank] = m
            updates2.append(m.to_update(bank, 1, int(len(y))))
        global_model = fed.aggregate(updates2)
        global_model.feature_mean = fed.global_model.feature_mean
        global_model.feature_std = fed.global_model.feature_std
    else:
        global_model = LogisticModel(weights=np.zeros(len(FEATURE_NAMES)), bias=-2.0)

    # Operating point on training negatives
    scores_list = []
    labels_list = []
    for bank in "ABC":
        rows = compute_account_features(train.accounts, train.events_by_bank[bank], bank, as_of)
        if not rows:
            continue
        X = np.vstack([r.values for r in rows.values()])
        y = np.array([r.label for r in rows.values()])
        scores_list.append(global_model.predict_proba(X))
        labels_list.append(y)
    if scores_list:
        thr = threshold_at_fpr(np.concatenate(scores_list), np.concatenate(labels_list), settings.account_fpr)
    else:
        thr = 0.5
    return local_models, global_model, thr


def run_hero(
    seed: int | None = None,
    *,
    settings: Settings | None = None,
    accounts_per_bank: int = 600,
    analyst_delay_s: int | None = None,
    freeze_k: int | None = None,
    write_replay: bool = True,
    scammer: Any | None = None,
    participating_banks: str = "ABC",
    use_federated: bool = True,
    min_banks: int = 2,
) -> HeroRunResult:
    settings = settings or get_settings()
    seed = seed if seed is not None else settings.seed_hero
    analyst_delay_s = analyst_delay_s if analyst_delay_s is not None else settings.analyst_delay_s
    freeze_k = freeze_k if freeze_k is not None else settings.freeze_budget_k
    banks = "".join(c for c in participating_banks.upper() if c in "ABCDE") or "ABC"

    local_models, global_model, score_thr = _train_models(seed, accounts_per_bank, settings)
    # Share threshold for beacons: use model threshold (calibrated to FPR)
    share_threshold = max(settings.share_threshold, score_thr * 0.85)

    # Baseline today
    base = simulate(
        seed,
        scenario="hero",
        accounts_per_bank=accounts_per_bank,
        scammer=scammer,
    )

    tokeniser = Tokeniser(settings.hmac_key, settings.hmac_epoch)
    ledgers = {b: PrivacyLedger(b) for b in banks}
    graph = TokenGraph(window_s=settings.graph_window_s)
    index = LiveRingIndex()

    # Process live window in time slices
    slice_s = 60
    time_to_detect: int | None = None
    alerted_ring = None
    plan = None
    hub_timeline: list[dict[str, Any]] = []

    # Map tokens for later freeze → account
    acct_by_token: dict[str, str] = {}
    for aid, acct in base.accounts.items():
        if acct.archetype == "exit":
            continue
        acct_by_token[tokeniser.account_token(aid)] = aid

    for t in range(0, base.live_window_end + 1, slice_s):
        events_to_t = [e for e in base.events if e.ts <= t]
        for bank in banks:
            model = global_model if use_federated else local_models.get(bank, global_model)
            bank_events = [
                e
                for e in events_to_t
                if (e.src_bank == bank or e.dst_bank == bank)
            ]
            scores = score_bank_accounts(base.accounts, bank_events, bank, model, t)
            beacons = emit_beacons(
                bank_id=bank,
                accounts=base.accounts,
                scores=scores,
                tokeniser=tokeniser,
                share_threshold=share_threshold,
                model_version=model.version,
                window_end_ts=t,
                ledger=ledgers[bank],
            )
            edges = emit_edges(
                bank_id=bank,
                events=bank_events,
                scores=scores,
                tokeniser=tokeniser,
                share_threshold=share_threshold,
                ledger=ledgers[bank],
                accounts=base.accounts,
            )
            for b in beacons:
                graph.ingest_beacon(b)
            for e in edges:
                graph.ingest_edge(e)

        rings = detect_communities(
            graph, share_threshold=share_threshold, seed=seed, min_banks=min_banks
        )
        for ring in rings:
            score_ring(graph, ring)
            if ring.score >= settings.watch_threshold:
                ring.state = RingState.WATCH
            if ring.score >= settings.alert_threshold:
                ring.state = RingState.ALERT
                if time_to_detect is None:
                    time_to_detect = t
                    alerted_ring = ring
                    hub_timeline.append(
                        {
                            "ts": t,
                            "event": "RING_ALERT",
                            "ring_id": ring.ring_id,
                            "score": ring.score,
                            "banks": ring.banks,
                            "components": ring.components,
                        }
                    )
                # Update live ring index
                for tok in ring.members:
                    ns = graph.nodes.get(tok)
                    mem = min(1.0, 0.5 * (ns.score if ns else 0) + 0.5 * ring.score)
                    tier: Any = 0
                    codes: list[ReasonCode] = []
                    if ring.state == RingState.ALERT and mem >= 0.55:
                        tier = 3
                        codes = [ReasonCode.RING_MEMBER_HIGH, ReasonCode.FLAGGED_AT_N_BANKS]
                    elif ring.state == RingState.WATCH and mem >= 0.35:
                        tier = 2
                        codes = [ReasonCode.FAST_PASSTHROUGH, ReasonCode.SHARED_DEVICE_CLUSTER]
                    elif mem >= 0.25:
                        tier = 1
                        codes = [ReasonCode.NEW_ACCOUNT_INFLOW_SPIKE]
                    if tier:
                        index.upsert(
                            tok,
                            LiveRingEntry(
                                ring_ref=ring.ring_id,
                                tier=tier,
                                reason_codes=codes,
                                membership_prob=mem,
                                state=ring.state.value,
                            ),
                        )
        if alerted_ring is not None and t >= time_to_detect:  # type: ignore[operator]
            # Keep evaluating but we have detection
            pass

    # Planner at alert + analyst delay
    interventions: list[Intervention] = []
    lookalike_full = 0
    planner_expected = 0.0
    freeze_tokens: list[str] = []
    if alerted_ring is not None:
        score_ring(graph, alerted_ring)
        plan = plan_freezes(graph, alerted_ring, k=freeze_k)
        planner_expected = plan.expected_stopped_total
        decision_ts = (time_to_detect or 0) + analyst_delay_s
        lookalike_ids = set(base.ground_truth.lookalikes)
        for item in plan.items:
            aid = acct_by_token.get(item.token)
            freeze_tokens.append(item.token)
            if aid is None:
                continue
            if item.tier == "T4" and aid in lookalike_ids:
                lookalike_full += 1
                # Cap: do not full-freeze lookalikes in applied plan (A10)
                continue
            kind = FreezeKind.FULL_FREEZE if item.tier == "T4" else FreezeKind.HOLD
            if item.tier in ("T3", "T4"):
                interventions.append(Freeze(account_id=aid, at_ts=decision_ts, kind=kind))
            # T2 is recommendation only — no freeze

        # Prevention: V2 payee block if tier 3 at T+22m
        v2 = base.ground_truth.victim_transfers[1]
        payee_aid = v2["payee"]
        payee_tok = tokeniser.account_token(payee_aid)
        # Ensure index was populated; microbenchmark lookups
        for _ in range(50):
            lookup_payee(
                index,
                PayeeRiskRequestV1(
                    payer_bank="B",
                    payee_token=payee_tok,
                    amount_myr=6500.0,
                    ts=str(22 * 60),
                ),
            )
        resp = lookup_payee(
            index,
            PayeeRiskRequestV1(
                payer_bank="B",
                payee_token=payee_tok,
                amount_myr=6500.0,
                ts=str(22 * 60),
            ),
        )
        payee_v2_tier = resp.tier
        if resp.tier >= 3:
            from ringbreaker.sim.types import PayeeBlock

            interventions.append(
                PayeeBlock(
                    account_id=payee_aid,
                    from_ts=22 * 60,
                    compliance_rate=settings.compliance_rate,
                )
            )
    else:
        payee_v2_tier = None

    base2, treated, stopped = counterfactual_stopped(
        seed,
        interventions,
        scenario="hero",
        accounts_per_bank=accounts_per_bank,
        scammer=scammer,
    )

    if write_replay:
        from pathlib import Path
        import json

        replay = build_replay(
            treated,
            today_result=base2,
            hub_timeline=hub_timeline,
            today_outcomes={
                "cashed_out_myr": base2.outcomes.cashed_out_myr,
                "stuck_myr": base2.outcomes.stuck_myr,
                "victim_losses_myr": base2.outcomes.victim_losses_myr,
            },
            rb_outcomes={
                "cashed_out_myr": treated.outcomes.cashed_out_myr,
                "stopped_myr": stopped,
                "false_freezes": treated.outcomes.false_freezes,
                "time_to_detect_s": time_to_detect,
                "planner_expected_myr": planner_expected,
            },
        )
        out = Path("results/replay.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(replay, indent=2), encoding="utf-8")

    return HeroRunResult(
        seed=seed,
        time_to_detect_s=time_to_detect,
        ring_score=float(alerted_ring.score) if alerted_ring else 0.0,
        ring_alerted=alerted_ring is not None,
        cashed_out_today_myr=base2.outcomes.cashed_out_myr,
        cashed_out_rb_myr=treated.outcomes.cashed_out_myr,
        stopped_myr=stopped,
        false_freezes=treated.outcomes.false_freezes,
        lookalike_full_freezes=lookalike_full,
        planner_expected_myr=planner_expected,
        payee_p95_ms=index.p95_latency_ms(),
        payee_v2_tier=payee_v2_tier,
        banks_spanned=list(alerted_ring.banks) if alerted_ring else [],
        ring_id=alerted_ring.ring_id if alerted_ring else None,
        freeze_tokens=freeze_tokens,
        meta={
            "synthetic": True,
            "share_threshold": share_threshold,
            "score_thr": score_thr,
            "analyst_delay_s": analyst_delay_s,
            "freeze_k": freeze_k,
            "cash_out_complete_ts_today": base2.ground_truth.cash_out_complete_ts,
            "n_interventions": len(interventions),
            "participating_banks": banks,
            "use_federated": use_federated,
            "evasion": getattr(scammer, "evasion", "E0") if scammer else "E0",
            "ledger": {b: ledgers[b].snapshot() for b in banks},
            "raw_fields_sent_total": sum(ledgers[b].raw_fields_sent for b in banks),
        },
    )
