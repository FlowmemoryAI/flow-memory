"""Deterministic memory consolidation for predictive cognition."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from flow_memory.cognition.experience import list_experiences
from flow_memory.cognition.state import stable_id, utc_now

DEFAULT_LESSON_DIR = Path("artifacts/cognition/lessons")


@dataclass(frozen=True)
class ConsolidatedLesson:
    lesson_id: str
    title: str
    summary: str
    domain: str
    tags: tuple[str, ...]
    source_experience_ids: tuple[str, ...]
    repeated_error_type: str
    recommended_future_action: str
    confidence_delta: float
    risk_delta: float
    usefulness_score: float
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "lesson_id": self.lesson_id,
            "title": self.title,
            "summary": self.summary,
            "domain": self.domain,
            "tags": self.tags,
            "source_experience_ids": self.source_experience_ids,
            "repeated_error_type": self.repeated_error_type,
            "recommended_future_action": self.recommended_future_action,
            "confidence_delta": self.confidence_delta,
            "risk_delta": self.risk_delta,
            "usefulness_score": self.usefulness_score,
            "created_at": self.created_at,
        }


def consolidate_experiences(
    root: str | Path = ".",
    *,
    min_repetitions: int = 1,
    directory: str | Path = DEFAULT_LESSON_DIR,
) -> Mapping[str, Any]:
    """Group local experiences into reusable deterministic lesson records."""

    records = tuple(list_experiences(root))
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for record in records:
        error = dict(record.get("prediction_error", {})) if isinstance(record.get("prediction_error", {}), Mapping) else {}
        domain = _domain_from_record(record)
        error_type = str(error.get("error_type", "observed"))
        groups.setdefault((domain, error_type), []).append(record)

    written: list[Mapping[str, Any]] = []
    for (domain, error_type), group in sorted(groups.items()):
        if len(group) < max(1, min_repetitions):
            continue
        lesson = build_consolidated_lesson(domain, error_type, tuple(group))
        written.append(write_lesson(lesson, root=root, directory=directory))

    return {
        "ok": True,
        "experience_count": len(records),
        "consolidated_lesson_count": len(written),
        "lessons": tuple(item["record"] for item in written),
        "lesson_paths": tuple(item["path"] for item in written),
        "local_only": True,
    }


def build_consolidated_lesson(domain: str, error_type: str, records: tuple[Mapping[str, Any], ...]) -> ConsolidatedLesson:
    source_ids = tuple(str(record.get("experience_id", "")) for record in records if record.get("experience_id"))
    tags = _merge_tags(domain, records)
    confidence_delta = _mean(float(record.get("confidence_after", 0.0) or 0.0) - float(record.get("confidence_before", 0.0) or 0.0) for record in records)
    risk_delta = _mean(float(record.get("risk_after", 0.0) or 0.0) - float(record.get("risk_before", 0.0) or 0.0) for record in records)
    error_mean = _mean(float(dict(record.get("prediction_error", {})).get("prediction_error", 0.0) or 0.0) for record in records)
    recommended = _recommended_action(domain, error_type, records)
    title = _title(domain, error_type)
    summary = _summary(domain, error_type, records, recommended)
    usefulness = max(0.0, min(1.0, 0.48 + min(len(source_ids), 5) * 0.08 + error_mean * 0.24 - max(0.0, risk_delta) * 0.12))
    lesson_id = stable_id("consolidated_lesson", domain, error_type, "|".join(source_ids), recommended)
    return ConsolidatedLesson(
        lesson_id=lesson_id,
        title=title,
        summary=summary,
        domain=domain,
        tags=tags,
        source_experience_ids=source_ids,
        repeated_error_type=error_type,
        recommended_future_action=recommended,
        confidence_delta=round(confidence_delta, 6),
        risk_delta=round(risk_delta, 6),
        usefulness_score=round(usefulness, 6),
    )


def write_lesson(
    record: ConsolidatedLesson | Mapping[str, Any],
    *,
    root: str | Path = ".",
    directory: str | Path = DEFAULT_LESSON_DIR,
) -> Mapping[str, Any]:
    payload = record.as_record() if isinstance(record, ConsolidatedLesson) else dict(record)
    path = _lesson_path(root, directory, str(payload["lesson_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "lesson_id": payload["lesson_id"], "path": _rel(Path(root).resolve(), path), "record": payload}


def list_lessons(root: str | Path = ".", directory: str | Path = DEFAULT_LESSON_DIR) -> tuple[Mapping[str, Any], ...]:
    base = Path(root).resolve() / directory
    if not base.exists():
        return ()
    return tuple(_read_record(path) for path in sorted(base.glob("*.json")))


def get_lesson(lesson_id: str, root: str | Path = ".", directory: str | Path = DEFAULT_LESSON_DIR) -> Mapping[str, Any]:
    path = _lesson_path(root, directory, lesson_id)
    if not path.exists():
        raise KeyError(f"unknown lesson: {lesson_id}")
    return _read_record(path)


def query_lessons(
    query: str = "",
    *,
    domain: str = "",
    tags: tuple[str, ...] = (),
    root: str | Path = ".",
    limit: int = 10,
) -> tuple[Mapping[str, Any], ...]:
    lowered = query.lower().strip()
    tag_set = {tag.lower() for tag in tags}
    matches: list[Mapping[str, Any]] = []
    for record in list_lessons(root):
        if domain and str(record.get("domain", "")) != domain:
            continue
        record_tags = {str(tag).lower() for tag in record.get("tags", ())}
        if tag_set and not tag_set.intersection(record_tags):
            continue
        text = json.dumps(record, sort_keys=True).lower()
        if lowered and not _query_matches(lowered, text):
            continue
        matches.append(record)
    return tuple(matches[-limit:])


def retrieve_similar_lessons(state_or_query: Mapping[str, Any] | str, root: str | Path = ".", limit: int = 5) -> tuple[Mapping[str, Any], ...]:
    if isinstance(state_or_query, Mapping):
        query = str(state_or_query.get("goal", ""))
        tags = tuple(str(tag) for tag in state_or_query.get("memory_tags", ()) if str(tag).strip())
        if not tags:
            tags = _tags_from_text(query)
    else:
        query = str(state_or_query)
        tags = _tags_from_text(query)
    domain = _domain_from_tags(tags)
    return query_lessons(query, domain=domain if domain != "general" else "", tags=tags, root=root, limit=limit)


def _lesson_path(root: str | Path, directory: str | Path, lesson_id: str) -> Path:
    safe = "".join(ch for ch in lesson_id if ch.isalnum() or ch in {"-", "_", "."}).strip(".")
    if not safe:
        raise ValueError("lesson_id is required")
    return Path(root).resolve() / directory / f"{safe}.json"


def _read_record(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"lesson is not a JSON object: {path}")
    return dict(payload)


def _domain_from_record(record: Mapping[str, Any]) -> str:
    tags = tuple(str(tag) for tag in record.get("memory_tags", ()) if str(tag).strip())
    text = json.dumps(record, sort_keys=True).lower()
    return _domain_from_tags(tags or _tags_from_text(text))


def _domain_from_tags(tags: tuple[str, ...]) -> str:
    lowered = {tag.lower() for tag in tags}
    for domain in ("dashboard", "release", "policy", "compute", "git", "memory", "neural"):
        if domain in lowered:
            return domain
    if "mission-control" in lowered:
        return "dashboard"
    return "general"


def _tags_from_text(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    tags = ["cognition", "consolidated-lesson"]
    for tag in ("dashboard", "mission-control", "release", "gpu", "policy", "compute", "market", "git", "commit", "memory", "neural"):
        if tag in lowered:
            tags.append("compute" if tag == "market" else "git" if tag == "commit" else tag)
    return tuple(dict.fromkeys(tags))


def _query_matches(query: str, text: str) -> bool:
    if query in text:
        return True
    tokens = tuple(token for token in query.replace("-", " ").split() if len(token) > 4)
    if not tokens:
        return False
    overlap = sum(1 for token in tokens if token in text)
    return overlap >= min(2, len(tokens))


def _merge_tags(domain: str, records: tuple[Mapping[str, Any], ...]) -> tuple[str, ...]:
    tags = ["cognition", "consolidated-lesson", domain]
    for record in records:
        tags.extend(str(tag) for tag in record.get("memory_tags", ()) if str(tag).strip())
    return tuple(dict.fromkeys(tags))


def _recommended_action(domain: str, error_type: str, records: tuple[Mapping[str, Any], ...]) -> str:
    text = json.dumps(records, sort_keys=True).lower()
    if domain == "dashboard":
        return "restart stale local dashboard server before verification"
    if domain == "release" or "gpu" in text:
        return "import GPU evidence artifact then export and verify release evidence"
    if domain == "policy" or error_type == "policy_denial_mismatch":
        return "simulate policy-sensitive action without side effects and request approval for real changes"
    if domain == "compute":
        return "use dry-run compute-market route with no live provider or funds"
    if domain == "git":
        return "run tests/checks, stage requested paths, commit, push, and confirm clean"
    return "retrieve similar lessons and verify the observable outcome before acting"


def _title(domain: str, error_type: str) -> str:
    return f"{domain.replace('-', ' ').title()} lesson for {error_type.replace('_', ' ')}"


def _summary(domain: str, error_type: str, records: tuple[Mapping[str, Any], ...], recommended: str) -> str:
    count = len(records)
    return f"{count} local experience record(s) in {domain} produced {error_type}; future ticks should {recommended}."


def _mean(values: Any) -> float:
    numbers = tuple(float(value) for value in values)
    if not numbers:
        return 0.0
    return sum(numbers) / len(numbers)


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
