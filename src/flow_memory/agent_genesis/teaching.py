"""Human teaching events for Agent Genesis."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from flow_memory.cognition.consolidation import write_lesson
from flow_memory.cognition.state import stable_id, utc_now

DEFAULT_TEACHING_DIR = Path("artifacts/genesis/teaching")


@dataclass(frozen=True)
class TeachingEvent:
    teaching_event_id: str
    user_id: str
    agent_id: str
    correction_type: str
    content: str
    lesson: str
    applies_to_tags: tuple[str, ...]
    privacy_mode: str = "private_only"
    contribution_allowed: bool = False
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "teaching_event_id": self.teaching_event_id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "correction_type": self.correction_type,
            "content": self.content,
            "lesson": self.lesson,
            "applies_to_tags": self.applies_to_tags,
            "privacy_mode": self.privacy_mode,
            "contribution_allowed": self.contribution_allowed,
            "created_at": self.created_at,
        }


def create_teaching_event(*, user_id: str, agent_id: str, correction_type: str, content: str = "", lesson: str, applies_to_tags: tuple[str, ...] = (), privacy_mode: str = "private_only", contribution_allowed: bool = False) -> TeachingEvent:
    event_id = stable_id("teaching_event", user_id, agent_id, correction_type, lesson, "|".join(applies_to_tags))
    return TeachingEvent(event_id, user_id, agent_id, correction_type, content, lesson, applies_to_tags, privacy_mode, contribution_allowed)


def write_teaching_event(event: TeachingEvent | Mapping[str, Any], root: str | Path = ".", directory: str | Path = DEFAULT_TEACHING_DIR) -> Mapping[str, Any]:
    payload = event.as_record() if isinstance(event, TeachingEvent) else dict(event)
    path = _path(root, directory, str(payload["teaching_event_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lesson_record = {
        "lesson_id": stable_id("teaching_lesson", payload["agent_id"], payload["lesson"]),
        "title": f"Teaching lesson for {payload['correction_type']}",
        "summary": payload["lesson"],
        "domain": _domain(payload.get("applies_to_tags", ())),
        "tags": tuple(payload.get("applies_to_tags", ())) + ("human-teaching",),
        "source_experience_ids": (payload["teaching_event_id"],),
        "repeated_error_type": "human_teaching_event",
        "recommended_future_action": payload["lesson"],
        "confidence_delta": 0.0,
        "risk_delta": 0.0,
        "usefulness_score": 0.72,
        "created_at": payload.get("created_at", utc_now()),
    }
    lesson_write = write_lesson(lesson_record, root=root)
    return {"ok": True, "teaching_event_id": payload["teaching_event_id"], "path": _rel(Path(root).resolve(), path), "record": payload, "private_lesson": lesson_write["record"]}


def list_teaching_events(agent_id: str = "", root: str | Path = ".", directory: str | Path = DEFAULT_TEACHING_DIR) -> tuple[Mapping[str, Any], ...]:
    base = Path(root).resolve() / directory
    if not base.exists():
        return ()
    records = tuple(json.loads(path.read_text(encoding="utf-8")) for path in sorted(base.glob("*.json")))
    if agent_id:
        records = tuple(record for record in records if record.get("agent_id") == agent_id)
    return records


def _domain(tags: Any) -> str:
    lowered = {str(tag).lower() for tag in tags}
    for domain in ("dashboard", "release", "policy", "compute", "git", "memory"):
        if domain in lowered:
            return domain
    return "teaching"


def _path(root: str | Path, directory: str | Path, event_id: str) -> Path:
    safe = "".join(ch for ch in event_id if ch.isalnum() or ch in {"-", "_", "."}).strip(".")
    if not safe:
        raise ValueError("teaching_event_id is required")
    return Path(root).resolve() / directory / f"{safe}.json"


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
