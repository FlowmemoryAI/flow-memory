"""Agent goals, priorities, decomposition, and conflict detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from flow_memory.core.types import new_id


class GoalPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class GoalStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


@dataclass
class Goal:
    description: str
    priority: GoalPriority = GoalPriority.NORMAL
    status: GoalStatus = GoalStatus.PENDING
    completion_criteria: tuple[str, ...] = field(default_factory=tuple)
    goal_id: str = field(default_factory=lambda: new_id("goal"))

    def decompose(self) -> tuple["Goal", ...]:
        parts = [part.strip() for part in self.description.replace(";", ".").split(".") if part.strip()]
        if len(parts) <= 1:
            return (self,)
        return tuple(Goal(description=part, priority=self.priority, completion_criteria=self.completion_criteria) for part in parts)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "goal_id": self.goal_id,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "completion_criteria": tuple(self.completion_criteria),
        }


@dataclass
class GoalStack:
    goals: list[Goal] = field(default_factory=list)

    def push(self, goal: Goal) -> None:
        self.goals.append(goal)

    def active(self) -> Goal | None:
        pending = [goal for goal in self.goals if goal.status in {GoalStatus.PENDING, GoalStatus.ACTIVE}]
        order = {GoalPriority.CRITICAL: 0, GoalPriority.HIGH: 1, GoalPriority.NORMAL: 2, GoalPriority.LOW: 3}
        return sorted(pending, key=lambda goal: order[goal.priority])[0] if pending else None

    def conflicts(self) -> tuple[tuple[str, str], ...]:
        conflicts: list[tuple[str, str]] = []
        active = [goal for goal in self.goals if goal.status in {GoalStatus.PENDING, GoalStatus.ACTIVE}]
        for index, left in enumerate(active):
            for right in active[index + 1 :]:
                if _conflicts(left.description, right.description):
                    conflicts.append((left.goal_id, right.goal_id))
        return tuple(conflicts)

    def as_records(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(goal.as_record() for goal in self.goals)


def goal_to_plan_text(goal: Goal) -> str:
    return goal.description


def _conflicts(left: str, right: str) -> bool:
    left_l = left.lower()
    right_l = right.lower()
    return ("do not " in left_l and left_l.replace("do not ", "") in right_l) or (
        "do not " in right_l and right_l.replace("do not ", "") in left_l
    )
