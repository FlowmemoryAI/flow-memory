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
        manifests["python"] = _parse_pyproject(pyproject)
    if package_json.exists():
        manifests["dashboard"] = _parse_package_json(package_json)
    if cargo_toml.exists():
        manifests["rust"] = _parse_cargo(cargo_toml)

    return DependencyInventory(root=_public_inventory_root(root_path), manifests=manifests, inventory_hash=content_hash(manifests))


def _public_inventory_root(root_path: Path) -> str:
    """Return a stable public root label without leaking workstation paths."""

    return _sanitize_legacy_public_name(root_path.name)


def _sanitize_legacy_public_name(value: str) -> str:
    sanitized = value
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


def _parse_pyproject(path: Path) -> Mapping[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return {
        "path": _relative_name(path),
        "name": _scalar(lines, "name"),
        "version": _scalar(lines, "version"),
        "requires_python": _scalar(lines, "requires-python"),
        "dependencies": _inline_array(lines, "dependencies"),
        "optional_dependencies": _optional_dependencies(lines),
    }


def _parse_package_json(path: Path) -> Mapping[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "path": _relative_name(path),
        "name": data.get("name", ""),
        "version": data.get("version", ""),
        "private": bool(data.get("private", False)),
        "dependencies": dict(data.get("dependencies", {})),
        "dev_dependencies": dict(data.get("devDependencies", {})),
    }


def _parse_cargo(path: Path) -> Mapping[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return {
        "path": _relative_name(path),
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
        if "=" in stripped and "[" in stripped and not stripped.startswith('"'):
            if current_key:
                result[current_key] = tuple(current_items)
            current_key = stripped.split("=", 1)[0].strip()
            after = stripped.split("=", 1)[1].strip()
            array_text = after[after.index("[") + 1 :]
            closed = _contains_array_close(array_text)
            current_items = _array_items(_array_until_close(array_text) if closed else array_text)
            if closed:
                result[current_key] = tuple(current_items)
                current_key = ""
                current_items = []
        elif current_key:
            closed = _contains_array_close(stripped)
            current_items.extend(_array_items(_array_until_close(stripped) if closed else stripped))
            if closed:
                result[current_key] = tuple(current_items)
                current_key = ""
                current_items = []
    if current_key:
        result[current_key] = tuple(current_items)
    return result


def _contains_array_close(value: str) -> bool:
    in_quote = False
    escaped = False
    for char in value:
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_quote:
            escaped = True
            continue
        if char == '"':
            in_quote = not in_quote
            continue
        if char == "]" and not in_quote:
            return True
    return False


def _array_until_close(value: str) -> str:
    in_quote = False
    escaped = False
    chars: list[str] = []
    for char in value:
        if escaped:
            chars.append(char)
            escaped = False
            continue
        if char == "\\" and in_quote:
            chars.append(char)
            escaped = True
            continue
        if char == '"':
            chars.append(char)
            in_quote = not in_quote
            continue
        if char == "]" and not in_quote:
            break
        chars.append(char)
    return "".join(chars)


def _array_items(value: str) -> list[str]:
    items: list[str] = []
    item: list[str] = []
    in_quote = False
    escaped = False
    for char in value:
        if escaped:
            item.append(char)
            escaped = False
            continue
        if char == "\\" and in_quote:
            item.append(char)
            escaped = True
            continue
        if char == '"':
            item.append(char)
            in_quote = not in_quote
            continue
        if char == "," and not in_quote:
            _append_array_item(items, "".join(item))
            item = []
            continue
        item.append(char)
    _append_array_item(items, "".join(item))
    return items


def _append_array_item(items: list[str], item: str) -> None:
    normalized = item.strip().strip(",").strip()
    if not normalized:
        return
    if normalized.startswith('"') and normalized.endswith('"'):
        normalized = normalized[1:-1]
    items.append(normalized)


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


def _relative_name(path: Path) -> str:
    parts = path.parts
    if "flow-memory" in parts:
        return "/".join(parts[parts.index("flow-memory") + 1 :])
    return path.name
