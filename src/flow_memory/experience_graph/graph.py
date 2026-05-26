"""Artifact-backed Experience Graph for Flow Memory learning traces."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from flow_memory.agent_genesis.contribution import list_contributions
from flow_memory.cognition.consolidation import list_lessons
from flow_memory.cognition.experience import list_experiences
from flow_memory.cognition.state import stable_id, utc_now

DEFAULT_GRAPH_DIR = Path("artifacts/experience_graph/graphs")
PRIVATE_KEYS = frozenset({"raw_private_content", "raw_payload", "private_memory", "private_key", "secret", "token"})
NODE_TYPES = frozenset({"agent", "genome", "goal", "prediction", "action", "outcome", "prediction_error", "lesson", "teaching_event", "contribution", "policy", "proof"})
EDGE_TYPES = frozenset({"has_genome", "pursues_goal", "predicted", "selected_action", "caused", "failed_because", "learned", "reused", "policy_applied", "policy_denied", "contributed", "forked_from", "improved", "taught"})


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    node_type: str
    title: str
    summary: str = ""
    agent_id: str = ""
    ref_id: str = ""
    privacy_mode: str = "private_only"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.node_type not in NODE_TYPES:
            raise ValueError(f"unknown graph node_type: {self.node_type}")
        if not self.node_id:
            raise ValueError("node_id is required")

    def as_record(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "title": self.title,
            "summary": self.summary,
            "agent_id": self.agent_id,
            "ref_id": self.ref_id,
            "privacy_mode": self.privacy_mode,
            "metadata": _sanitize(dict(self.metadata)),
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class GraphEdge:
    edge_id: str
    source_id: str
    target_id: str
    edge_type: str
    weight: float = 1.0
    evidence_ref: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.edge_type not in EDGE_TYPES:
            raise ValueError(f"unknown graph edge_type: {self.edge_type}")
        if not self.source_id or not self.target_id:
            raise ValueError("source_id and target_id are required")

    def as_record(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type,
            "weight": round(max(0.0, min(1.0, float(self.weight))), 6),
            "evidence_ref": self.evidence_ref,
            "metadata": _sanitize(dict(self.metadata)),
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class ExperienceGraph:
    graph_id: str
    nodes: tuple[Mapping[str, Any], ...]
    edges: tuple[Mapping[str, Any], ...]
    metrics: Mapping[str, Any]
    created_at: str = field(default_factory=utc_now)
    local_only: bool = True
    raw_private_payload_excluded: bool = True
    safety_authority: str = "policy_engine_and_approval_gate"

    def as_record(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "nodes": tuple(dict(node) for node in self.nodes),
            "edges": tuple(dict(edge) for edge in self.edges),
            "metrics": dict(self.metrics),
            "created_at": self.created_at,
            "local_only": self.local_only,
            "raw_private_payload_excluded": self.raw_private_payload_excluded,
            "safety_authority": self.safety_authority,
        }


def build_experience_graph(root: str | Path = ".", *, include_demo_if_empty: bool = True, write_artifact: bool = True) -> Mapping[str, Any]:
    root_path = Path(root).resolve()
    experiences = tuple(list_experiences(root_path))
    lessons = tuple(list_lessons(root_path))
    contributions = tuple(list_contributions(root=root_path))
    births = _records_from(root_path / "artifacts" / "genesis" / "births")
    genomes = _records_from(root_path / "artifacts" / "genesis" / "genomes")
    passports = _records_from(root_path / "artifacts" / "genesis" / "passports")
    teaching = _records_from(root_path / "artifacts" / "genesis" / "teaching")
    if include_demo_if_empty and not any((experiences, lessons, contributions, births, genomes, teaching)):
        experiences, lessons, contributions, births, genomes, passports, teaching = _demo_records()

    builder = _GraphBuilder()
    for record in genomes:
        builder.add_genome(record)
    for record in births:
        builder.add_birth(record)
    for record in passports:
        builder.add_passport(record)
    for record in experiences:
        builder.add_experience(record)
    for record in lessons:
        builder.add_lesson(record)
    for record in teaching:
        builder.add_teaching_event(record)
    for record in contributions:
        builder.add_contribution(record)

    metrics = _metrics(builder.nodes.values(), builder.edges.values())
    graph = ExperienceGraph(
        graph_id=stable_id("experience_graph", str(metrics), str(sorted(builder.nodes)), str(sorted(builder.edges))),
        nodes=tuple(node.as_record() for node in sorted(builder.nodes.values(), key=lambda item: item.node_id)),
        edges=tuple(edge.as_record() for edge in sorted(builder.edges.values(), key=lambda item: item.edge_id)),
        metrics=metrics,
    ).as_record()
    result: dict[str, Any] = {"ok": True, "graph": graph, "metrics": metrics}
    if write_artifact:
        result["write"] = write_graph(graph, root_path)
    return result


def write_graph(record: ExperienceGraph | Mapping[str, Any], root: str | Path = ".", directory: str | Path = DEFAULT_GRAPH_DIR) -> Mapping[str, Any]:
    payload = record.as_record() if isinstance(record, ExperienceGraph) else dict(record)
    path = _graph_path(root, directory, str(payload["graph_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "graph_id": payload["graph_id"], "path": _rel(Path(root).resolve(), path), "record": payload}


def list_graphs(root: str | Path = ".", directory: str | Path = DEFAULT_GRAPH_DIR) -> tuple[Mapping[str, Any], ...]:
    base = Path(root).resolve() / directory
    if not base.exists():
        return ()
    return tuple(_read_record(path) for path in sorted(base.glob("*.json")))


def get_graph(graph_id: str, root: str | Path = ".", directory: str | Path = DEFAULT_GRAPH_DIR) -> Mapping[str, Any]:
    path = _graph_path(root, directory, graph_id)
    if not path.exists():
        raise KeyError(f"unknown experience graph: {graph_id}")
    return _read_record(path)


def latest_graph(root: str | Path = ".") -> Mapping[str, Any]:
    records = list_graphs(root)
    if records:
        return records[-1]
    return dict(build_experience_graph(root, write_artifact=True)["graph"])


def agent_graph_view(agent_id: str, root: str | Path = ".", *, graph: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    payload = dict(graph or latest_graph(root))
    nodes = tuple(dict(node) for node in payload.get("nodes", ()) if isinstance(node, Mapping))
    edges = tuple(dict(edge) for edge in payload.get("edges", ()) if isinstance(edge, Mapping))
    node_ids = {str(node.get("node_id", "")) for node in nodes if str(node.get("agent_id", "")) == agent_id}
    for edge in edges:
        if edge.get("source_id") in node_ids or edge.get("target_id") in node_ids:
            node_ids.add(str(edge.get("source_id", "")))
            node_ids.add(str(edge.get("target_id", "")))
    return {
        "ok": True,
        "agent_id": agent_id,
        "graph_id": payload.get("graph_id", ""),
        "nodes": tuple(node for node in nodes if str(node.get("node_id", "")) in node_ids),
        "edges": tuple(edge for edge in edges if str(edge.get("source_id", "")) in node_ids and str(edge.get("target_id", "")) in node_ids),
        "raw_private_payload_excluded": True,
    }


class _GraphBuilder:
    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: dict[str, GraphEdge] = {}

    def node(self, node_type: str, ref_id: str, title: str, *, summary: str = "", agent_id: str = "", metadata: Mapping[str, Any] | None = None, privacy_mode: str = "private_only") -> str:
        node_id = stable_id("graph_node", node_type, ref_id or title, agent_id)
        self.nodes.setdefault(node_id, GraphNode(node_id, node_type, title, summary, agent_id, ref_id, privacy_mode, metadata or {}))
        return node_id

    def edge(self, source_id: str, target_id: str, edge_type: str, *, weight: float = 1.0, evidence_ref: str = "", metadata: Mapping[str, Any] | None = None) -> None:
        edge_id = stable_id("graph_edge", source_id, target_id, edge_type, evidence_ref)
        self.edges.setdefault(edge_id, GraphEdge(edge_id, source_id, target_id, edge_type, weight, evidence_ref, metadata or {}))

    def add_genome(self, genome: Mapping[str, Any]) -> None:
        agent_id = str(genome.get("agent_id", ""))
        agent = self.node("agent", agent_id, agent_id or "Genesis agent", agent_id=agent_id)
        genome_node = self.node("genome", str(genome.get("genome_id", agent_id)), str(genome.get("archetype_id", "agent genome")), agent_id=agent_id, metadata={"instincts": genome.get("instincts", ()), "boundaries": genome.get("boundaries", ())})
        self.edge(agent, genome_node, "has_genome", evidence_ref=str(genome.get("genome_id", "")))
        parent = str(genome.get("parent_genome_id", ""))
        if parent:
            parent_node = self.node("genome", parent, "parent genome", agent_id=agent_id)
            self.edge(genome_node, parent_node, "forked_from", evidence_ref=str(genome.get("genome_id", "")))

    def add_birth(self, birth: Mapping[str, Any]) -> None:
        agent_id = str(birth.get("agent_id", ""))
        agent = self.node("agent", agent_id, str(birth.get("name", agent_id or "born agent")), summary=str(birth.get("purpose", "")), agent_id=agent_id)
        goal = self.node("goal", str(birth.get("birth_id", agent_id)), str(birth.get("purpose", "agent purpose")), agent_id=agent_id)
        self.edge(agent, goal, "pursues_goal", evidence_ref=str(birth.get("birth_id", "")))
        first = dict(birth.get("first_prediction", {})) if isinstance(birth.get("first_prediction", {}), Mapping) else {}
        if first:
            prediction = self.node("prediction", str(birth.get("birth_id", agent_id)), str(first.get("prediction", "first prediction")), agent_id=agent_id, metadata={"confidence": first.get("confidence", 0.0), "risk": first.get("risk", 0.0)})
            self.edge(agent, prediction, "predicted", evidence_ref=str(birth.get("birth_id", "")))

    def add_passport(self, passport: Mapping[str, Any]) -> None:
        agent_id = str(passport.get("agent_id", ""))
        agent = self.node("agent", agent_id, agent_id or "agent", agent_id=agent_id)
        proof = self.node("proof", agent_id, f"stage {passport.get('stage', 'seed')}", agent_id=agent_id, metadata={"prediction_accuracy": passport.get("prediction_accuracy", 0.0), "policy_compliance": passport.get("policy_compliance", 0.0)})
        self.edge(agent, proof, "improved", weight=float(passport.get("prediction_accuracy", 0.0) or 0.0), evidence_ref=agent_id)

    def add_experience(self, experience: Mapping[str, Any]) -> None:
        agent_id = str(experience.get("agent_id", ""))
        experience_id = str(experience.get("experience_id", ""))
        agent = self.node("agent", agent_id, agent_id or "experience agent", agent_id=agent_id)
        goal = self.node("goal", stable_id("goal", agent_id, str(experience.get("goal", ""))), str(experience.get("goal", "local goal")), agent_id=agent_id)
        self.edge(agent, goal, "pursues_goal", evidence_ref=experience_id)
        prediction_record = _mapping(experience.get("prediction", {}))
        action_record = _mapping(experience.get("selected_action", {}))
        actual = _mapping(experience.get("actual_outcome", {}))
        error = _mapping(experience.get("prediction_error", {}))
        policy = _mapping(experience.get("policy_decision", {}))
        prediction = self.node("prediction", str(prediction_record.get("prediction_id", experience_id)), str(prediction_record.get("predicted_result", "predicted outcome")), agent_id=agent_id, metadata={"confidence": prediction_record.get("confidence", 0.0), "risk": prediction_record.get("risk", 0.0)})
        action = self.node("action", str(action_record.get("action_id", experience_id)), str(action_record.get("description", "selected action")), agent_id=agent_id, metadata={"requires_approval": action_record.get("requires_approval", False)})
        outcome = self.node("outcome", stable_id("outcome", experience_id, str(actual)), str(actual.get("reason", "actual outcome")), agent_id=agent_id, metadata={"success": actual.get("success", False), "state_patch": actual.get("state_patch", {})})
        error_node = self.node("prediction_error", str(error.get("error_id", experience_id)), str(error.get("error_type", "prediction_error")), agent_id=agent_id, metadata={"prediction_error": error.get("prediction_error", 0.0), "match_score": error.get("match_score", 0.0)})
        policy_node = self.node("policy", stable_id("policy", experience_id, str(policy)), "policy gate", agent_id=agent_id, metadata=policy)
        lesson = self.node("lesson", stable_id("lesson", experience_id, str(experience.get("lesson", error.get("lesson", "")))), str(experience.get("lesson", error.get("lesson", "lesson learned"))), agent_id=agent_id, metadata={"memory_tags": experience.get("memory_tags", ())})
        self.edge(goal, prediction, "predicted", evidence_ref=experience_id)
        self.edge(prediction, action, "selected_action", evidence_ref=experience_id)
        self.edge(action, outcome, "caused", evidence_ref=experience_id, weight=1.0 if actual.get("success") else 0.35)
        self.edge(outcome, error_node, "failed_because", evidence_ref=experience_id, weight=float(error.get("prediction_error", 0.0) or 0.0))
        self.edge(error_node, lesson, "learned", evidence_ref=experience_id, weight=max(0.1, 1.0 - float(error.get("prediction_error", 0.0) or 0.0)))
        self.edge(policy_node, action, "policy_applied" if policy.get("allowed", policy.get("approved", True)) else "policy_denied", evidence_ref=experience_id)

    def add_lesson(self, lesson: Mapping[str, Any]) -> None:
        lesson_node = self.node("lesson", str(lesson.get("lesson_id", "")), str(lesson.get("title", lesson.get("lesson_id", "consolidated lesson"))), summary=str(lesson.get("summary", "")), metadata={"domain": lesson.get("domain", ""), "usefulness_score": lesson.get("usefulness_score", 0.0), "recommended_future_action": lesson.get("recommended_future_action", "")})
        for source_id in lesson.get("source_experience_ids", ()) if isinstance(lesson.get("source_experience_ids", ()), (list, tuple)) else ():
            source = self.node("prediction_error", str(source_id), "source prediction error")
            self.edge(source, lesson_node, "learned", evidence_ref=str(lesson.get("lesson_id", "")), weight=float(lesson.get("usefulness_score", 0.0) or 0.0))

    def add_teaching_event(self, event: Mapping[str, Any]) -> None:
        agent_id = str(event.get("agent_id", ""))
        teaching = self.node("teaching_event", str(event.get("teaching_event_id", "")), str(event.get("correction_type", "teaching event")), summary=str(event.get("lesson", "")), agent_id=agent_id, metadata={"applies_to_tags": event.get("applies_to_tags", ()), "privacy_mode": event.get("privacy_mode", "private_only")})
        lesson = self.node("lesson", stable_id("lesson", str(event.get("teaching_event_id", "")), str(event.get("lesson", ""))), str(event.get("lesson", "private lesson")), agent_id=agent_id)
        self.edge(teaching, lesson, "taught", evidence_ref=str(event.get("teaching_event_id", "")))

    def add_contribution(self, contribution: Mapping[str, Any]) -> None:
        agent_id = str(contribution.get("agent_id", ""))
        payload = _mapping(contribution.get("sanitized_payload", {}))
        contribution_node = self.node("contribution", str(contribution.get("contribution_id", "")), str(contribution.get("contribution_type", "network contribution")), agent_id=agent_id, privacy_mode=str(contribution.get("privacy_mode", "private_only")), metadata={"validation_status": contribution.get("validation_status", ""), "raw_payload_excluded": contribution.get("raw_payload_excluded", True), "usefulness_score": contribution.get("usefulness_score", 0.0)})
        source = self.node("lesson" if contribution.get("contribution_type") == "consolidated_lesson" else "proof", str(contribution.get("source_record_id", "")), str(payload.get("title", contribution.get("source_record_id", "source record"))), agent_id=agent_id)
        self.edge(source, contribution_node, "contributed", evidence_ref=str(contribution.get("contribution_id", "")), weight=float(contribution.get("usefulness_score", 0.0) or 0.0))


def _metrics(nodes: Iterable[GraphNode], edges: Iterable[GraphEdge]) -> Mapping[str, Any]:
    node_list = tuple(nodes)
    edge_list = tuple(edges)
    node_types: dict[str, int] = {}
    edge_types: dict[str, int] = {}
    for node in node_list:
        node_types[node.node_type] = node_types.get(node.node_type, 0) + 1
    for edge in edge_list:
        edge_types[edge.edge_type] = edge_types.get(edge.edge_type, 0) + 1
    policy_edges = edge_types.get("policy_denied", 0) + edge_types.get("policy_applied", 0)
    return {
        "node_count": len(node_list),
        "edge_count": len(edge_list),
        "node_types": dict(sorted(node_types.items())),
        "edge_types": dict(sorted(edge_types.items())),
        "experience_count": node_types.get("prediction", 0),
        "lesson_count": node_types.get("lesson", 0),
        "contribution_count": node_types.get("contribution", 0),
        "policy_denial_count": edge_types.get("policy_denied", 0),
        "policy_override_rate": round(edge_types.get("policy_denied", 0) / policy_edges, 6) if policy_edges else 0.0,
        "raw_private_payload_excluded": True,
        "local_only": True,
    }


def _demo_records() -> tuple[tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...]]:
    agent_id = "mira-demo-agent"
    experience = {
        "experience_id": "experience_demo_dashboard_stale_server",
        "agent_id": agent_id,
        "goal": "verify Mission Control dashboard",
        "selected_action": {"action_id": "action_restart_dashboard", "description": "restart stale dashboard server and verify served HTML", "requires_approval": False},
        "prediction": {"prediction_id": "prediction_demo_dashboard", "predicted_result": "Mission Control will show real panels after stale server restart", "confidence": 0.82, "risk": 0.14},
        "policy_decision": {"allowed": True, "authority": "policy_engine_and_approval_gate"},
        "actual_outcome": {"success": True, "reason": "served HTML contained Mission Control panels"},
        "prediction_error": {"error_id": "prediction_error_demo_dashboard", "error_type": "minor_difference", "prediction_error": 0.08, "match_score": 0.92, "lesson": "Check port 4173 and verify served HTML before reporting dashboard success."},
        "lesson": "Check port 4173 and verify served HTML before reporting dashboard success.",
        "memory_tags": ("dashboard", "mission-control", "proof-of-learning"),
        "confidence_before": 0.72,
        "confidence_after": 0.88,
        "risk_before": 0.22,
        "risk_after": 0.08,
    }
    lesson = {"lesson_id": "lesson_demo_dashboard_stale_server", "title": "Dashboard stale server lesson", "summary": "Repeated dashboard checks improve after verifying the served HTML.", "domain": "dashboard", "tags": ("dashboard", "proof-of-learning"), "source_experience_ids": (experience["experience_id"],), "repeated_error_type": "minor_difference", "recommended_future_action": experience["lesson"], "usefulness_score": 0.86}
    contribution = {"contribution_id": "contribution_demo_lesson", "agent_id": agent_id, "source_record_id": lesson["lesson_id"], "contribution_type": "consolidated_lesson", "privacy_mode": "sanitized_lessons", "sanitized_payload": {"title": lesson["title"], "summary": lesson["summary"], "raw_private_payload_excluded": True}, "raw_payload_excluded": True, "usefulness_score": 0.86, "validation_status": "accepted"}
    birth = {"birth_id": "birth_demo_mira", "agent_id": agent_id, "name": "Mira", "purpose": "Help me build Flow Memory", "archetype": "research-builder", "genome_id": "genome_demo_mira", "first_prediction": {"prediction": "I can map project state and verify the next safe step.", "confidence": 0.72, "risk": 0.1}}
    genome = {"genome_id": "genome_demo_mira", "agent_id": agent_id, "archetype_id": "research-builder", "instincts": ("careful", "builder"), "boundaries": ("never_share_private_memory", "never_spend_money")}
    passport = {"agent_id": agent_id, "stage": "apprentice", "prediction_accuracy": 0.86, "policy_compliance": 1.0}
    teaching = {"teaching_event_id": "teaching_demo_dashboard", "agent_id": agent_id, "correction_type": "remember_this", "lesson": "Verify observable dashboard state before claiming success.", "privacy_mode": "private_only", "applies_to_tags": ("dashboard",)}
    return (experience,), (lesson,), (contribution,), (birth,), (genome,), (passport,), (teaching,)


def _records_from(directory: Path) -> tuple[Mapping[str, Any], ...]:
    if not directory.exists():
        return ()
    records: list[Mapping[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping):
            records.append(_sanitize(dict(payload)))
    return tuple(records)


def _sanitize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _sanitize(item) for key, item in value.items() if str(key) not in PRIVATE_KEYS}
    if isinstance(value, (list, tuple)):
        return tuple(_sanitize(item) for item in value)
    return value


def _mapping(value: Any) -> Mapping[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _graph_path(root: str | Path, directory: str | Path, graph_id: str) -> Path:
    safe = "".join(ch for ch in graph_id if ch.isalnum() or ch in {"-", "_", "."}).strip(".")
    if not safe:
        raise ValueError("graph_id is required")
    return Path(root).resolve() / directory / f"{safe}.json"


def _read_record(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"graph file is not a JSON object: {path}")
    return dict(payload)


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
