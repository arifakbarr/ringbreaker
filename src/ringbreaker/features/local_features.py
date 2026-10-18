"""Per-account rolling-window features (computed inside each bank)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from ringbreaker.sim.types import Account, TransferEvent

WINDOWS_S = {
    "1h": 3600,
    "6h": 6 * 3600,
    "24h": 24 * 3600,
    "7d": 7 * 24 * 3600,
}

FEATURE_NAMES: list[str] = [
    "in_count_6h",
    "out_count_6h",
    "in_sum_6h",
    "out_sum_6h",
    "distinct_in_6h",
    "distinct_out_6h",
    "passthrough_6h",
    "median_dwell_min",
    "account_age_days",
    "first_time_payer_share",
    "eod_balance_ratio",
    "round_amount_ratio",
    "near_limit_ratio",
    "night_ratio",
    "kyc_tier",
    "local_shared_device",
    "local_shared_ip",
]


@dataclass
class FeatureRow:
    account_id: str
    bank_id: str
    values: np.ndarray
    label: int


def compute_account_features(
    accounts: dict[str, Account],
    events: list[TransferEvent],
    bank_id: str,
    as_of_ts: int,
    device_counts: dict[str, int] | None = None,
    ip_counts: dict[str, int] | None = None,
) -> dict[str, FeatureRow]:
    """Feature matrix for accounts belonging to bank_id at as_of_ts."""
    bank_accts = {aid: a for aid, a in accounts.items() if a.bank_id == bank_id and a.archetype != "exit"}
    if device_counts is None:
        device_counts = defaultdict(int)
        for a in bank_accts.values():
            device_counts[a.device_id] += 1
    if ip_counts is None:
        ip_counts = defaultdict(int)
        for a in bank_accts.values():
            ip_counts[a.ip] += 1

    in_ev: dict[str, list[TransferEvent]] = defaultdict(list)
    out_ev: dict[str, list[TransferEvent]] = defaultdict(list)
    w = WINDOWS_S["6h"]
    for e in events:
        if e.ts > as_of_ts or e.ts < as_of_ts - w:
            continue
        if e.dst_account in bank_accts:
            in_ev[e.dst_account].append(e)
        if e.src_account in bank_accts:
            out_ev[e.src_account].append(e)

    rows: dict[str, FeatureRow] = {}
    for aid, acct in bank_accts.items():
        inns = in_ev.get(aid, [])
        outs = out_ev.get(aid, [])
        in_sum = sum(e.amount_myr for e in inns) or 1e-6
        out_sum = sum(e.amount_myr for e in outs)
        distinct_in = len({e.src_account for e in inns})
        distinct_out = len({e.dst_account for e in outs})
        passthrough = min(1.0, out_sum / in_sum)

        dwells: list[float] = []
        inns_sorted = sorted(inns, key=lambda x: x.ts)
        outs_sorted = sorted(outs, key=lambda x: x.ts)
        oi = 0
        for inn in inns_sorted:
            while oi < len(outs_sorted) and outs_sorted[oi].ts < inn.ts:
                oi += 1
            if oi < len(outs_sorted):
                dwells.append((outs_sorted[oi].ts - inn.ts) / 60.0)
        median_dwell = float(np.median(dwells)) if dwells else 120.0

        first_time = 1.0  # simplified: no long history store yet
        eod_ratio = min(1.0, acct.balance_myr / max(in_sum, 1.0))
        all_amts = [e.amount_myr for e in inns + outs]
        round_ratio = (
            sum(1 for a in all_amts if abs(a - round(a / 100) * 100) < 1e-6) / max(1, len(all_amts))
        )
        near_limit = sum(1 for a in all_amts if 9_000 <= a <= 10_000) / max(1, len(all_amts))
        night = sum(1 for e in inns + outs if (e.ts // 3600) % 24 < 6) / max(1, len(inns) + len(outs))

        vals = np.array(
            [
                float(len(inns)),
                float(len(outs)),
                float(sum(e.amount_myr for e in inns)),
                float(out_sum),
                float(distinct_in),
                float(distinct_out),
                passthrough,
                median_dwell,
                float(acct.age_days),
                first_time,
                eod_ratio,
                round_ratio,
                near_limit,
                night,
                float(acct.kyc_tier),
                float(device_counts.get(acct.device_id, 1)),
                float(ip_counts.get(acct.ip, 1)),
            ],
            dtype=np.float64,
        )
        label = 1 if acct.is_ring and acct.archetype == "mule" else 0
        rows[aid] = FeatureRow(account_id=aid, bank_id=bank_id, values=vals, label=label)
    return rows


def bucket_passthrough(v: float) -> str:
    if v < 0.35:
        return "low"
    if v < 0.75:
        return "med"
    return "high"


def bucket_dwell(minutes: float) -> str:
    if minutes < 30:
        return "fast"
    if minutes < 180:
        return "med"
    return "slow"


def bucket_age(days: int) -> str:
    if days < 30:
        return "under_30"
    if days < 180:
        return "30_to_180"
    return "over_180"
