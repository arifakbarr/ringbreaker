"""Versioned message contracts. extra='forbid' everywhere."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


BankId = Literal["A", "B", "C", "D", "E"]
Channel = Literal[
    "duitnow_transfer",
    "duitnow_qr",
    "interbank_transfer",
    "cash_out_exit",
]
AgeBucket = Literal["under_30", "30_to_180", "over_180"]
PassThroughBucket = Literal["low", "med", "high"]
DwellBucket = Literal["fast", "med", "slow"]


class ReasonCode(str, Enum):
    RING_MEMBER_HIGH = "RING_MEMBER_HIGH"
    FLAGGED_AT_N_BANKS = "FLAGGED_AT_N_BANKS"
    FAST_PASSTHROUGH = "FAST_PASSTHROUGH"
    SHARED_DEVICE_CLUSTER = "SHARED_DEVICE_CLUSTER"
    NEW_ACCOUNT_INFLOW_SPIKE = "NEW_ACCOUNT_INFLOW_SPIKE"


class LinkageV1(StrictModel):
    device: list[str] = Field(default_factory=list, max_length=5)
    ip: list[str] = Field(default_factory=list, max_length=5)
    phone: list[str] = Field(default_factory=list, max_length=5)


class CoarseFeaturesV1(StrictModel):
    pass_through_bucket: PassThroughBucket
    median_dwell_bucket: DwellBucket
    account_age_bucket: AgeBucket


class BeaconV1(StrictModel):
    schema_version: Literal["beacon.v1"] = "beacon.v1"
    bank_id: BankId
    token: str
    score: float = Field(ge=0.0, le=1.0)
    model_version: str
    window_end: str
    linkage: LinkageV1
    coarse: CoarseFeaturesV1
    balance_myr_rounded: int


class EdgeEventV1(StrictModel):
    schema_version: Literal["edge.v1"] = "edge.v1"
    edge_id: str
    src_token: str
    dst_token: str
    src_bank: BankId | Literal["EXT"]
    dst_bank: BankId | Literal["EXT"]
    amount_myr: float
    ts: str
    channel: Channel


class FedUpdateV1(StrictModel):
    schema_version: Literal["fedupdate.v1"] = "fedupdate.v1"
    bank_id: BankId
    round: int
    n_samples: int
    weights: list[float]
    bias: float
    clip_norm: float
    noise_sigma: float = 0.0


class PayeeRiskRequestV1(StrictModel):
    schema_version: Literal["payee.v1"] = "payee.v1"
    payer_bank: BankId
    payee_token: str
    amount_myr: float
    ts: str


class PayeeRiskResponseV1(StrictModel):
    schema_version: Literal["payee.v1"] = "payee.v1"
    tier: Literal[0, 1, 2, 3]
    reason_codes: list[ReasonCode]
    ring_ref: str | None = None
    evaluated_at: str
    latency_ms: float


class NoticeActionV1(StrictModel):
    account_ref: str
    tier: Literal["T2", "T3", "T4"]
    rationale_codes: list[str]


class FreezeNoticeV1(StrictModel):
    schema_version: Literal["notice.v1"] = "notice.v1"
    bank_id: BankId
    case_id: str
    actions: list[NoticeActionV1]
    generated_text: str
    analyst_decision_id: str
