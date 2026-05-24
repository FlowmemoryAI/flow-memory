"""Offline dependency inventory for Flow Memory release evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from flow_memory.crypto.hashes import content_hash


@dataclass(frozen=True)
class DependencyInventory:
    root: str
    manifests: Mapping[str, Any]
    inventory_hash: str

    def as_record(self) -> Mapping[str, Any]:
        return {"root": self.root, "manifests": dict(self.manifests), "inventory_hash": self.inventory_hash}


@dataclass(frozen=True)
class DependencyPolicyReport:
    ok: bool
    inventory_hash: str
    errors: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def as_record(self) -> Mapping[str, Any]:
        return {
            "ok": self.ok,
            "inventory_hash": self.inventory_hash,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def build_dependency_inventory(root: str | Path = ".") -> DependencyInventory:
    root_path = Path(root).resolve()
    manifests: dict[str, Any] = {}
    pyproject = root_path / "pyproject.toml"
    package_json = root_path / "dashboard" / "package.json"
    cargo_toml = root_path / "rust" / "flow-memory-core" / "Cargo.toml"

    if pyproject.exists():
        manifests["python"] = _parse_pyproject(pyproject, root_path)
    if package_json.exists():
        manifests["dashboard"] = _parse_package_json(package_json, root_path)
    if cargo_toml.exists():
        manifests["rust"] = _parse_cargo(cargo_toml, root_path)

    return DependencyInventory(root=str(root_path), manifests=manifests, inventory_hash=content_hash(manifests))


def write_dependency_inventory(root: str | Path, output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_dependency_inventory(root).as_record(), indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return path


def validate_dependency_policy(root: str | Path = ".") -> DependencyPolicyReport:
    inventory = build_dependency_inventory(root)
    errors: list[str] = []
    warnings: list[str] = []

    for required in ("python", "dashboard", "rust"):
        if required not in inventory.manifests:
            errors.append(f"missing dependency manifest: {required}")

    python_manifest = inventory.manifests.get("python", {})
    if python_manifest.get("dependencies"):
        errors.append("pyproject base dependencies must remain empty for the offline default install")
    for group, specs in dict(python_manifest.get("optional_dependencies", {})).items():
        for spec in tuple(specs):
            _validate_python_spec(str(group), str(spec), errors)

    dashboard_manifest = inventory.manifests.get("dashboard", {})
    if dashboard_manifest and not dashboard_manifest.get("private", False):
        errors.append("dashboard package must stay private until an explicit package-publishing release")
    for section in ("dependencies", "dev_dependencies"):
        for name, version in dict(dashboard_manifest.get(section, {})).items():
            _validate_dashboard_spec(str(name), str(version), errors)

    rust_manifest = inventory.manifests.get("rust", {})
    if rust_manifest.get("dependencies"):
        warnings.append("rust helper crate has dependencies; verify Cargo.lock and cargo audit before release")

    return DependencyPolicyReport(
        ok=not errors,
        inventory_hash=inventory.inventory_hash,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


_VERSION_MARKERS = (">=", "==", "~=", "<=", ">", "<")


def _validate_python_spec(group: str, spec: str, errors: list[str]) -> None:
    normalized = spec.strip()
    lowered = normalized.lower()
    if not normalized:
        errors.append(f"empty dependency spec in optional group {group}")
        return
    if " @ " in normalized or lowered.startswith(("git+", "http://", "https://", "file:")):
        errors.append(
            f"non-registry dependency is not allowed in optional group {group}: {normalized}"
        )
    if not any(marker in normalized for marker in _VERSION_MARKERS):
        errors.append(
            f"dependency must declare an explicit version constraint in optional group {group}: {normalized}"
        )


def _validate_dashboard_spec(name: str, version: str, errors: list[str]) -> None:
    normalized = version.strip().lower()
    if not normalized:
        errors.append(f"dashboard dependency {name} has an empty version")
        return
    if normalized in {"*", "latest"}:
        errors.append(f"dashboard dependency {name} must not use {version!r}")
    if normalized.startswith(("git+", "http://", "https://", "file:")):
        errors.append(f"dashboard dependency {name} must not use non-registry source {version!r}")


def _parse_pyproject(path: Path, root: Path) -> Mapping[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return {
        "path": _relative_name(path, root),
        "name": _scalar(lines, "name"),
        "version": _scalar(lines, "version"),
        "requires_python": _scalar(lines, "requires-python"),
        "dependencies": _inline_array(lines, "dependencies"),
        "optional_dependencies": _optional_dependencies(lines),
    }


def _parse_package_json(path: Path, root: Path) -> Mapping[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "path": _relative_name(path, root),
        "name": data.get("name", ""),
        "version": data.get("version", ""),
        "private": bool(data.get("private", False)),
        "dependencies": dict(data.get("dependencies", {})),
        "dev_dependencies": dict(data.get("devDependencies", {})),
    }


def _parse_cargo(path: Path, root: Path) -> Mapping[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return {
        "path": _relative_name(path, root),
        "name": _scalar(lines, "name"),
        "version": _scalar(lines, "version"),
        "edition": _scalar(lines, "edition"),
        "dependencies": _section_keys(lines, "dependencies"),
    }


def _scalar(lines: list[str], key: str) -> str:
    prefix = key + " ="
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(prefix):
            value = stripped.split("=", 1)[1].strip()
            return value.strip('"')
    return ""


def _inline_array(lines: list[str], key: str) -> tuple[str, ...]:
    prefix = key + " ="
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(prefix) and "[" in stripped and "]" in stripped:
            return tuple(_array_items(stripped[stripped.index("[") + 1 : stripped.rindex("]")]))
    return ()


def _optional_dependencies(lines: list[str]) -> Mapping[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    in_optional = False
    current_key = ""
    current_items: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            in_optional = stripped == "[project.optional-dependencies]"
            continue
        if not in_optional or not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped and "[" in stripped:
            if current_key:
                result[current_key] = tuple(current_items)
            current_key = stripped.split("=", 1)[0].strip()
            after = stripped.split("[", 1)[1]
            current_items = _array_items(after.split("]", 1)[0]) if "]" in after else _array_items(after)
            if "]" in stripped:
                result[current_key] = tuple(current_items)
                current_key = ""
                current_items = []
        elif current_key:
            current_items.extend(_array_items(stripped.split("]", 1)[0]))
            if "]" in stripped:
                result[current_key] = tuple(current_items)
                current_key = ""
                current_items = []
    if current_key:
        result[current_key] = tuple(current_items)
    return result


def _array_items(value: str) -> list[str]:
    return [part.strip().strip(',').strip('"') for part in value.split(",") if part.strip().strip(",")]


def _section_keys(lines: list[str], section: str) -> tuple[str, ...]:
    in_section = False
    keys: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            in_section = stripped == f"[{section}]"
            continue
        if in_section and "=" in stripped and not stripped.startswith("#"):
            keys.append(stripped.split("=", 1)[0].strip())
    return tuple(keys)


def _relative_name(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name
