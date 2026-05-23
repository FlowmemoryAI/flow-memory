"""Optional Neo4j memory adapter seam."""
from __future__ import annotations


class Neo4jMemoryAdapter:
    def __init__(self, uri: str, user: str = "neo4j", password: str = "") -> None:
        self.uri = uri
        self.user = user
        self.password = password

    def _driver(self):
        try:
            from neo4j import GraphDatabase  # type: ignore
        except Exception as exc:
            raise RuntimeError("Neo4j adapter requires optional dependency: neo4j") from exc
        return GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def describe(self) -> dict[str, str]:
        return {"adapter": "neo4j", "uri": self.uri, "user": self.user}
