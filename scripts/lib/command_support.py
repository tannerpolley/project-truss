"""Shared parsing, path, process, and receipt mechanics for command modules."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from typing import Any


class ScriptError(Exception):
    pass


@dataclass
class Context:
    script_path: Path
    repo_root: Path
    script_rel: str
    script_name: str
    args: list[str]
    plugin_root: Path | None = None
    invocation_cwd: Path | None = None


def find_repo_root(path: Path) -> Path:
    current = path.resolve().parent
    while current != current.parent:
        if (current / ".codex-plugin" / "plugin.json").is_file() and (current / "scripts").is_dir():
            return current
        current = current.parent
    raise ScriptError(f"could not locate repo root for {path}")


def normalize_rel(path: Path | str, root: Path | None = None) -> str:
    value = Path(path)
    if root is not None:
        try:
            value = value.resolve().relative_to(root.resolve())
        except Exception:
            value = Path(os.path.relpath(str(value), str(root)))
    text = value.as_posix()
    return text[2:] if text.startswith("./") else text


def resolve_under(root: Path, value: str, label: str = "path") -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ScriptError(f"{label} is outside repo root: {resolved}") from exc
    return resolved


def project_root_for(ctx: Context, args: dict[str, Any]) -> Path:
    base = (ctx.invocation_cwd or Path.cwd()).resolve()
    value = arg_value(args, "RepoRoot", "repo_root")
    if value is None:
        return base
    root = Path(str(value))
    return (base / root).resolve() if not root.is_absolute() else root.resolve()


def project_path_for(root: Path, value: str, label: str = "path") -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ScriptError(f"{label}: {resolved} is outside project root") from exc
    return resolved


def parse_ps_args(argv: list[str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {"_positional": []}
    index = 0
    while index < len(argv):
        token = argv[index]
        if token.startswith("--"):
            key = token[2:].replace("-", "_")
        elif token.startswith("-") and token != "-":
            key = token[1:]
        else:
            parsed["_positional"].append(token)
            index += 1
            continue
        if index + 1 < len(argv) and not argv[index + 1].startswith("-"):
            value: Any = argv[index + 1]
            index += 2
        else:
            value = True
            index += 1
        if key in parsed:
            if not isinstance(parsed[key], list):
                parsed[key] = [parsed[key]]
            parsed[key].append(value)
        else:
            parsed[key] = value
    return parsed


def arg_value(args: dict[str, Any], *names: str, default: Any = None) -> Any:
    lowered = {key.lower(): value for key, value in args.items()}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return default


def has_switch(args: dict[str, Any], *names: str) -> bool:
    value = arg_value(args, *names, default=False)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() not in {"", "false", "0", "no"}
    return bool(value)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _strict_json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ScriptError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json_arg(root: Path, args: dict[str, Any], json_name: str, path_name: str, required: bool = True) -> tuple[Any, str]:
    inline = arg_value(args, json_name)
    path_value = arg_value(args, path_name)
    if inline and path_value:
        raise ScriptError(f"provide exactly one of {json_name} or {path_name}")
    if inline:
        return json.loads(str(inline), object_pairs_hook=_strict_json_pairs), ""
    if path_value:
        path = project_path_for(root, str(path_value), path_name)
        if not path.is_file():
            raise ScriptError(f"{path_name} is missing: {path_value}")
        return json.loads(read_text(path), object_pairs_hook=_strict_json_pairs), normalize_rel(path, root)
    if required:
        raise ScriptError(f"{json_name} or {path_name} is required")
    return None, ""


def emit(obj: Any, ok_exit: int = 0) -> int:
    print(json.dumps(obj, indent=2, ensure_ascii=False))
    return ok_exit


def complete(ok: bool, phase: str, reason: str, **extra: Any) -> int:
    payload = {"ok": ok, "phase": phase, "reason": reason, **extra}
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if ok else 1


def run(cmd: list[str], cwd: Path, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def run_checked(cmd: list[str], cwd: Path, timeout: int | None = None) -> dict[str, Any]:
    result = run(cmd, cwd, timeout)
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
    return {"command": " ".join(cmd), "exit_code": result.returncode, "ok": result.returncode == 0}
