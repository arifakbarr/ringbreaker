"""Victim warnings — EN / MS templates; calm, non-blaming, ≤60 words."""

from __future__ import annotations

from typing import Literal

Lang = Literal["en", "ms"]


TEMPLATES: dict[tuple[int, Lang], str] = {
    (
        3,
        "en",
    ): (
        "Please pause this payment. Our fraud check flagged elevated risk for this payee "
        "in a synthetic simulation. Contact your bank using its official number before "
        "continuing. Do not move money to another 'safe' account."
    ),
    (
        3,
        "ms",
    ): (
        "Sila hentikan seketika pembayaran ini. Semakan fraud (simulasi) menandakan risiko "
        "tinggi bagi penerima ini. Hubungi bank anda hanya melalui nombor rasmi sebelum "
        "teruskan. Jangan pindah wang ke akaun yang dikatakan 'lebih selamat'."
    ),
    (
        2,
        "en",
    ): (
        "A quick check: this payee shows unusual patterns in our simulation. "
        "Confirm the payee through your bank's official channel before sending."
    ),
    (
        2,
        "ms",
    ): (
        "Semakan pantas: penerima ini menunjukkan corak luar biasa dalam simulasi kami. "
        "Sahkan penerima melalui saluran rasmi bank anda sebelum menghantar wang."
    ),
    (
        1,
        "en",
    ): (
        "Optional tip: take a moment to confirm this payee via your bank app or hotline "
        "before you send. This is a synthetic simulation notice."
    ),
    (
        1,
        "ms",
    ): (
        "Cadangan: luangkan masa sahkan penerima melalui aplikasi atau talian rasmi bank "
        "sebelum menghantar. Ini notis simulasi sintetik."
    ),
}


FORBIDDEN = ("scammer", "criminal", "guaranteed", "other bank", "account number")


def victim_warning(tier: int, lang: Lang = "en", amount_band: str = "medium") -> dict:
    text = TEMPLATES.get((tier, lang)) or TEMPLATES[(2, lang)]
    words = text.split()
    if len(words) > 60:
        text = " ".join(words[:60])
    low = text.lower()
    for f in FORBIDDEN:
        if f in low:
            raise ValueError(f"forbidden content: {f}")
    return {
        "tier": tier,
        "lang": lang,
        "amount_band": amount_band,
        "text": text,
        "mode": "template",
        "synthetic": True,
    }
