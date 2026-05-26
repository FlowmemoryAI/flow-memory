"""Memory Seed records for Agent Genesis."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from flow_memory.cognition.state import stable_id, utc_now

DEFAULT_MEMORY_SEED_DIR = Path("artifacts/genesis/memory_seeds")


@dataclass(frozen=True)
class MemorySeed:
    seed_id: str
    agent_id: str
    user_preferences: tuple[str, ...]
    project_context: tuple[str, ...]
    behavior_rules: tuple[str, ...]
    initial_lessons: tuple[str, ...]
    privacy_mode: str = "private_only"
    raw_private_content: str = ""
    sanitized_summary: str = ""
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "seed_id": self.seed_id,
            "agent_id": self.agent_id,
            "user_preferences": self.user_preferences,
            "project_context": self.project_context,
            "behavior_rules": self.behavior_rules,
            "initial_lessons": self.initial_lessons,
            "privacy_mode": self.privacy_mode,
            "raw_private_content": self.raw_private_content,
            "sanitized_summary": self.sanitized_summary,
            "raw_private_content_shared": False,
            "created_at": self.created_at,
        }


def create_memory_seed(
    *,
    agent_id: str,
    user_preferences: tuple[str, ...] = (),
    project_context: tuple[str, ...] = (),
    behavior_rules: tuple[str, ...] = (),
    initial_lessons: tuple[str, ...] = (),
    privacy_mode: str = "private_only",
    raw_private_content: str = "",
) -> MemorySeed:
    sanitized = _sanitize_summary(user_preferences, project_context, behavior_rules, initial_lessons)
    seed_id = stable_id("memory_seed", agent_id, "|".join(user_preferences), "|".join(project_context), "|".join(behavior_rules), privacy_mode)
    return MemorySeed(
        seed_id=seed_id,
        agent_id=agent_id,
        user_preferences=user_preferences,
        project_context=project_context,
        behavior_rules=behavior_rules,
        initial_lessons=initial_lessons,
        privacy_mode=privacy_mode,
        raw_private_content=raw_private_content,
        sanitized_summary=sanitized,
    )


def write_memory_seed(seed: MemorySeed | Mapping[str, Any], root: str | Path = ".", directory: str | Path = DEFAULT_MEMORY_SEED_DIR) -> Mapping[str, Any]:
    payload = seed.as_record() if isinstance(seed, MemorySeed) else dict(seed)
    path = _path(root, directory, str(payload["agent_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "agent_id": payload["agent_id"], "seed_id": payload["seed_id"], "path": _rel(Path(root).resolve(), path), "record": payload}


def get_memory_seed(agent_id: str, root: str | Path = ".", directory: str | Path = DEFAULT_MEMORY_SEED_DIR) -> Mapping[str, Any]:
    path = _path(root, directory, agent_id)
    if not path.exists():
        raise KeyError(f"unknown memory seed: {agent_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _sanitize_summary(*groups: tuple[str, ...]) -> str:
    values: list[str] = []
    for group in groups:
        values.extend(item.strip() for item in group if item.strip())
    return "; ".join(values[:8])


def _path(root: str | Path, directory: str | Path, agent_id: str) -> Path:
    safe = "".join(ch for ch in agent_id if ch.isalnum() or ch in {"-", "_", "."}).strip(".")
    if not safe:
        raise ValueError("agent_id is required")
    return Path(root).resolve() / directory / f"{safe}.json"


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
