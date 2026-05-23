# AEON competitor notes

## Sources reviewed

- README context supplied for this review. Source URL to verify when available: repository README for AEON.
- Retrieval gap: no independently fetched repository URL was available in this task context. The claims below should be treated as README claims until verified against source files, tests, releases, and runtime behavior.

## README claims

AEON's README claims:

- 121 skills
- unattended schedules
- self-healing
- quality scoring
- persistent memory
- reactive triggers
- GitHub Actions integration
- MCP and A2A gateways
- dashboard
- skill catalog
- skill repair and self-improvement

## Engineering-relevant interpretation

AEON is positioned as an automation platform with a large skill catalog and autonomous maintenance loop. Its differentiator is breadth of orchestration features: scheduled execution, reactive triggers, quality measurement, skill repair, and external gateway integrations.

The risk is that README-level breadth can obscure whether the runtime is deterministic, locally inspectable, safe under unattended execution, or suitable for high-reliability workflows. Flow Memory should not respond by matching the feature list one-for-one without stronger safety and evidence semantics.

## Flow Memory requirements derived from AEON comparison

### Skill system

- Represent each skill with a manifest containing inputs, outputs, required permissions, safety class, deterministic test cases, and version.
- Refuse unregistered skills by default in local/offline mode.
- Require skill execution records: agent ID, skill ID, input hash, output hash, policy result, start/end timestamp, and error state.
- Separate skill discovery from skill execution. A dashboard or catalog must not grant execution rights.

### Unattended schedules and reactive triggers

- Scheduled or reactive work must use an explicit policy envelope: allowed tools, maximum spend, maximum duration, allowed files/resources, and escalation behavior.
- Triggers must be auditable and replayable from stored events.
- The scheduler must support dry-run planning before execution.
- Default local runtime should disable unattended external side effects unless the user opts in.

### Quality scoring

- Quality scores must be computed from observable evidence, not free-form self-assessment.
- Store score components separately: task success, test evidence, reviewer evidence, policy violations, dispute status, and regression history.
- Never let a single aggregate score replace provenance.

### Self-healing and skill repair

- Self-repair must produce a patch, evidence, and rollback path.
- Self-repair must not silently modify policies, secrets, deployment settings, or economic settlement rules.
- The system should distinguish repair suggestions from applied repairs.
- Repairs that affect security, funds, identity, or governance require human approval in default configuration.

### MCP/A2A/GitHub Actions gateways

- Gateways must be adapters, not core dependencies.
- Gateway calls must preserve Flow Memory's audit schema and safety decisions.
- External automation should receive least-privilege tokens and scoped manifests.
- GitHub Actions integration must be optional and must not be required for local operation.

## Gaps and cautions

- README claims do not establish production readiness, complete implementation, quality of the 121 skills, or safety of unattended execution.
- Self-healing and self-improvement claims require special scrutiny because they can mask uncontrolled mutation if not constrained by policy and audit trails.
- Gateway breadth is valuable only if permissioning, provenance, and replay are first-class.

## Flow Memory response

Flow Memory should compete on trustworthy autonomy rather than raw skill count: deterministic skill manifests, guarded execution, provenance-rich memory, explicit approval gates for risky repairs, and local-first operation.
