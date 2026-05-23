"""Deterministic local scheduler for skill manifests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from flow_memory.skills.manifest import SkillManifest
from flow_memory.skills.registry import SkillRegistry


@dataclass
class SkillScheduler:
    """Selects due skills without threads, timers, or wall-clock side effects."""

    registry: SkillRegistry
    last_run_at: dict[str, datetime] = field(default_factory=dict)
    now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc)

    def list_due(self, now: datetime | None = None) -> tuple[SkillManifest, ...]:
        effective_now = _coerce_datetime(now) if now is not None else _coerce_datetime(self.now_fn())
        return tuple(manifest for manifest in self.registry.list() if _is_due(manifest, effective_now, self.last_run_at.get(manifest.skill_id)))

    def due_skills(self, now: datetime | None = None) -> tuple[SkillManifest, ...]:
        return self.list_due(now=now)

    def mark_run(self, skill_id: str, ran_at: datetime | None = None) -> None:
        self.registry.get(skill_id)
        self.last_run_at[skill_id] = _coerce_datetime(ran_at) if ran_at is not None else _coerce_datetime(self.now_fn())


def _is_due(manifest: SkillManifest, now: datetime, last_run_at: datetime | None) -> bool:
    schedule = manifest.schedule
    if schedule.get("enabled", True) is False:
        return False
    if not schedule:
        return False

    run_at = schedule.get("run_at") or schedule.get("start_at")
    if run_at is not None and now < _coerce_datetime(run_at):
        return False

    interval = schedule.get("interval_seconds")
    if interval is None:
        return last_run_at is None
    interval_seconds = float(interval)
    if interval_seconds < 0:
        raise ValueError("interval_seconds must be non-negative")
    if last_run_at is None:
        return True
    return (now - _coerce_datetime(last_run_at)).total_seconds() >= interval_seconds


def _coerce_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    raise TypeError(f"Expected datetime or ISO timestamp, got {type(value).__name__}")
