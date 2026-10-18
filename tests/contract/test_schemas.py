"""Contract: extra=forbid and no raw identifier patterns in bank→hub payloads."""

import re

import pytest
from pydantic import ValidationError

from ringbreaker.privacy.schemas import BeaconV1, CoarseFeaturesV1, EdgeEventV1, LinkageV1

RAW_ID_PATTERNS = [
    re.compile(r"\+60\d{8,}"),  # MY phone
    re.compile(r"\b[A-E]\d{10}\b"),  # synthetic account format
    re.compile(r"\bdev-[a-z0-9-]+\b", re.I),
]


def _scan(obj: dict) -> list[str]:
    blob = str(obj)
    hits = []
    for pat in RAW_ID_PATTERNS:
        if pat.search(blob):
            hits.append(pat.pattern)
    return hits


def test_beacon_forbid_extra():
    with pytest.raises(ValidationError):
        BeaconV1(
            bank_id="A",
            token="ABCDEFGHIJKLMNOPQRSTUV",
            score=0.5,
            model_version="x",
            window_end="2026-01-01T00:00:00Z",
            linkage=LinkageV1(),
            coarse=CoarseFeaturesV1(
                pass_through_bucket="med",
                median_dwell_bucket="fast",
                account_age_bucket="under_30",
            ),
            balance_myr_rounded=100,
            account_number="A8800000001",  # type: ignore[call-arg]
        )


def test_beacon_payload_has_no_raw_ids():
    b = BeaconV1(
        bank_id="A",
        token="ABCDEFGHIJKLMNOPQRSTUV",
        score=0.512,
        model_version="fed-r1",
        window_end="2026-01-01T00:00:00Z",
        linkage=LinkageV1(device=["TOKDEVICE000000000001"], ip=["TOKIP00000000000000001"]),
        coarse=CoarseFeaturesV1(
            pass_through_bucket="high",
            median_dwell_bucket="fast",
            account_age_bucket="under_30",
        ),
        balance_myr_rounded=40000,
    )
    assert _scan(b.model_dump()) == []


def test_edge_forbid_extra():
    with pytest.raises(ValidationError):
        EdgeEventV1(
            edge_id="E1",
            src_token="A",
            dst_token="B",
            src_bank="A",
            dst_bank="B",
            amount_myr=10,
            ts="0",
            channel="duitnow_transfer",
            raw_name="Alice",  # type: ignore[call-arg]
        )
