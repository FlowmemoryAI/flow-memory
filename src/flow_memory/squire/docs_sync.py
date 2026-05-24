"""Machine-readable Squire/UsePod documentation sync seams.

Base tests never fetch the network. These records tell Flow Memory what to sync
when an operator explicitly enables documentation refreshes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class DocsSource:
    name: str
    url: str
    kind: str
    live_or_roadmap: str = "live"
    purpose: str = "capability refresh"

    def as_record(self) -> Mapping[str, Any]:
        return dict(self.__dict__)


def default_squire_docs_sources() -> tuple[DocsSource, ...]:
    return (
        DocsSource("UsePod pages manifest", "https://docs.usepod.ai/pages.json", "pages_manifest", purpose="discover docs pages and markdown URLs"),
        DocsSource("UsePod llms", "https://docs.usepod.ai/llms.txt", "llms", purpose="agent-readable docs index"),
        DocsSource("UsePod full docs", "https://docs.usepod.ai/llms-full.txt", "llms_full", purpose="offline docs snapshot"),
        DocsSource("Sortis skills catalog", "https://github.com/Sortis-AI/skills", "skills_catalog", purpose="installable skills discovery"),
    )


def docs_sync_plan(*, enabled: bool = False) -> Mapping[str, Any]:
    return {
        "enabled": enabled,
        "network_required": True,
        "base_tests_fetch_network": False,
        "sources": tuple(source.as_record() for source in default_squire_docs_sources()),
        "memory_policy": "store source URL, content hash, fetched_at, and live/roadmap classification",
    }
