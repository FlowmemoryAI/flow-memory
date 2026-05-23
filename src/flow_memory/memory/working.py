"""Working memory: small bounded typed blackboard."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Iterable

from flow_memory.core.types import MemoryRecord


@dataclass
class WorkingMemory:
    """Small bounded typed blackboard, defaulting to Miller-style capacity 7."""

    capacity: int = 7
    _items: deque[MemoryRecord] = field(default_factory=deque, init=False, repr=False)

    def put(self, record: MemoryRecord) -> None:
        self._items.append(record)
        while len(self._items) > self.capacity:
            self._items.popleft()

    def extend(self, records: Iterable[MemoryRecord]) -> None:
        for record in records:
            self.put(record)

    def snapshot(self) -> tuple[MemoryRecord, ...]:
        return tuple(self._items)

    def by_kind(self, kind: str) -> tuple[MemoryRecord, ...]:
        return tuple(record for record in self._items if record.kind == kind)

    def clear(self) -> None:
        self._items.clear()
