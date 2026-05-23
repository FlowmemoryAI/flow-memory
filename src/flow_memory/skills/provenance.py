"""Skill provenance records."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from flow_memory.core.types import new_id, utc_now


@dataclass(frozen=True)
class SkillProvenanceRecord:
    skill_id: str
    source: str
    version: str = "local"
    author: str = "flow-memory"
    record_id: str = field(default_factory=lambda: new_id("skill_provenance"))
    created_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def as_record(self) -> Mapping[str, object]:
        return {
            "record_id": self.record_id,
            "skill_id": self.skill_id,
            "source": self.source,
            "version": self.version,
            "author": self.author,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }
