#!/usr/bin/env python3
"""Compact dispatcher and source validators for Project Truss."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import yaml

from command_catalog import load_command_catalog
from command_support import *
from commands import load_handlers
from package_provenance import load_runtime_package, runtime_manifest, validate_runtime_reads
from skill_slimming import validate_skill_slimming
from truss_policy import load_contract


SKILLS = {"setup", "start", "shape", "resolve", "close", "advanced-user-input"}
def active_skill_names(root: Path) -> list[str]:
    return sorted(path.name for path in (root / "skills").iterdir() if path.is_dir())


def command_validate_skill_metadata_contract(ctx: Context, args: dict[str, Any]) -> int:
    root = project_root_for(ctx, args)
    findings = []
    files = sorted((root / "skills").glob("*/agents/openai.yaml"))
    if {path.parents[1].name for path in files} != SKILLS:
        findings.append({"reason": "metadata inventory must match the six skills"})
    for path in files:
        try:
            interface = (yaml.safe_load(read_text(path)) or {}).get("interface", {})
            if any(not interface.get(field) for field in ("display_name", "short_description", "default_prompt")):
                findings.append({"path": normalize_rel(path, root), "reason": "metadata interface is incomplete"})
        except Exception as exc:
            findings.append({"path": normalize_rel(path, root), "reason": f"YAML parse failed: {exc}"})
    return emit({"ok": not findings, "phase": "skill-metadata-contract", "findings": findings}, 0 if not findings else 1)


def _text_files(root: Path) -> list[Path]:
    files = []
    for rel in (".codex-plugin", "skills", "scripts", "docs/project-truss", "README.md", "AGENTS.md", ".github"):
        path = root / rel
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(item for item in path.rglob("*") if item.is_file() and item.suffix.lower() not in {".png", ".svg"})
    return files


def _validate_source(root: Path) -> None:
    manifest = json.loads(read_text(root / ".codex-plugin" / "plugin.json"))
    if manifest.get("name") != "project-truss" or manifest.get("version") != "3.0.0":
        raise ScriptError("manifest identity must be project-truss 3.0.0")
    if set(active_skill_names(root)) != SKILLS:
        raise ScriptError("active skill inventory must be exactly " + ", ".join(sorted(SKILLS)))
    if len(read_text(root / "README.md").splitlines()) > 150:
        raise ScriptError("README.md exceeds 150 lines")
    forms = {
        "outcome.yml": [
            "Problem Statement",
            "Solution",
            "User Stories",
            "Implementation Decisions",
            "Testing Decisions",
            "Out of Scope",
            "Further Notes",
        ],
        "leaf.yml": ["Parent", "What to build", "Acceptance criteria", "Blocked by"],
        "standalone.yml": ["What to build", "Acceptance criteria", "Blocked by"],
    }
    for filename, expected in forms.items():
        template = yaml.safe_load(
            read_text(root / ".github" / "ISSUE_TEMPLATE" / filename)
        ) or {}
        labels = [
            item.get("attributes", {}).get("label")
            for item in template.get("body", [])
        ]
        if labels != expected or template.get("labels") != []:
            raise ScriptError(f"{filename} does not match the Project Truss 3.0 contract")
    load_contract(root / "docs" / "project-truss" / "contract.yml")
    load_command_catalog(root)
    package = load_runtime_package(root)
    findings = validate_runtime_reads(root, package)
    if findings:
        raise ScriptError("; ".join(findings))


def _validate_active_text(root: Path) -> None:
    stale = (
        "$superpowers" + "-project:",
        "Super" + "powers",
        "Manual" + " Mode",
        "Auto" + " Mode",
        "Looping" + " Mode",
        "run" + " ledger",
        "issue" + " mirror",
    )
    windows = re.compile(r"(pwsh|power" + r"shell|ExecutionPolicy|windows-latest|\.ps1|C:\\Users\\|cmd\.exe)", re.I)
    offenders = []
    for path in _text_files(root):
        if path.name == "project_truss_cli.py":
            continue
        try:
            text = read_text(path)
        except UnicodeDecodeError:
            continue
        if any(phrase in text for phrase in stale) or windows.search(text):
            offenders.append(normalize_rel(path, root))
    if offenders:
        raise ScriptError("stale active surface: " + ", ".join(offenders[:20]))


def _line_budgets(root: Path) -> dict[str, int]:
    def meaningful_lines(paths: list[Path]) -> int:
        return sum(bool(line.strip()) for path in paths for line in read_text(path).splitlines())

    skill_lines = sum(len(read_text(path).splitlines()) for path in (root / "skills").glob("*/SKILL.md"))
    script_files = [path for path in (root / "scripts").rglob("*") if path.is_file() and path.suffix in {".py", ".sh"}]
    test_files = list((root / "tests").glob("*.py"))
    values = {
        "skill_lines": skill_lines,
        "script_lines": meaningful_lines(script_files),
        "test_lines": meaningful_lines(test_files),
        "shell_files": sum(1 for path in script_files if path.suffix == ".sh") + sum(1 for path in (root / "skills").rglob("*.sh")),
    }
    limits = {"skill_lines": 300, "script_lines": 4250, "test_lines": 2350, "shell_files": 18}
    excess = [f"{name}={values[name]}>{limit}" for name, limit in limits.items() if values[name] > limit]
    if excess:
        raise ScriptError("lean budget failed: " + ", ".join(excess))
    return values


def _run_must(command: list[str], cwd: Path) -> None:
    result = subprocess.run(command, cwd=cwd, text=True)
    if result.returncode != 0:
        raise ScriptError("command failed: " + " ".join(command))


def command_validate(ctx: Context, args: dict[str, Any]) -> int:
    root = ctx.repo_root
    checks = []

    def step(name: str, action) -> None:
        action()
        checks.append({"name": name, "ok": True})

    try:
        step("compact source contract", lambda: _validate_source(root))
        step("active surface", lambda: _validate_active_text(root))
        step("runtime package", lambda: _run_must([sys.executable, str(root / "scripts" / "validate-runtime-package.py"), "--repo-root", str(root)], root))
        step("plugin manifest", lambda: _run_must([sys.executable, str(root / "scripts" / "validate-plugin.py"), str(root)], root))
        step("unit behavior suite", lambda: _run_must([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], root))
        for skill in active_skill_names(root):
            step(f"skill {skill}", lambda skill=skill: _run_must([sys.executable, str(root / "scripts" / "quick-validate-skill.py"), str(root / "skills" / skill)], root))
        step("skill metadata", lambda: command_validate_skill_metadata_contract(ctx, {"RepoRoot": str(root)}) == 0 or (_ for _ in ()).throw(ScriptError("skill metadata failed")))
        step("skill surface", lambda: not validate_skill_slimming(root)[0] or (_ for _ in ()).throw(ScriptError(str(validate_skill_slimming(root)[0]))))
        step("lean budgets", lambda: _line_budgets(root))
        step("release wiring", lambda: load_handlers()["command_prepare_release"](ctx, {"RepoRoot": str(root), "CheckOnly": True}) == 0 or (_ for _ in ()).throw(ScriptError("release wiring failed")))
        return emit({"ok": True, "repo_root": str(root), "line_budgets": _line_budgets(root), "checks": checks})
    except Exception as exc:
        return emit({"ok": False, "repo_root": str(root), "reason": str(exc), "checks": checks}, 1)


FOCUSED_HANDLERS = load_handlers()


def resolve_handler(command_name: str):
    return FOCUSED_HANDLERS.get(command_name) or globals().get(command_name)


def dispatch(ctx: Context) -> int:
    args = parse_ps_args(ctx.args)
    try:
        spec = load_command_catalog(ctx.repo_root).get(ctx.script_rel)
        if spec is None:
            raise ScriptError(f"unregistered script path: {ctx.script_rel}")
        if has_switch(args, "DispatchProbe"):
            return emit({"ok": True, "path": spec.path, "handler": spec.handler, "kind": spec.kind, "mutation": spec.mutation})
        handler = resolve_handler(spec.handler)
        if not callable(handler):
            raise ScriptError(f"unregistered command handler: {spec.handler}")
        return handler(ctx, args)
    except Exception as exc:
        return complete(False, Path(ctx.script_name).stem, str(exc), script=ctx.script_rel)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("script_path")
    known, rest = parser.parse_known_args(argv)
    script_path = Path(known.script_path).resolve()
    root = find_repo_root(script_path)
    return dispatch(Context(script_path, root, normalize_rel(script_path, root), script_path.name, rest, plugin_root=root, invocation_cwd=Path.cwd().resolve()))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
