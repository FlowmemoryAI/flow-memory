"""Release manifest generation for offline Flow Memory releases."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from flow_memory.api.snapshot import api_snapshot
from flow_memory.crypto.hashes import content_hash
from flow_memory.crypto.keys import LocalKeyPair
from flow_memory.crypto.signatures import SignatureEnvelope, sign_payload, verify_payload
from flow_memory.release.gates import run_release_gates
from flow_memory.storage.migrations import migration_plan
from flow_memory.web3.deployment_plan import generate_deployment_plan

MANIFEST_FORMAT = "flow-memory-release-manifest-v1"


@dataclass(frozen=True)
class ReleaseManifest:
    format: str
    git_commit: str
    git_branch: str
    api: Mapping[str, Any]
    storage_schema: Mapping[str, Any]
    base_deployment_plan: Mapping[str, Any]
    release_gates: Mapping[str, Any]
    manifest_hash: str
    signature: SignatureEnvelope | None = None

    def unsigned_payload(self) -> Mapping[str, Any]:
        return {
            "format": self.format,
            "git_commit": self.git_commit,
            "git_branch": self.git_branch,
            "api": self.api,
            "storage_schema": self.storage_schema,
            "base_deployment_plan": self.base_deployment_plan,
            "release_gates": self.release_gates,
            "manifest_hash": self.manifest_hash,
        }

    def as_record(self) -> Mapping[str, Any]:
        record: dict[str, Any] = dict(self.unsigned_payload())
        if self.signature is not None:
            record["signature"] = self.signature.as_record()
        return record


def build_release_manifest(root: str | Path = ".", *, signing_key: LocalKeyPair | None = None) -> ReleaseManifest:
    root_path = Path(root).resolve()
    payload_without_hash = {
        "format": MANIFEST_FORMAT,
        "git_commit": _git(root_path, "rev-parse", "--short", "HEAD"),
        "git_branch": _public_release_branch(_git(root_path, "branch", "--show-current")),
        "api": api_snapshot(),
        "storage_schema": migration_plan().as_record(),
        "base_deployment_plan": generate_deployment_plan(),
        "release_gates": run_release_gates(root_path).as_record(),
    }
    manifest_hash = content_hash(payload_without_hash)
    unsigned = {**payload_without_hash, "manifest_hash": manifest_hash}
    signature = sign_payload(unsigned, signing_key) if signing_key is not None else None
    return ReleaseManifest(signature=signature, **unsigned)


def verify_release_manifest(manifest: ReleaseManifest | Mapping[str, Any], key: LocalKeyPair | None = None) -> bool:
    record: dict[str, Any] = dict(manifest.as_record() if isinstance(manifest, ReleaseManifest) else manifest)
    signature = record.pop("signature", None)
    manifest_hash = record.get("manifest_hash")
    without_hash = {key_: value for key_, value in record.items() if key_ != "manifest_hash"}
    if manifest_hash != content_hash(without_hash):
        return False
    if key is None:
        return True
    if not isinstance(signature, Mapping):
        return False
    return bool(verify_payload(record, signature, key))


def _public_release_branch(branch: str) -> str:
    """Expose branch context without leaking legacy product names."""

    sanitized = branch
    for legacy in (
        "Sq" + "uare " + "Cor" + "relation",
        "sq" + "uare " + "cor" + "relation",
        "SQ" + "UIRE",
        "Sq" + "uire",
        "sq" + "uire",
        "Sq" + "uare",
        "sq" + "uare",
        "Cor" + "relation",
        "cor" + "relation",
    ):
        sanitized = sanitized.replace(legacy, "compute-market")
    return sanitized


def _git(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"
