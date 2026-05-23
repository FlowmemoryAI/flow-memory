# Datalog Policy Engine Roadmap

Flow Memory should use Datalog-style rules for parts of the agent economy where facts, provenance, and monotonic inference matter more than imperative control flow.

Souffle is a Datalog-inspired logic language used for static analysis and related rule-heavy domains. It can compile declarative rules into efficient native programs, which makes it a good reference point for Flow Memory policy, reputation, task eligibility, slashing, and memory-consolidation inference. Ascent is a Rust-native Datalog-style candidate for a future hardened Rust runtime.

## Current implementation

Starter rule files live in `rules/`:

- `rules/policy.dl`
- `rules/reputation.dl`
- `rules/slashing.dl`
- `rules/task_eligibility.dl`
- `rules/memory_consolidation.dl`

These are readable starter rules, not a required runtime dependency. The default Python test path does not require Souffle.

## Why Datalog belongs in Flow Memory

Datalog is a strong fit for:

- Unsafe action approval requirements.
- Reputation deltas from verified events.
- Slashing after confirmed bad work.
- Task eligibility from capability and reputation facts.
- Memory consolidation from relevance, recency, and repetition.
- Explaining why a task was allowed, blocked, slashed, or routed.

Flow Memory should prefer Datalog for inference that needs auditability and explainability, not for every runtime decision.

## Fact model v0

Policy facts:

```text
action(agent, action_id, permission, risk)
policy(agent, permission, requires_approval)
unsafe_permission(permission)
approval_required(agent, action_id, permission)
```

Reputation facts:

```text
settlement(task, worker, verifier, status)
reputation_delta(agent, task, delta, reason)
```

Slashing facts:

```text
dispute(task, accused, status, finding)
slash_event(agent, task, severity, reason)
escrow_refund(task, requester)
```

Task eligibility facts:

```text
task(task_id, required_capability, min_reputation)
agent_capability(agent, capability)
reputation(agent, score)
eligible(agent, task_id)
ineligible(agent, task_id, reason)
```

Memory facts:

```text
memory_record(record, domain, relevance, age_hours)
repeated_observation(record, count)
consolidate(record, target_domain, reason)
forget_candidate(record, reason)
```

## Runtime path

Near-term:

```text
Python emits facts -> rule file is versioned -> tests verify files exist and contain expected declarations
```

Next:

```text
Python emits facts -> optional Souffle/Ascent runner -> derived decisions -> audit event
```

Longer-term:

```text
Rust policy host -> signed FlowIR manifest -> Datalog inference -> capability decisions -> Wasm host imports
```

## Safety requirements

A Datalog rule output must never silently execute an unsafe action. It may produce a decision candidate such as `approval_required`, but the runtime still has to enforce approval, capability, sandbox, audit, and rate-limit boundaries.

## Limitations

- No Souffle binary is required or invoked in the current validation path.
- Rules are starter specs and are not yet benchmarked.
- Facts are not yet generated automatically from every runtime subsystem.
- Rule outputs are not yet wired into the Python policy engine.
