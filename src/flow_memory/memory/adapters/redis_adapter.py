"""Optional Redis memory adapter seam."""
from __future__ import annotations


class RedisMemoryAdapter:
    def __init__(self, url: str) -> None:
        self.url = url

    def _client(self):
        try:
            import redis  # type: ignore
        except Exception as exc:
            raise RuntimeError("Redis adapter requires optional dependency: redis") from exc
        return redis.Redis.from_url(self.url)

    def write(self, key: str, value: str) -> None:
        self._client().set(key, value)

    def read(self, key: str) -> str | None:
        value = self._client().get(key)
        return value.decode("utf-8") if isinstance(value, bytes) else value
