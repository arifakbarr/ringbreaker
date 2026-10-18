"""Per-ring aliases — Gemini never sees raw tokens or bank account IDs."""

from __future__ import annotations


class AliasMap:
    def __init__(self, ring_id: str) -> None:
        self.ring_id = ring_id
        self._tok_to_alias: dict[str, str] = {}
        self._alias_to_tok: dict[str, str] = {}
        self._n = 0

    def alias_for(self, token: str) -> str:
        if token not in self._tok_to_alias:
            self._n += 1
            a = f"ACC-{self._n:02d}"
            self._tok_to_alias[token] = a
            self._alias_to_tok[a] = token
        return self._tok_to_alias[token]

    def token_for(self, alias: str) -> str | None:
        return self._alias_to_tok.get(alias)

    def bank_label(self, bank_id: str) -> str:
        return f"Bank {bank_id}" if bank_id and bank_id != "EXT" else "External"

    def snapshot(self) -> dict[str, str]:
        return dict(self._tok_to_alias)


ALLOWLIST_TOOL_FIELDS = frozenset(
    {
        "ring_id",
        "ring_score",
        "components",
        "banks",
        "member_count",
        "first_detection_s",
        "nodes",
        "edges",
        "links",
        "alias",
        "bank",
        "score",
        "coarse",
        "balance_myr_rounded",
        "amount_myr",
        "ts",
        "channel",
        "from_alias",
        "to_alias",
        "evidence_id",
        "plan",
        "signal",
        "score_without",
        "delta",
        "lookalike",
        "account_age_bucket",
        "counterparty_diversity",
    }
)


def redact(obj: dict, allow: frozenset[str] = ALLOWLIST_TOOL_FIELDS) -> dict:
    return {k: v for k, v in obj.items() if k in allow}
