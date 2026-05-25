"""Safe import helpers for cloud GPU artifacts."""
from __future__ import annotations
import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any, Mapping

SAFE_SUFFIXES = {".txt", ".json", ".md", ".jsonl", ".log"}
BINARY_SUFFIXES = {".pt", ".pth", ".ckpt", ".safetensors", ".onnx"}


def sha256_file(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def safe_member_name(name: str) -> bool:
    p=Path(name)
    return not p.is_absolute() and '..' not in p.parts and p.suffix.lower() in SAFE_SUFFIXES and p.suffix.lower() not in BINARY_SUFFIXES


def safe_extract_metadata(tarball: Path, out_dir: Path) -> tuple[dict[str,str], tuple[str,...]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    hashes: dict[str,str] = {"source_artifact.tar.gz": sha256_file(tarball)}
    skipped: list[str] = []
    with tarfile.open(tarball, 'r:gz') as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            if not safe_member_name(member.name):
                skipped.append(member.name)
                continue
            target = out_dir / Path(member.name).name
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            data = extracted.read(2_000_000)
            target.write_bytes(data)
            hashes[target.name] = hashlib.sha256(data).hexdigest()
    return hashes, tuple(skipped)


def load_json_if_present(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, Mapping) else {}


def find_text(directory: Path, names: tuple[str,...]) -> str:
    for name in names:
        path=directory/name
        if path.exists():
            return path.read_text(encoding='utf-8', errors='replace').strip()
    return ""
