"""Analyst feedback loop — suppress / demote aliases after LOOKS_LEGIT rejects."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class FeedbackStore:
    path: Path
    suppressed_aliases: set[str] = field(default_factory=set)
    events: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                ev = json.loads(line)
                self.events.append(ev)
                if ev.get("action") == "suppress":
                    self.suppressed_aliases.add(ev["alias"])

    def record(
        self,
        *,
        case_id: str,
        alias: str,
        action: str,
        reason: str = "",
        note: str = "",
    ) -> dict[str, Any]:
        ev = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "case_id": case_id,
            "alias": alias,
            "action": action,
            "reason": reason,
            "note": note,
            "synthetic": True,
        }
        self.events.append(ev)
        if action == "suppress":
            self.suppressed_aliases.add(alias)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=True) + "\n")
        return ev

    def apply_to_plan(self, freeze_priority: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Demote suppressed aliases: drop T4 → T2 recommendation-only."""
        out = []
        for item in freeze_priority:
            row = dict(item)
            if row.get("alias") in self.suppressed_aliases:
                row["tier"] = "T2"
                row["false_freeze_risk"] = min(1.0, float(row.get("false_freeze_risk", 0.2)) + 0.35)
                row["rationale"] = (row.get("rationale") or "") + " [feedback:LOOKS_LEGIT]"
                row["feedback_demoted"] = True
            out.append(row)
        # Re-rank
        out.sort(key=lambda r: (0 if r.get("feedback_demoted") else 1, r.get("rank", 99)))
        for i, r in enumerate(out, 1):
            r["rank"] = i
        return out

    def summary(self) -> dict[str, Any]:
        return {
            "synthetic": True,
            "n_events": len(self.events),
            "suppressed_aliases": sorted(self.suppressed_aliases),
            "events": self.events[-20:],
        }
