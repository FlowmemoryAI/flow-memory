# Sandbox Hardening

Status: functional local safety prototype; not hardened process, container, VM, or kernel isolation.

## Purpose

Define the hardening path from Flow Memory's local policy-gated action execution toward a defensible sandbox boundary for untrusted tools, skills, and agent actions. The sandbox must make unsafe effects explicit, auditable, and deny-by-default before execution.

## Local-safe behavior

- Local actions pass through policy checks, approval decisions, audit logging, rate limits, and circuit breakers.
- Subprocess execution should be capability-scoped and use explicit working directories, environment allowlists, and timeouts.
- File-system and network effects should require declared permissions before execution.
- Audit records should capture actor, requested action, policy decision, approval context, sandbox configuration, and observed result.
- The local sandbox is suitable for deterministic development checks, not hostile-code containment.

## Public-alpha RC1 additions

- `SandboxProfile` now records timeout, memory, CPU, filesystem, network, environment, output limit, and approval requirements.
- `evaluate_sandbox_profile()` blocks unsafe/default-disallowed profiles or marks them approval-required.
- `SandboxReceipt` includes backend metadata for local evidence.
- `DockerSandbox` and `sandbox_backends.py` provide an optional Docker backend seam that is disabled by default and fails clearly when Docker is unavailable or not explicitly enabled.
- `scripts/sandbox_smoke_test.py` verifies the local profile/policy/receipt path without launching untrusted code.

## Limitations

- No claim of escape resistance against malicious code.
- No gVisor, Firecracker, seccomp/AppArmor profile, Windows Job Object policy, container isolation, VM boundary, syscall filter, or eBPF enforcement is certified here.
- Resource accounting is not a complete defense against fork bombs, kernel bugs, side channels, supply-chain attacks, or credential exfiltration.
- Human approval reduces risk but does not replace isolation, least privilege, or incident response.

## Next implementation steps

1. Define a sandbox capability manifest for filesystem, network, process, secret, wallet, and external-service access.
2. Add deny-by-default enforcement around every action executor entry point.
3. Implement OS-specific resource controls and test failure modes for timeout, memory, process count, and denied path/network access.
4. Add an optional container or microVM backend with reproducible profiles and no ambient credentials.
5. Commission security review and adversarial escape testing before running untrusted workloads.
