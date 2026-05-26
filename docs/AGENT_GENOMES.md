# Agent Genomes

An Agent Genome is a portable, inspectable Flow Memory profile that defines how an agent is configured. It is not biological DNA and it does not imply consciousness. It is a structured system configuration.

## Fields

An Agent Genome includes:

- identity: agent id, archetype id, purpose, version
- instincts: product-facing behavior weights such as careful, builder, memory-first, verifier
- boundaries: policy-gated limits such as never spend money and never share private memory
- drive profile: operational weights for goal completion, uncertainty reduction, prediction accuracy, policy compliance, and trust preservation
- cognition profile: predictive core, prediction-error learning, memory consolidation, and local deterministic world model settings
- neural profile: advisory tiny_torch/live neural settings
- memory profile: private memory and memory seed references
- policy profile: supervised mode and approval requirements
- privacy profile: consent mode and raw-payload exclusion
- contribution profile: allowed contribution mode and record types
- benchmark refs: evidence references for deterministic local benchmarks

Private memory is excluded by default.

## Example

```json
{
  "agent_genome": {
    "archetype_id": "research-builder",
    "purpose": "Help me build Flow Memory",
    "instincts": ["careful", "builder", "memory_first"],
    "boundaries": ["ask_before_risky_action", "never_share_private_memory", "never_spend_money"],
    "cognition_profile": {
      "predictive_core_enabled": true,
      "prediction_error_learning": true,
      "memory_consolidation_enabled": true
    },
    "privacy_profile": {
      "consent_mode": "private_only",
      "raw_payload_allowed": false
    },
    "private_memory_excluded": true
  }
}
```

## FlowLang

```flow
agent Mira {
  genesis {
    archetype: "research-builder"
    purpose: "help me build and remember Flow Memory"
    instincts: ["careful", "curious", "builder", "memory_first"]
    boundaries: ["ask_before_risky_action", "never_share_private_memory", "never_spend_money"]
    consent_mode: "private_only"
    stage: "seed"
  }

  memory_seed {
    user_preferences: ["exact commands", "honest status", "visible proof"]
    project_context: ["Flow Memory is the Human Compute Network"]
    behavior_rules: ["do not overclaim", "ask before risky actions"]
  }
}
```

## Forking rule

A public genome can be forked without private memory. Private user memory, raw conversations, secrets, local files, and raw private payloads stay excluded unless a future explicit consent mode allows a sanitized record type.
