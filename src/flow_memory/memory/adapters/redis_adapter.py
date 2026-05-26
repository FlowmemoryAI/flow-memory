"""Optional Redis memory adapter seam."""
from __future__ import annotations
from typing import Protocol, cast


class _RedisClient(Protocol):
    def set(self, key: str, value: str) -> object: ...

    def get(self, key: str) -> object: ...



class RedisMemoryAdapter:
    def __init__(self, url: str) -> None:
        self.url = url

    def _client(self) -> _RedisClient:
        try:
            import redis
        except Exception as exc:
            raise RuntimeError("Redis adapter requires optional dependency: redis") from exc
        return cast(_RedisClient, redis.Redis.from_url(self.url))

    def write(self, key: str, value: str) -> None:
        self._client().set(key, value)

    def read(self, key: str) -> str | None:
        value = self._client().get(key)
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return cast(str | None, value)
