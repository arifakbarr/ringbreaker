"""Scammer parameter templates and ring structure generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from ringbreaker.sim.types import Account, BankId


EvasionLevel = Literal["E0", "E1", "E2", "E3", "E4"]


@dataclass
class ScammerParams:
    n_layers: int = 3
    fanout_per_layer: list[int] = field(default_factory=lambda: [3, 3, 2])
    dwell_minutes_per_layer: list[float] = field(default_factory=lambda: [8.0, 10.0, 12.0])
    banks_span: int = 3
    device_reuse_prob: float = 0.55
    ip_reuse_prob: float = 0.35
    phone_reuse_prob: float = 0.25
    structuring_limit_myr: float = 25_000.0
    decoy_payments: int = 2
    exit_type: str = "cash_agent"
    adaptive: bool = False
    template: str = "R1"
    evasion: EvasionLevel = "E0"

    def apply_evasion(self) -> ScammerParams:
        p = ScammerParams(**{**self.__dict__})
        if self.evasion == "E1":
            p.dwell_minutes_per_layer = [d * 1.8 for d in self.dwell_minutes_per_layer]
        elif self.evasion == "E2":
            p.structuring_limit_myr = min(self.structuring_limit_myr, 9_900.0)
        elif self.evasion == "E3":
            p.device_reuse_prob = 0.15
            p.ip_reuse_prob = 0.08
            p.phone_reuse_prob = 0.08
        elif self.evasion == "E4":
            p.n_layers = 4
            p.fanout_per_layer = [3, 3, 3, 2]
            p.dwell_minutes_per_layer = [10.0, 12.0, 14.0, 10.0]
            p.banks_span = min(3, self.banks_span) if self.banks_span <= 3 else 4
            # Keep ABC-only rings when prefer_banks limits participation demos
            if self.banks_span <= 3:
                p.n_layers = 4
                p.fanout_per_layer = [3, 3, 2, 2]
                p.banks_span = 3
            p.decoy_payments = 6
            p.device_reuse_prob = 0.2
            p.structuring_limit_myr = 9_900.0
        if self.adaptive:
            # After analyst pressure, lengthen remaining dwell (E4 adaptive stub)
            p.dwell_minutes_per_layer = [d * 1.35 for d in p.dwell_minutes_per_layer]
            p.decoy_payments = max(p.decoy_payments, 4)
        return p


def hero_scammer_params() -> ScammerParams:
    """Hero defaults: 3 layers, 9 mules across A/B/C, out by ~T+38m."""
    return ScammerParams(
        n_layers=3,
        fanout_per_layer=[3, 3, 2],
        dwell_minutes_per_layer=[8.0, 12.0, 14.0],
        banks_span=3,
        device_reuse_prob=0.6,
        ip_reuse_prob=0.3,
        phone_reuse_prob=0.25,
        structuring_limit_myr=25_000.0,
        decoy_payments=2,
        template="R1",
        evasion="E0",
        adaptive=False,
    )


@dataclass
class RingPlan:
    ring_id: str
    params: ScammerParams
    collectors: list[str]
    layers: list[list[str]]
    exits: list[str]
    shared_device: str | None
    shared_phone: str | None
    banks_used: list[BankId]


def pick_banks(rng: np.random.Generator, n: int, prefer: list[BankId] | None = None) -> list[BankId]:
    pool: list[BankId] = list(prefer) if prefer else ["A", "B", "C", "D", "E"]
    if prefer is None:
        order = list(rng.permutation(pool))
        return order[:n]
    # Prefer A,B,C for hero participation story
    base: list[BankId] = ["A", "B", "C"]
    extra: list[BankId] = ["D", "E"]
    if n <= 3:
        return base[:n]
    return base + list(rng.choice(extra, size=n - 3, replace=False))


def allocate_ring_accounts(
    rng: np.random.Generator,
    accounts: dict[str, Account],
    params: ScammerParams,
    ring_id: str,
    prefer_banks: list[BankId] | None = None,
) -> RingPlan:
    """Mark existing accounts as ring members and return structure."""
    params = params.apply_evasion()
    banks = pick_banks(rng, params.banks_span, prefer_banks)
    candidates = [
        a
        for a in accounts.values()
        if a.bank_id in banks and not a.is_ring and a.archetype not in ("exit",)
        and not a.is_lookalike
        and a.age_days < 180
    ]
    rng.shuffle(candidates)

    layers: list[list[str]] = []
    used: list[Account] = []
    for layer_i, fanout in enumerate(params.fanout_per_layer[: params.n_layers]):
        layer_accts: list[Account] = []
        # Spread across banks
        for j in range(fanout):
            bank = banks[j % len(banks)]
            pool = [a for a in candidates if a.bank_id == bank and a not in used]
            if not pool:
                pool = [a for a in candidates if a not in used]
            if not pool:
                break
            acct = pool[0]
            candidates.remove(acct)
            used.append(acct)
            acct.is_ring = True
            acct.ring_id = ring_id
            acct.layer = layer_i
            acct.ring_role = "collector" if layer_i == 0 else f"layer_{layer_i}"
            acct.archetype = "mule"
            layer_accts.append(acct)
        layers.append([a.account_id for a in layer_accts])

    # External exits (synthetic EXT bank accounts living in meta)
    exits: list[str] = []
    for i in range(2):
        eid = f"EXT-EXIT-{ring_id}-{i}"
        exits.append(eid)
        accounts[eid] = Account(
            account_id=eid,
            bank_id="A",  # placeholder; transfers use EXT
            archetype="exit",
            age_days=30,
            kyc_tier=0,
            phone=f"+6017{rng.integers(1000000, 9999999)}",
            device_id=f"dev-exit-{ring_id}-{i}",
            ip=f"203.0.113.{rng.integers(10, 200)}",
            is_ring=True,
            ring_id=ring_id,
            ring_role="exit",
            layer=params.n_layers,
            balance_myr=0.0,
        )

    shared_device = None
    shared_phone = None
    if rng.random() < params.device_reuse_prob and used:
        shared_device = f"dev-shared-{ring_id}"
        for a in used[: max(2, len(used) // 2)]:
            a.device_id = shared_device
    if rng.random() < params.phone_reuse_prob and used:
        shared_phone = f"+6012{rng.integers(1000000, 9999999)}"
        for a in used[: max(2, len(used) // 3)]:
            a.phone = shared_phone

    collectors = layers[0] if layers else []
    return RingPlan(
        ring_id=ring_id,
        params=params,
        collectors=collectors,
        layers=layers,
        exits=exits,
        shared_device=shared_device,
        shared_phone=shared_phone,
        banks_used=banks,
    )
