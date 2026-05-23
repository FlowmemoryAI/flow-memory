"""Optional Neo4j semantic-memory adapter skeleton."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass
class Neo4jSemanticAdapter:
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "flowmemory"

    def _driver(self) -> Any:
        try:
            from neo4j import GraphDatabase  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Install flow-memory[memory] to use Neo4jSemanticAdapter") from exc
        return GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def merge_fact(self, subject: str, relation: str, object_: str, attrs: Mapping[str, Any] | None = None) -> None:
        driver = self._driver()
        with driver.session() as session:
            session.run(
                """
                MERGE (s:Entity {id: $subject})
                MERGE (o:Entity {id: $object})
                MERGE (s)-[r:RELATION {type: $relation}]->(o)
                SET r += $attrs
                """,
                subject=subject,
                object=object_,
                relation=relation,
                attrs=dict(attrs or {}),
            )
        driver.close()
