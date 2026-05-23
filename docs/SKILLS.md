# Skills

Status: implemented local skill system; production scheduling/network execution remains future work.

## Implemented

- `SkillManifest` with schemas, permissions, schedule, economic value, capabilities, and risk level.
- `SkillRegistry` for registration and lookup.
- `SkillRunner` with schema validation and `SafetySystem` policy checks before handler execution.
- `SkillScheduler` for deterministic interval-based local scheduling.
- `SkillEvaluator` for local quality scoring.
- `SkillRepairPlanner` for safety-gated repair plans that do not auto-modify code.
- `SkillProvenanceRecord` for source/version metadata.
- Starter built-ins for research brief, repo audit, market watch, memory consolidation, safety review, and economic task proposal.

## Difference from AEON

AEON is strong at unattended scheduled skills. Flow Memory's skill system is smaller today, but each skill has explicit cognitive/economic context: permissions, risk, capability requirements, economic value, safety decision, audit events, and optional repair planning.

## Non-goals

- No unattended cloud scheduler by default.
- No automatic code patching without approval.
- No external API keys required.
