"""Local policy gates for constitutional memory writes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

CONSTITUTIONAL_DOMAINS: frozenset[str] = frozenset(
    {
        "identity",
        "goals",
        "constraints",
        "strategy",
        "tasks",
        "observations",
        "outcomes",
        "reputation",
    }
)

_HIGH_INTEGRITY_DOMAINS: frozenset[str] = frozenset(
    {"identity", "goals", "constraints", "reputation"}
)


@dataclass(frozen=True)
class MemoryWriteRequest:
    """Policy input for a proposed constitutional graph write."""

    domain: str
    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    actor: str = "local-agent"
    source: str = "local"
    confidence: float = 1.0


@dataclass(frozen=True)
class MemoryPolicyDecision:
    """Deterministic decision for a memory write."""

    approved: bool
    reasons: Sequence[str] = field(default_factory=tuple)
    requires_human: bool = False
    risk_level: str = "low"


@dataclass(frozen=True)
class MemoryPolicy:
    """Dependency-free local policy for constitutional graph writes.

    The policy is intentionally conservative for identity, goals, constraints, and
    reputation because those domains influence future behavior. Callers can narrow
    writable domains for tests, sandboxes, or delegated agents.
    """

    allowed_domains: frozenset[str] = CONSTITUTIONAL_DOMAINS
    blocked_terms: frozenset[str] = frozenset(
        {"ignore policy", "bypass policy", "disable safety"}
    )
    require_source_for: frozenset[str] = _HIGH_INTEGRITY_DOMAINS
    require_human_for: frozenset[str] = frozenset({"identity", "constraints"})
    min_confidence: float = 0.0

    def evaluate(self, request: MemoryWriteRequest) -> MemoryPolicyDecision:
        reasons: list[str] = []
        domain = request.domain.strip().lower()
        text = request.text.strip()

        if domain not in CONSTITUTIONAL_DOMAINS:
            reasons.append(f"unknown_domain:{domain or '<empty>'}")
        elif domain not in self.allowed_domains:
            reasons.append(f"domain_not_allowed:{domain}")

        if not text:
            reasons.append("empty_text")

        if request.confidence < self.min_confidence:
            reasons.append("confidence_below_minimum")

        lowered = text.lower()
        for term in self.blocked_terms:
            if term in lowered:
                reasons.append(f"blocked_term:{term}")

        if domain in self.require_source_for and not request.source.strip():
            reasons.append("missing_source")

        requires_human = domain in self.require_human_for
        approved = not reasons
        risk_level = "high" if requires_human or reasons else "low"
        return MemoryPolicyDecision(
            approved=approved,
            reasons=tuple(reasons),
            requires_human=requires_human,
            risk_level=risk_level,
        )
