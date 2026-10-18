"""Shared simulation datatypes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


BankId = Literal["A", "B", "C", "D", "E"]
Channel = Literal[
    "duitnow_transfer",
    "duitnow_qr",
    "interbank_transfer",
    "cash_out_exit",
]
Archetype = Literal[
    "salaried",
    "student_p2p",
    "qr_merchant",
    "sme_payroll",
    "landlord",
    "gig_worker",
    "remittance_agent",
    "small_seller",
    "student_treasurer",
    "mule",
    "exit",
]


class FreezeKind(str, Enum):
    HOLD = "hold"
    FULL_FREEZE = "full_freeze"


@dataclass(frozen=True)
class Freeze:
    account_id: str
    at_ts: int
    kind: FreezeKind = FreezeKind.FULL_FREEZE


@dataclass(frozen=True)
class PayeeBlock:
    account_id: str
    from_ts: int
    compliance_rate: float = 0.70


Intervention = Freeze | PayeeBlock


@dataclass
class Account:
    account_id: str
    bank_id: BankId
    archetype: Archetype
    age_days: int
    kyc_tier: int
    phone: str
    device_id: str
    ip: str
    is_lookalike: bool = False
    is_ring: bool = False
    ring_role: str | None = None
    ring_id: str | None = None
    layer: int | None = None
    balance_myr: float = 500.0


@dataclass
class TransferEvent:
    edge_id: str
    src_account: str
    dst_account: str
    src_bank: BankId | Literal["EXT"]
    dst_bank: BankId | Literal["EXT"]
    amount_myr: float
    ts: int
    channel: Channel
    is_ring: bool = False
    victim_id: str | None = None


@dataclass
class GroundTruth:
    ring_ids: list[str]
    members: dict[str, list[str]]  # ring_id -> account_ids
    roles: dict[str, str]  # account_id -> role
    victim_transfers: list[dict[str, Any]]
    lookalikes: list[str]
    exit_accounts: list[str]
    cash_out_complete_ts: int | None = None


@dataclass
class Outcomes:
    cashed_out_myr: float = 0.0
    stuck_myr: float = 0.0
    victim_losses_myr: dict[str, float] = field(default_factory=dict)
    frozen_legit_accounts: list[str] = field(default_factory=list)
    stopped_myr: float = 0.0
    false_freezes: int = 0


@dataclass
class SimulationResult:
    seed: int
    scenario: str
    accounts: dict[str, Account]
    events: list[TransferEvent]
    events_by_bank: dict[str, list[TransferEvent]]
    ground_truth: GroundTruth
    outcomes: Outcomes
    live_window_start: int
    live_window_end: int
    meta: dict[str, Any] = field(default_factory=dict)
