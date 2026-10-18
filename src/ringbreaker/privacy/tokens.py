"""Type-scoped HMAC tokenisation. Hub never holds the key."""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import re
from typing import Literal

TokenType = Literal["account", "device", "ip", "phone"]

_SEP = b"\x1f"


def normalise(value: str, token_type: TokenType) -> str:
    v = value.strip()
    if token_type == "phone":
        digits = re.sub(r"\D", "", v)
        if digits.startswith("0"):
            digits = "60" + digits[1:]
        if not digits.startswith("60"):
            digits = "60" + digits
        return "+" + digits
    if token_type == "device":
        return v.lower()
    if token_type == "ip":
        try:
            return str(ipaddress.ip_address(v))
        except ValueError:
            return v
    return v


class Tokeniser:
    """HMAC-SHA256 → base32 truncated. Bank-side only."""

    def __init__(self, key: str, epoch: str = "e1") -> None:
        self._key = key.encode("utf-8")
        self._epoch = epoch.encode("utf-8")

    def token(self, value: str, token_type: TokenType) -> str:
        norm = normalise(value, token_type)
        msg = self._epoch + _SEP + token_type.encode("utf-8") + _SEP + norm.encode("utf-8")
        digest = hmac.new(self._key, msg, hashlib.sha256).digest()
        b32 = base64.b32encode(digest).decode("ascii").rstrip("=")
        return b32[:22]

    def account_token(self, account_id: str) -> str:
        return self.token(account_id, "account")

    def device_token(self, device_id: str) -> str:
        return self.token(device_id, "device")

    def ip_token(self, ip: str) -> str:
        return self.token(ip, "ip")

    def phone_token(self, phone: str) -> str:
        return self.token(phone, "phone")
