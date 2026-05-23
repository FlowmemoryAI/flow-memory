from __future__ import annotations

import json

from flow_memory.action.sandbox_backends import describe_sandbox_backend
from flow_memory.action.sandbox_profiles import SandboxProfile
from flow_memory.action.sandbox_policy import evaluate_sandbox_profile
from flow_memory.action.sandbox_receipts import SandboxReceipt
from flow_memory.crypto.hashes import content_hash


def main() -> int:
    profile = SandboxProfile(network="deny", timeout_seconds=1.0, output_size_limit=1024)
    policy = evaluate_sandbox_profile(profile)
    receipt = SandboxReceipt(status="planned", profile_hash=content_hash(profile.as_record()), metadata={"backend": describe_sandbox_backend().as_record()})
    report = {"ok": not profile.validate() and policy.allowed, "profile": profile.as_record(), "policy": policy.as_record(), "receipt": receipt.as_record()}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
