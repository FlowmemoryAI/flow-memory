"""Safe neural artifact metadata helpers.

The GPU evidence importer records hashes for every archive member, but only
persists small text/JSON metadata. Model weights and binary payloads are never
extracted into release evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Mapping

SAFE_TEXT_SUFFIXES = frozenset({".json", ".jsonl", ".md", ".txt", ".log", ".csv", ".yaml", ".yml"})
CHECKPOINT_SUFFIXES = frozenset({".pt", ".pth", ".ckpt", ".safetensors", ".onnx", ".bin"})
MAX_METADATA_BYTES = 1_048_576
HASH_CHUNK_BYTES = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_stream(handle: BinaryIO, *, capture_limit: int = 0) -> tuple[str, int, bytes | None, bool]:
    """Hash a stream and optionally capture bytes up to ``capture_limit``.

    Returns ``(sha256, size_bytes, captured_bytes, over_limit)``. If the stream
    exceeds ``capture_limit`` the returned capture is ``None``; hashing still
    consumes the whole stream.
    """

    digest = hashlib.sha256()
    chunks: list[bytes] = [] if capture_limit > 0 else []
    total = 0
    over_limit = False
    while True:
        chunk = handle.read(HASH_CHUNK_BYTES)
        if not chunk:
            break
        digest.update(chunk)
        total += len(chunk)
        if capture_limit > 0 and not over_limit:
            if total <= capture_limit:
                chunks.append(chunk)
            else:
                over_limit = True
                chunks.clear()
    captured = b"".join(chunks) if capture_limit > 0 and not over_limit else None
    return digest.hexdigest(), total, captured, over_limit


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return payload


def run_id_from_artifact(path: Path) -> str:
    name = path.name
    for suffix in (".tar.gz", ".tgz", ".tar", ".zip"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def safe_archive_name(name: str) -> str | None:
    normalized = name.replace("\\", "/").strip()
    if not normalized or normalized.startswith("/"):
        return None
    path = PurePosixPath(normalized)
    parts = tuple(part for part in path.parts if part not in {"", "."})
    if not parts or any(part == ".." for part in parts):
        return None
    return "/".join(parts)


def is_safe_metadata_name(name: str, *, size_bytes: int | None = None) -> bool:
    safe_name = safe_archive_name(name)
    if safe_name is None:
        return False
    suffix = PurePosixPath(safe_name).suffix.lower()
    if suffix not in SAFE_TEXT_SUFFIXES:
        return False
    return size_bytes is None or size_bytes <= MAX_METADATA_BYTES


def is_checkpoint_name(name: str) -> bool:
    return PurePosixPath(name.replace("\\", "/")).suffix.lower() in CHECKPOINT_SUFFIXES


def metadata_output_path(metadata_dir: Path, archive_name: str) -> Path:
    safe_name = safe_archive_name(archive_name)
    if safe_name is None:
        raise ValueError(f"unsafe archive member path: {archive_name}")
    return metadata_dir / safe_name


def relative_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def checkpoint_metadata_from_path(path: Path, root: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "name": path.name,
        "path": relative_posix(path, root),
        "suffix": path.suffix.lower(),
        "size_bytes": stat.st_size,
        "sha256": sha256_file(path),
    }


def list_checkpoint_metadata(root: Path) -> tuple[Mapping[str, Any], ...]:
    if not root.exists():
        return ()
    records = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and is_checkpoint_name(item.name)):
        records.append(checkpoint_metadata_from_path(path, root))
    return tuple(records)
