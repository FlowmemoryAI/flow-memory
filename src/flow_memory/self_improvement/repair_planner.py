"""Repair planning primitives that never apply code changes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence
from uuid import uuid4

from flow_memory.self_improvement.health import HealthReport


@dataclass(frozen=True)
class RepairStep:
    """One proposed local repair action."""

    flag: str
    action: str
    rationale: str
    requires_approval: bool = False
    safe_to_apply_automatically: bool = False


@dataclass(frozen=True)
class RepairPlan:
    """A non-executing repair plan produced from health degradation."""

    steps: Sequence[RepairStep]
    plan_id: str = field(default_factory=lambda: f"repair_{uuid4().hex}")

    @property
    def requires_approval(self) -> bool:
        return any(step.requires_approval for step in self.steps)

    @property
    def applies_code(self) -> bool:
        return False


@dataclass(frozen=True)
class RepairPlanner:
    """Generate concrete repair plans without mutating files or runtime state."""

    recipes: Mapping[str, RepairStep] = field(
        default_factory=lambda: {
            "api_error": RepairStep(
                flag="api_error",
                action="Inspect local API error evidence, isolate failing adapter, and add a focused regression test.",
                rationale="Repeated API failures usually indicate a boundary contract or adapter issue.",
            ),
            "stale_data": RepairStep(
                flag="stale_data",
                action="Refresh the local source snapshot or mark dependent memories stale before further use.",
                rationale="Old inputs can produce invalid plans even when code is healthy.",
            ),
            "rate_limited": RepairStep(
                flag="rate_limited",
                action="Back off the affected local scheduler path and queue work until the limit clears.",
                rationale="Continuing to call a limited service increases failures and noise.",
            ),
            "unsafe_action": RepairStep(
                flag="unsafe_action",
                action="Route the proposed action through human approval and safety policy review before execution.",
                rationale="Unsafe action evidence must not be repaired or bypassed automatically.",
                requires_approval=True,
            ),
            "low_quality": RepairStep(
                flag="low_quality",
                action="Collect failing examples, tighten acceptance criteria, and add a focused quality test.",
                rationale="Quality degradation should be corrected by observable behavior, not hidden thresholds.",
            ),
            "failed_test": RepairStep(
                flag="failed_test",
                action="Reproduce the named failing test locally and plan the smallest source fix that makes it pass.",
                rationale="A failing test is executable evidence for the repair target.",
            ),
            "missing_dependency": RepairStep(
                flag="missing_dependency",
                action="Select a dependency-free fallback or document the unavailable optional capability.",
                rationale="Default runtime must remain local and dependency-free.",
                requires_approval=True,
            ),
        }
    )

    def plan(self, report: HealthReport) -> RepairPlan:
        steps: list[RepairStep] = []
        for flag in sorted(report.flags):
            recipe = self.recipes.get(flag)
            if recipe is None:
                steps.append(
                    RepairStep(
                        flag=flag,
                        action="Escalate unknown degradation flag for human triage.",
                        rationale="Unknown health flags must not trigger automatic behavior.",
                        requires_approval=True,
                    )
                )
            else:
                steps.append(recipe)
        return RepairPlan(steps=tuple(steps))
