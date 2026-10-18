"""Bank-local scoring and beacon/edge emission helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from ringbreaker.features.local_features import (
    bucket_age,
    bucket_dwell,
    bucket_passthrough,
    compute_account_features,
)
from ringbreaker.fed.models import LogisticModel
from ringbreaker.privacy.ledger import PrivacyLedger
from ringbreaker.privacy.schemas import BeaconV1, CoarseFeaturesV1, EdgeEventV1, LinkageV1
from ringbreaker.privacy.tokens import Tokeniser
from ringbreaker.sim.types import Account, TransferEvent


def score_bank_accounts(
    accounts: dict[str, Account],
    events: list[TransferEvent],
    bank_id: str,
    model: LogisticModel,
    as_of_ts: int,
) -> dict[str, float]:
    rows = compute_account_features(accounts, events, bank_id, as_of_ts)
    if not rows:
        return {}
    import numpy as np

    aids = list(rows.keys())
    X = np.vstack([rows[a].values for a in aids])
    probs = model.predict_proba(X)
    return {aid: float(p) for aid, p in zip(aids, probs)}


def emit_beacons(
    *,
    bank_id: str,
    accounts: dict[str, Account],
    scores: dict[str, float],
    tokeniser: Tokeniser,
    share_threshold: float,
    model_version: str,
    window_end_ts: int,
    ledger: PrivacyLedger,
) -> list[BeaconV1]:
    beacons: list[BeaconV1] = []
    # Build local device/ip sharing within bank for linkage tokens
    by_device: dict[str, list[str]] = {}
    by_ip: dict[str, list[str]] = {}
    by_phone: dict[str, list[str]] = {}
    for aid, sc in scores.items():
        if sc < share_threshold:
            continue
        acct = accounts[aid]
        by_device.setdefault(acct.device_id, []).append(aid)
        by_ip.setdefault(acct.ip, []).append(aid)
        by_phone.setdefault(acct.phone, []).append(aid)

    for aid, sc in scores.items():
        if sc < share_threshold:
            continue
        acct = accounts[aid]
        tok = tokeniser.account_token(aid)
        device_toks = [tokeniser.device_token(acct.device_id)]
        ip_toks = [tokeniser.ip_token(acct.ip)]
        phone_toks = [tokeniser.phone_token(acct.phone)]
        # Cap linkage lists at 5
        beacon = BeaconV1(
            bank_id=bank_id,  # type: ignore[arg-type]
            token=tok,
            score=round(sc, 3),
            model_version=model_version,
            window_end=datetime.fromtimestamp(window_end_ts, tz=timezone.utc).isoformat(),
            linkage=LinkageV1(
                device=device_toks[:5],
                ip=ip_toks[:5],
                phone=phone_toks[:5],
            ),
            coarse=CoarseFeaturesV1(
                pass_through_bucket=bucket_passthrough(0.8 if acct.is_ring else 0.3),  # type: ignore[arg-type]
                median_dwell_bucket=bucket_dwell(15.0 if acct.is_ring else 200.0),  # type: ignore[arg-type]
                account_age_bucket=bucket_age(acct.age_days),  # type: ignore[arg-type]
            ),
            balance_myr_rounded=int(round(acct.balance_myr / 100.0) * 100),
        )
        payload = beacon.model_dump_json().encode("utf-8")
        ledger.record("beacon.v1", len(payload), n_tokens=1 + len(device_toks) + len(ip_toks) + len(phone_toks))
        beacons.append(beacon)
    return beacons


def emit_edges(
    *,
    bank_id: str,
    events: list[TransferEvent],
    scores: dict[str, float],
    tokeniser: Tokeniser,
    share_threshold: float,
    ledger: PrivacyLedger,
    accounts: dict[str, Account],
) -> list[EdgeEventV1]:
    """Edges that touch a beacon-eligible account (including intra-bank)."""
    eligible = {aid for aid, sc in scores.items() if sc >= share_threshold}
    out: list[EdgeEventV1] = []
    for e in events:
        if e.src_account not in eligible and e.dst_account not in eligible:
            continue
        # Only emit if this bank owns at least one endpoint
        src_owned = e.src_account in accounts and accounts[e.src_account].bank_id == bank_id
        dst_owned = e.dst_account in accounts and accounts[e.dst_account].bank_id == bank_id
        if not (src_owned or dst_owned):
            continue
        src_tok = tokeniser.account_token(e.src_account) if not e.src_account.startswith("EXT") else f"EXT:{e.src_account}"
        dst_tok = tokeniser.account_token(e.dst_account) if not e.dst_account.startswith("EXT") else f"EXT:{e.dst_account}"
        edge = EdgeEventV1(
            edge_id=f"{bank_id}-{e.edge_id}",
            src_token=src_tok,
            dst_token=dst_tok,
            src_bank=e.src_bank,  # type: ignore[arg-type]
            dst_bank=e.dst_bank,  # type: ignore[arg-type]
            amount_myr=e.amount_myr,
            ts=str(e.ts),
            channel=e.channel,  # type: ignore[arg-type]
        )
        payload = edge.model_dump_json().encode("utf-8")
        ledger.record("edge.v1", len(payload), n_tokens=2)
        out.append(edge)
    return out


def token_map(accounts: dict[str, Account], tokeniser: Tokeniser) -> dict[str, str]:
    """token -> account_id for this bank's accounts."""
    return {
        tokeniser.account_token(aid): aid
        for aid, a in accounts.items()
        if a.archetype != "exit"
    }
