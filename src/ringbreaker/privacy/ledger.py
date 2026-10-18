"""Append-only privacy ledger counters per bank."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PrivacyLedger:
    bank_id: str
    messages_by_type: dict[str, int] = field(default_factory=dict)
    bytes_by_type: dict[str, int] = field(default_factory=dict)
    tokens_sent: int = 0
    raw_fields_sent: int = 0

    def record(self, msg_type: str, payload_bytes: int, n_tokens: int = 1) -> None:
        self.messages_by_type[msg_type] = self.messages_by_type.get(msg_type, 0) + 1
        self.bytes_by_type[msg_type] = self.bytes_by_type.get(msg_type, 0) + payload_bytes
        self.tokens_sent += n_tokens

    def snapshot(self) -> dict[str, Any]:
        return {
            "bank_id": self.bank_id,
            "messages_by_type": dict(self.messages_by_type),
            "bytes_by_type": dict(self.bytes_by_type),
            "tokens_sent": self.tokens_sent,
            "raw_fields_sent": self.raw_fields_sent,
            "synthetic": True,
        }
