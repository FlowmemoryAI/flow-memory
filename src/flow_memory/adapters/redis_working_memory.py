"""Optional Redis working-memory adapter."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from flow_memory.core.types import MemoryRecord


@dataclass
class RedisWorkingMemoryAdapter:
    url: str = "redis://localhost:6379/0"
    key_prefix: str = "flow_memory:working"

    def _client(self) -> Any:
        try:
            import redis  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Install flow-memory[memory] to use RedisWorkingMemoryAdapter") from exc
        return redis.Redis.from_url(self.url, decode_responses=True)

    def put(self, agent_id: str, record: MemoryRecord, capacity: int = 7) -> None:
        client = self._client()
        key = f"{self.key_prefix}:{agent_id}"
        client.rpush(key, json.dumps(asdict(record), default=str, sort_keys=True))
        client.ltrim(key, -capacity, -1)

    def snapshot(self, agent_id: str) -> tuple[dict[str, Any], ...]:
        client = self._client()
        key = f"{self.key_prefix}:{agent_id}"
        return tuple(json.loads(row) for row in client.lrange(key, 0, -1))
