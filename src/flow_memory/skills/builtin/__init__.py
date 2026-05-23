"""Built-in local starter skills."""

from flow_memory.skills.builtin.economic_task import manifest as economic_task_manifest, run as run_economic_task
from flow_memory.skills.builtin.market_watch import manifest as market_watch_manifest, run as run_market_watch
from flow_memory.skills.builtin.memory_consolidation import manifest as memory_consolidation_manifest, run as run_memory_consolidation
from flow_memory.skills.builtin.repo_audit import manifest as repo_audit_manifest, run as run_repo_audit
from flow_memory.skills.builtin.research_brief import manifest as research_brief_manifest, run as run_research_brief
from flow_memory.skills.builtin.safety_review import manifest as safety_review_manifest, run as run_safety_review

BUILTINS = {
    research_brief_manifest.skill_id: (research_brief_manifest, run_research_brief),
    repo_audit_manifest.skill_id: (repo_audit_manifest, run_repo_audit),
    market_watch_manifest.skill_id: (market_watch_manifest, run_market_watch),
    memory_consolidation_manifest.skill_id: (memory_consolidation_manifest, run_memory_consolidation),
    safety_review_manifest.skill_id: (safety_review_manifest, run_safety_review),
    economic_task_manifest.skill_id: (economic_task_manifest, run_economic_task),
}

__all__ = ["BUILTINS"]
