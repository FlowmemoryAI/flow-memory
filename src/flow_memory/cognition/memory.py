"""Experience-memory retrieval helpers for cognition."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

from flow_memory.cognition.experience import get_experience, list_experiences, query_experiences, retrieve_similar_experiences, write_experience


def memory_summary(root: str | Path = ".") -> Mapping[str, object]:
    records = list_experiences(root)
    high_error = sum(1 for record in records if float(dict(record.get("prediction_error", {})).get("prediction_error", 0.0) or 0.0) > 0.5)
    return {"ok": True, "experience_count": len(records), "high_error_count": high_error, "local_only": True}


__all__ = ["get_experience", "list_experiences", "memory_summary", "query_experiences", "retrieve_similar_experiences", "write_experience"]
