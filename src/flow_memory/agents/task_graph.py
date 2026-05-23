"""Resumable task graph for agent plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.core.types import new_id


@dataclass
class TaskNode:
    name: str
    status: str = "pending"
    attempts: int = 0
    max_retries: int = 1
    node_id: str = field(default_factory=lambda: new_id("node"))

    def start(self) -> None:
        if self.status not in {"pending", "failed"}:
            raise ValueError(f"cannot start node in status {self.status}")
        self.status = "running"
        self.attempts += 1

    def complete(self) -> None:
        self.status = "complete"

    def fail(self) -> None:
        self.status = "failed" if self.attempts <= self.max_retries else "terminal_failed"

    def as_record(self) -> Mapping[str, Any]:
        return {"node_id": self.node_id, "name": self.name, "status": self.status, "attempts": self.attempts, "max_retries": self.max_retries}


@dataclass(frozen=True)
class TaskEdge:
    before: str
    after: str

    def as_record(self) -> Mapping[str, str]:
        return {"before": self.before, "after": self.after}


@dataclass
class TaskGraph:
    nodes: dict[str, TaskNode] = field(default_factory=dict)
    edges: tuple[TaskEdge, ...] = field(default_factory=tuple)

    def add_node(self, node: TaskNode) -> None:
        self.nodes[node.node_id] = node

    def ready_nodes(self) -> tuple[TaskNode, ...]:
        ready: list[TaskNode] = []
        for node in self.nodes.values():
            if node.status not in {"pending", "failed"}:
                continue
            blockers = [edge.before for edge in self.edges if edge.after == node.node_id]
            if all(self.nodes[blocker].status == "complete" for blocker in blockers if blocker in self.nodes):
                ready.append(node)
        return tuple(ready)

    def propagate_failure(self, failed_node_id: str) -> None:
        for edge in self.edges:
            if edge.before == failed_node_id and edge.after in self.nodes:
                self.nodes[edge.after].status = "blocked"

    def as_record(self) -> Mapping[str, Any]:
        return {"nodes": tuple(node.as_record() for node in self.nodes.values()), "edges": tuple(edge.as_record() for edge in self.edges)}


def graph_from_steps(step_names: tuple[str, ...]) -> TaskGraph:
    graph = TaskGraph()
    previous_id = ""
    edges: list[TaskEdge] = []
    for name in step_names:
        node = TaskNode(name=name)
        graph.add_node(node)
        if previous_id:
            edges.append(TaskEdge(before=previous_id, after=node.node_id))
        previous_id = node.node_id
    graph.edges = tuple(edges)
    return graph
