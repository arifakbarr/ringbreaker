"""Seeded world generation and top-level simulate()."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal

import numpy as np

from ringbreaker.sim.intervene import freeze_set, is_payee_blocked
from ringbreaker.sim.rings import RingPlan, ScammerParams, allocate_ring_accounts, hero_scammer_params
from ringbreaker.sim.types import (
    Account,
    Archetype,
    BankId,
    Freeze,
    GroundTruth,
    Intervention,
    Outcomes,
    SimulationResult,
    TransferEvent,
)

BANK_PERSONALITY: dict[BankId, dict[str, Any]] = {
    "A": {"label": "retail", "young_share": 0.15, "merchant_share": 0.08},
    "B": {"label": "sme", "young_share": 0.20, "merchant_share": 0.25},
    "C": {"label": "digital", "young_share": 0.55, "merchant_share": 0.12},
    "D": {"label": "mixed", "young_share": 0.30, "merchant_share": 0.15},
    "E": {"label": "credit_union", "young_share": 0.25, "merchant_share": 0.10},
}

ARCHETYPE_WEIGHTS: dict[str, list[tuple[Archetype, float]]] = {
    "retail": [
        ("salaried", 0.45),
        ("landlord", 0.08),
        ("gig_worker", 0.12),
        ("student_p2p", 0.10),
        ("qr_merchant", 0.08),
        ("sme_payroll", 0.07),
        ("remittance_agent", 0.05),
        ("small_seller", 0.05),
    ],
    "sme": [
        ("sme_payroll", 0.20),
        ("qr_merchant", 0.22),
        ("salaried", 0.25),
        ("remittance_agent", 0.08),
        ("small_seller", 0.10),
        ("landlord", 0.05),
        ("gig_worker", 0.05),
        ("student_p2p", 0.05),
    ],
    "digital": [
        ("student_p2p", 0.28),
        ("gig_worker", 0.18),
        ("salaried", 0.22),
        ("qr_merchant", 0.10),
        ("small_seller", 0.08),
        ("student_treasurer", 0.04),
        ("remittance_agent", 0.05),
        ("landlord", 0.05),
    ],
    "mixed": [
        ("salaried", 0.30),
        ("student_p2p", 0.15),
        ("qr_merchant", 0.15),
        ("gig_worker", 0.15),
        ("sme_payroll", 0.10),
        ("landlord", 0.05),
        ("remittance_agent", 0.05),
        ("small_seller", 0.05),
    ],
    "credit_union": [
        ("salaried", 0.40),
        ("landlord", 0.12),
        ("student_p2p", 0.12),
        ("gig_worker", 0.12),
        ("qr_merchant", 0.08),
        ("sme_payroll", 0.06),
        ("small_seller", 0.05),
        ("remittance_agent", 0.05),
    ],
}

LOOKALIKE_ARCHETYPES: set[Archetype] = {"remittance_agent", "small_seller", "student_treasurer"}


def _spawn_rng(seed: int, name: str) -> np.random.Generator:
    """Named substream from master seed (deterministic, no global RNG)."""
    ss = np.random.SeedSequence(seed)
    child = ss.spawn(1)[0]
    # Mix name into entropy
    name_entropy = abs(hash(name)) % (2**32)
    return np.random.default_rng(child.generate_state(2, dtype=np.uint32).tolist() + [name_entropy])


def _pick_archetype(rng: np.random.Generator, personality: str) -> Archetype:
    items = ARCHETYPE_WEIGHTS[personality]
    labels, weights = zip(*items)
    return rng.choice(list(labels), p=np.array(weights) / sum(weights))  # type: ignore[return-value]


def _acct_id(bank: BankId, n: int) -> str:
    # Bank-specific synthetic formats (not real)
    prefixes = {"A": "88", "B": "77", "C": "66", "D": "55", "E": "44"}
    return f"{bank}{prefixes[bank]}{n:08d}"


def build_world(
    seed: int,
    accounts_per_bank: int = 800,
    lookalike_share: float = 0.015,
) -> dict[str, Account]:
    rng = _spawn_rng(seed, "world")
    accounts: dict[str, Account] = {}
    banks: list[BankId] = ["A", "B", "C", "D", "E"]

    # Shared household devices / CGNAT IPs (weak evidence)
    household_devices = [f"dev-hh-{i}" for i in range(max(20, accounts_per_bank // 40))]
    cgnat_ips = [f"100.64.{i // 250}.{i % 250}" for i in range(80)]

    for bank in banks:
        personality = BANK_PERSONALITY[bank]["label"]
        for i in range(accounts_per_bank):
            aid = _acct_id(bank, i)
            arch = _pick_archetype(rng, personality)
            young = rng.random() < BANK_PERSONALITY[bank]["young_share"]
            age = int(rng.integers(5, 90) if young else rng.integers(90, 4000))
            phone = f"+601{rng.integers(1, 9)}{rng.integers(1000000, 9999999)}"
            if rng.random() < 0.12:
                device = rng.choice(household_devices)
            else:
                device = f"dev-{bank}-{i}-{rng.integers(1, 1_000_000)}"
            if rng.random() < 0.25:
                ip = rng.choice(cgnat_ips)
            else:
                ip = f"14.{rng.integers(0, 255)}.{rng.integers(0, 255)}.{rng.integers(1, 254)}"
            bal = float(rng.uniform(50, 25_000))
            if arch in ("remittance_agent", "sme_payroll", "qr_merchant"):
                bal = float(rng.uniform(5_000, 120_000))
            accounts[aid] = Account(
                account_id=aid,
                bank_id=bank,
                archetype=arch,
                age_days=age,
                kyc_tier=3 if arch == "remittance_agent" else int(rng.integers(1, 4)),
                phone=phone,
                device_id=device,
                ip=ip,
                balance_myr=bal,
            )

    # Mark lookalikes (~lookalike_share)
    candidates = [
        a
        for a in accounts.values()
        if a.archetype in LOOKALIKE_ARCHETYPES and a.age_days > 365
    ]
    n_look = max(1, int(len(accounts) * lookalike_share))
    rng.shuffle(candidates)
    for a in candidates[:n_look]:
        a.is_lookalike = True

    return accounts


def _split_amount(rng: np.random.Generator, total: float, n: int, limit: float) -> list[float]:
    if n <= 0:
        return []
    if total <= 0:
        return [0.0] * n
    # Prefer splits under structuring limit
    weights = rng.dirichlet(np.ones(n))
    parts = (weights * total).tolist()
    # Cap and redistribute if needed
    for _ in range(5):
        over = [i for i, p in enumerate(parts) if p > limit]
        if not over:
            break
        for i in over:
            excess = parts[i] - limit
            parts[i] = limit
            under = [j for j, p in enumerate(parts) if p < limit * 0.9]
            if not under:
                break
            add = excess / len(under)
            for j in under:
                parts[j] += add
    return [round(p, 2) for p in parts]


def _emit_ring_flows(
    rng: np.random.Generator,
    accounts: dict[str, Account],
    plan: RingPlan,
    victim_event: TransferEvent,
    edge_counter: list[int],
    interventions: list[Intervention],
    compliance_rng: np.random.Generator,
) -> list[TransferEvent]:
    """Propagate victim funds through layers to exits. Supports freezes mid-path."""
    events: list[TransferEvent] = []
    params = plan.params
    frozen = freeze_set(interventions, victim_event.ts)

    # balances held in-ring (account_id -> amount still movable)
    in_flight: dict[str, float] = {}

    # Funds arrive on victim_event.dst_account; onward from that account's layer.
    entry = victim_event.dst_account
    if entry in frozen:
        return events
    in_flight[entry] = victim_event.amount_myr
    accounts[entry].balance_myr += victim_event.amount_myr

    start_layer = 0
    for li, layer in enumerate(plan.layers):
        if entry in layer:
            start_layer = li
            break

    t = victim_event.ts
    for layer_i in range(start_layer, len(plan.layers)):
        dwell_s = int(
            params.dwell_minutes_per_layer[min(layer_i, len(params.dwell_minutes_per_layer) - 1)] * 60
        )
        t = t + dwell_s
        frozen = freeze_set(interventions, t)

        # Current layer holds in-flight funds; push to next layer or exits.
        sources = plan.layers[layer_i]
        if layer_i + 1 < len(plan.layers):
            dests = plan.layers[layer_i + 1]
        else:
            dests = plan.exits

        for src in sources:
            amt = in_flight.get(src, 0.0)
            if amt <= 0:
                continue
            if src in frozen:
                continue
            # Payee block on destination (prevention) — rare mid-ring
            parts = _split_amount(rng, amt, len(dests), params.structuring_limit_myr)
            moved = 0.0
            for dst, part in zip(dests, parts):
                if part <= 0:
                    continue
                if is_payee_blocked(interventions, dst, t, float(compliance_rng.random())):
                    continue
                if dst in frozen:
                    continue
                edge_counter[0] += 1
                src_acct = accounts[src]
                dst_acct = accounts.get(dst)
                src_bank: BankId | Literal["EXT"] = src_acct.bank_id
                if dst.startswith("EXT-"):
                    dst_bank: BankId | Literal["EXT"] = "EXT"
                    channel: Any = "cash_out_exit"
                else:
                    assert dst_acct is not None
                    dst_bank = dst_acct.bank_id
                    channel = "duitnow_transfer" if src_bank != dst_bank else "interbank_transfer"
                ev = TransferEvent(
                    edge_id=f"E{edge_counter[0]:06d}",
                    src_account=src,
                    dst_account=dst,
                    src_bank=src_bank,
                    dst_bank=dst_bank,
                    amount_myr=part,
                    ts=t + int(rng.integers(0, 30)),
                    channel=channel,
                    is_ring=True,
                )
                events.append(ev)
                accounts[src].balance_myr -= part
                if dst in accounts:
                    accounts[dst].balance_myr += part
                in_flight[dst] = in_flight.get(dst, 0.0) + part
                moved += part
            in_flight[src] = max(0.0, amt - moved)

    return events


def _legit_noise(
    rng: np.random.Generator,
    accounts: dict[str, Account],
    live_start: int,
    live_end: int,
    edge_counter: list[int],
    n_events: int = 400,
) -> list[TransferEvent]:
    """Background legitimate traffic in the live window."""
    events: list[TransferEvent] = []
    pool = [a for a in accounts.values() if not a.is_ring and a.archetype != "exit"]
    if len(pool) < 2:
        return events
    channels = ["duitnow_transfer", "duitnow_qr", "interbank_transfer"]
    for _ in range(n_events):
        src, dst = rng.choice(pool, size=2, replace=False)
        ts = int(rng.integers(live_start, live_end))
        amt = float(rng.choice([20, 50, 100, 200, 500, 1000, 2500]) * rng.uniform(0.8, 1.2))
        # Remittance agents / sellers: higher throughput
        if src.archetype == "remittance_agent":
            amt = float(rng.uniform(500, 8000))
        edge_counter[0] += 1
        ch = rng.choice(channels)
        events.append(
            TransferEvent(
                edge_id=f"E{edge_counter[0]:06d}",
                src_account=src.account_id,
                dst_account=dst.account_id,
                src_bank=src.bank_id,
                dst_bank=dst.bank_id,
                amount_myr=round(amt, 2),
                ts=ts,
                channel=ch,  # type: ignore[arg-type]
                is_ring=False,
            )
        )
    return events


def _lookalike_overlap_traffic(
    rng: np.random.Generator,
    accounts: dict[str, Account],
    live_start: int,
    live_end: int,
    edge_counter: list[int],
) -> list[TransferEvent]:
    """Ensure remittance agent (B) and small seller (C) have traffic in the hero window."""
    events: list[TransferEvent] = []
    b_agents = [
        a
        for a in accounts.values()
        if a.bank_id == "B" and a.is_lookalike and a.archetype == "remittance_agent"
    ]
    c_sellers = [
        a
        for a in accounts.values()
        if a.bank_id == "C" and a.is_lookalike and a.archetype == "small_seller"
    ]
    if not b_agents:
        # Force one
        pool = [a for a in accounts.values() if a.bank_id == "B" and a.archetype == "remittance_agent"]
        if pool:
            pool[0].is_lookalike = True
            b_agents = [pool[0]]
    if not c_sellers:
        pool = [a for a in accounts.values() if a.bank_id == "C" and a.archetype == "small_seller"]
        if pool:
            pool[0].is_lookalike = True
            c_sellers = [pool[0]]

    payers = [a for a in accounts.values() if not a.is_ring and a.bank_id in ("A", "B", "C")]
    for agent in b_agents[:1]:
        for _ in range(12):
            payer = rng.choice(payers)
            edge_counter[0] += 1
            events.append(
                TransferEvent(
                    edge_id=f"E{edge_counter[0]:06d}",
                    src_account=payer.account_id,
                    dst_account=agent.account_id,
                    src_bank=payer.bank_id,
                    dst_bank=agent.bank_id,
                    amount_myr=round(float(rng.uniform(800, 6000)), 2),
                    ts=int(rng.integers(live_start, live_end)),
                    channel="duitnow_transfer",
                    is_ring=False,
                )
            )
    for seller in c_sellers[:1]:
        for _ in range(10):
            payer = rng.choice(payers)
            edge_counter[0] += 1
            events.append(
                TransferEvent(
                    edge_id=f"E{edge_counter[0]:06d}",
                    src_account=payer.account_id,
                    dst_account=seller.account_id,
                    src_bank=payer.bank_id,
                    dst_bank=seller.bank_id,
                    amount_myr=round(float(rng.uniform(30, 400)), 2),
                    ts=int(rng.integers(live_start, live_end)),
                    channel="duitnow_qr",
                    is_ring=False,
                )
            )
    return events


def simulate(
    seed: int,
    scenario: str = "hero",
    interventions: list[Intervention] | None = None,
    *,
    accounts_per_bank: int = 800,
    lookalike_share: float = 0.015,
    scammer: ScammerParams | None = None,
    live_window_s: int = 3 * 3600,
) -> SimulationResult:
    """
    Pure function: seeded world + scenario + interventions → events, ground truth, outcomes.

    Time is integer simulated seconds from scenario epoch T0=0 for the live window.
    History (30d) is summarised in account age / balances only for Tier 1 speed.
    """
    interventions = list(interventions or [])
    world_rng = _spawn_rng(seed, "world")
    rings_rng = _spawn_rng(seed, "rings")
    victims_rng = _spawn_rng(seed, "victims")
    noise_rng = _spawn_rng(seed, "noise")
    compliance_rng = _spawn_rng(seed, "compliance")

    accounts = build_world(seed, accounts_per_bank=accounts_per_bank, lookalike_share=lookalike_share)
    live_start = 0
    live_end = live_window_s
    edge_counter = [0]

    if scammer is None:
        scammer = hero_scammer_params() if scenario == "hero" else ScammerParams()

    ring_id = f"R-{seed}-1"
    plan = allocate_ring_accounts(
        rings_rng,
        accounts,
        scammer,
        ring_id,
        prefer_banks=["A", "B", "C"] if scenario == "hero" else None,
    )

    # Victims
    victims: list[Account] = []
    # V1: Bank C customer
    v1_pool = [a for a in accounts.values() if a.bank_id == "C" and not a.is_ring and not a.is_lookalike]
    v1 = v1_pool[int(victims_rng.integers(0, len(v1_pool)))]
    victims.append(v1)
    # V2: Bank B customer
    v2_pool = [a for a in accounts.values() if a.bank_id == "B" and not a.is_ring and a.account_id != v1.account_id]
    v2 = v2_pool[int(victims_rng.integers(0, len(v2_pool)))]
    victims.append(v2)

    events: list[TransferEvent] = []

    # V1 pays collector M1 at T0 — RM 40,000
    collector = plan.collectors[0]
    v1_amt = 40_000.0 if scenario == "hero" else float(victims_rng.uniform(5_000, 50_000))
    if not is_payee_blocked(interventions, collector, 0, float(compliance_rng.random())):
        edge_counter[0] += 1
        v1_ev = TransferEvent(
            edge_id=f"E{edge_counter[0]:06d}",
            src_account=v1.account_id,
            dst_account=collector,
            src_bank=v1.bank_id,
            dst_bank=accounts[collector].bank_id,
            amount_myr=v1_amt,
            ts=0,
            channel="duitnow_transfer",
            is_ring=True,
            victim_id=v1.account_id,
        )
        events.append(v1_ev)
        accounts[v1.account_id].balance_myr -= v1_amt
        ring_events = _emit_ring_flows(
            rings_rng, accounts, plan, v1_ev, edge_counter, interventions, compliance_rng
        )
        events.extend(ring_events)
    else:
        v1_amt = 0.0

    # V2 tries at T+22 minutes — RM 6,500 to a second-layer mule
    v2_ts = 22 * 60
    v2_amt = 6_500.0 if scenario == "hero" else float(victims_rng.uniform(1_000, 10_000))
    layer2 = plan.layers[1] if len(plan.layers) > 1 else plan.collectors
    payee2 = layer2[min(1, len(layer2) - 1)]
    v2_sent = 0.0
    if not is_payee_blocked(interventions, payee2, v2_ts, float(compliance_rng.random())):
        frozen = freeze_set(interventions, v2_ts)
        if payee2 not in frozen:
            edge_counter[0] += 1
            v2_ev = TransferEvent(
                edge_id=f"E{edge_counter[0]:06d}",
                src_account=v2.account_id,
                dst_account=payee2,
                src_bank=v2.bank_id,
                dst_bank=accounts[payee2].bank_id,
                amount_myr=v2_amt,
                ts=v2_ts,
                channel="duitnow_transfer",
                is_ring=True,
                victim_id=v2.account_id,
            )
            events.append(v2_ev)
            accounts[v2.account_id].balance_myr -= v2_amt
            v2_sent = v2_amt
            # Partial onward hop
            ring_events2 = _emit_ring_flows(
                rings_rng, accounts, plan, v2_ev, edge_counter, interventions, compliance_rng
            )
            events.extend(ring_events2)

    # Background + lookalike overlap
    events.extend(_legit_noise(noise_rng, accounts, live_start, live_end, edge_counter))
    events.extend(_lookalike_overlap_traffic(noise_rng, accounts, live_start, live_end, edge_counter))

    events.sort(key=lambda e: (e.ts, e.edge_id))

    # Outcomes
    cashed = sum(e.amount_myr for e in events if e.channel == "cash_out_exit")
    ring_member_ids = [a.account_id for a in accounts.values() if a.is_ring and a.archetype == "mule"]
    stuck = sum(max(0.0, accounts[aid].balance_myr) for aid in ring_member_ids) * 0.0
    # Stuck = ring funds still in mule accounts that did not exit
    ring_in = sum(e.amount_myr for e in events if e.victim_id)
    stuck = max(0.0, ring_in - cashed)

    frozen_legit: list[str] = []
    for iv in interventions:
        if isinstance(iv, Freeze):
            acct = accounts.get(iv.account_id)
            if acct and not acct.is_ring:
                frozen_legit.append(iv.account_id)

    victim_losses = {
        v1.account_id: v1_amt,
        v2.account_id: v2_sent,
    }

    cash_out_ts = None
    exit_events = [e for e in events if e.channel == "cash_out_exit"]
    if exit_events:
        # When cumulative exit reaches ~victim principal
        cum = 0.0
        for e in sorted(exit_events, key=lambda x: x.ts):
            cum += e.amount_myr
            if cum >= v1_amt * 0.95:
                cash_out_ts = e.ts
                break
        if cash_out_ts is None:
            cash_out_ts = exit_events[-1].ts

    members = {ring_id: [a.account_id for a in accounts.values() if a.ring_id == ring_id and a.archetype == "mule"]}
    roles = {a.account_id: (a.ring_role or "") for a in accounts.values() if a.is_ring}
    lookalikes = [a.account_id for a in accounts.values() if a.is_lookalike]

    events_by_bank: dict[str, list[TransferEvent]] = {b: [] for b in "ABCDE"}
    for e in events:
        for bank in {e.src_bank, e.dst_bank}:
            if bank in events_by_bank:
                # Bank sees event if it touches its accounts
                if (e.src_bank == bank and e.src_account in accounts and accounts[e.src_account].bank_id == bank) or (
                    e.dst_bank == bank and e.dst_account in accounts and accounts[e.dst_account].bank_id == bank
                ):
                    events_by_bank[bank].append(e)

    # Baseline outcomes (no intervention) for stopped_myr — computed by caller via counterfactual
    outcomes = Outcomes(
        cashed_out_myr=round(cashed, 2),
        stuck_myr=round(stuck, 2),
        victim_losses_myr=victim_losses,
        frozen_legit_accounts=frozen_legit,
        false_freezes=len(frozen_legit),
        stopped_myr=0.0,
    )

    gt = GroundTruth(
        ring_ids=[ring_id],
        members=members,
        roles=roles,
        victim_transfers=[
            {"victim": v1.account_id, "amount": v1_amt, "ts": 0, "payee": collector},
            {"victim": v2.account_id, "amount": v2_sent, "ts": v2_ts, "payee": payee2},
        ],
        lookalikes=lookalikes,
        exit_accounts=plan.exits,
        cash_out_complete_ts=cash_out_ts,
    )

    return SimulationResult(
        seed=seed,
        scenario=scenario,
        accounts=accounts,
        events=events,
        events_by_bank=events_by_bank,
        ground_truth=gt,
        outcomes=outcomes,
        live_window_start=live_start,
        live_window_end=live_end,
        meta={
            "synthetic": True,
            "banks_used": plan.banks_used,
            "scammer": asdict(plan.params),
            "n_accounts": len(accounts),
            "collectors": plan.collectors,
            "layers": plan.layers,
            "shared_device": plan.shared_device,
            "world_rng_probe": int(world_rng.integers(0, 1_000_000)),
        },
    )


def counterfactual_stopped(
    seed: int,
    interventions: list[Intervention],
    scenario: str = "hero",
    **kwargs: Any,
) -> tuple[SimulationResult, SimulationResult, float]:
    """Run baseline vs intervention; stopped = baseline.cashed_out - intervention.cashed_out."""
    base = simulate(seed, scenario=scenario, interventions=[], **kwargs)
    treated = simulate(seed, scenario=scenario, interventions=interventions, **kwargs)
    stopped = round(base.outcomes.cashed_out_myr - treated.outcomes.cashed_out_myr, 2)
    treated.outcomes.stopped_myr = max(0.0, stopped)
    treated.outcomes.false_freezes = treated.outcomes.false_freezes
    return base, treated, max(0.0, stopped)
