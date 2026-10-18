"""Victim warning rubric — EN/MS, ≤60 words, no forbidden terms."""

from __future__ import annotations

import pytest

from ringbreaker.llm.warnings import FORBIDDEN, victim_warning


@pytest.mark.parametrize("lang", ["en", "ms"])
@pytest.mark.parametrize("tier", [1, 2, 3])
def test_victim_warning_limits(lang: str, tier: int) -> None:
    w = victim_warning(tier, lang=lang)  # type: ignore[arg-type]
    assert w["synthetic"] is True
    assert w["tier"] == tier
    assert w["lang"] == lang
    words = w["text"].split()
    assert 1 <= len(words) <= 60
    low = w["text"].lower()
    for f in FORBIDDEN:
        assert f not in low
