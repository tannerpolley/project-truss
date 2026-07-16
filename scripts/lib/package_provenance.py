"""Deterministic provenance for the installable Project Truss surface."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import fnmatch
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

import yaml


@dataclass(frozen=True)
class PackageEntry:
    path: str
    mode: int
    length: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuntimePackage:
    version: int
    include: tuple[str, ...]


def load_runtime_package(plugin_root: Path) -> RuntimePackage:
    path = Path(plugin_root).resolve() / ".codex-plugin" / "runtime-package.yml"
    if not path.is_file():
        raise ValueError("runtime package manifest is missing")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    patterns = data.get("include")
    if data.get("version") != 1 or not isinstance(patterns, list) or not patterns or any(not isinstance(item, str) or not item.strip() for item in patterns):
        raise ValueError("runtime package manifest requires version 1 and non-empty include patterns")
    return RuntimePackage(1, tuple(patterns))


def _included(path: Path, root: Path, package: RuntimePackage) -> bool:
    rel = path.relative_to(root).as_posix()
    return not any(part in {"__pycache__", ".git"} for part in path.parts) and path.suffix not in {".pyc", ".pyo"} and any(fnmatch.fnmatchcase(rel, pattern) for pattern in package.include)


def _files(root: Path, package: RuntimePackage) -> Iterable[Path]:
    yield from (path for path in root.rglob("*") if path.is_file() and _included(path, root, package))


def runtime_manifest(plugin_root: Path) -> list[PackageEntry]:
    root = Path(plugin_root).resolve()
    package = load_runtime_package(root)
    entries = []
    for path in sorted(_files(root, package), key=lambda item: item.relative_to(root).as_posix()):
        data = path.read_bytes()
        entries.append(PackageEntry(path.relative_to(root).as_posix(), 0o755 if path.stat().st_mode & 0o111 else 0o644, len(data), hashlib.sha256(data).hexdigest()))
    return entries


def validate_runtime_reads(plugin_root: Path, package: RuntimePackage | None = None) -> list[str]:
    root = Path(plugin_root).resolve()
    selected = package or load_runtime_package(root)
    included = {path.relative_to(root).as_posix() for path in _files(root, selected)}
    required = {
        ".codex-plugin/plugin.json",
        ".codex-plugin/runtime-package.yml",
        "docs/project-truss/contract.yml",
        "docs/project-truss/METHODS.md",
        "docs/project-truss/README.md",
    }
    for source_root in (root / "scripts", root / "skills"):
        for path in source_root.rglob("*") if source_root.is_dir() else []:
            if not path.is_file() or path.suffix.lower() not in {".py", ".md", ".yaml", ".yml"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for match in re.finditer(r"docs/project-truss/[A-Za-z0-9_./-]+\.(?:md|ya?ml)", text):
                if (root / match.group(0)).is_file():
                    required.add(match.group(0))
    return [f"runtime read is excluded from package: {path}" for path in sorted(required - included)]


def runtime_contract_hash(plugin_root: Path) -> str:
    payload = [entry.to_dict() for entry in runtime_manifest(plugin_root)]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_runtime_provenance(record: dict[str, Any], plugin_root: Path, project_root: Path) -> None:
    if record.get("manifest") != [entry.to_dict() for entry in runtime_manifest(plugin_root)]:
        raise ValueError("runtime provenance manifest does not match plugin package")
    if record.get("contract_hash") != runtime_contract_hash(plugin_root):
        raise ValueError("runtime provenance contract hash does not match plugin package")
    supplied = record.get("project_root")
    if supplied is None or str(Path(str(supplied)).resolve()) != str(Path(project_root).resolve()):
        raise ValueError("runtime provenance project root does not match invocation")
