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


SKILLS = {"start", "shape", "resolve", "close", "advanced-user-input"}
OUTCOME_FIELDS = [
    "Intent", "Current Behavior", "Expected Outcome", "Target Output", "Owner", "Interface",
    "Cutover", "Replaced Path", "Evidence", "Acceptance Proof", "Stop Criteria", "Avoid", "Risk",
]
BOUNDARY_FIELDS = [
    "Files To Create", "Files To Modify", "Files To Avoid", "Source Of Truth", "Read Path", "Write Path",
    "Integration Points", "Migration Or Cutover", "Replaced Path Handling", "Acceptance Proof Gate",
]


def active_skill_names(root: Path) -> list[str]:
    return sorted(path.name for path in (root / "skills").iterdir() if path.is_dir())


def markdown_section(text: str, name: str) -> str | None:
    match = re.search(rf"(?ims)^\s{{0,3}}##\s+{re.escape(name)}\s*$\r?\n(?P<body>.*?)(?=^\s{{0,3}}##\s+|\Z)", text)
    return match.group("body") if match else None


def field_value(text: str, name: str) -> str | None:
    escaped = re.escape(name)
    for pattern in (
        rf"(?im)^\s*\*\*{escaped}\s*:\s*\*\*\s*(.+?)\s*$",
        rf"(?im)^\s*\*\*{escaped}\*\*\s*:\s*(.+?)\s*$",
        rf"(?im)^\s*{escaped}\s*:\s*(.+?)\s*$",
    ):
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


def _concrete(field: str, value: str | None) -> tuple[bool, str]:
    if value is None or not value.strip():
        return False, f"{field} is empty"
    if re.match(r"^(tbd|none|n/a|na|not applicable|same as above|-)$", value.strip(), re.I):
        return False, f"{field} uses a generic value"
    if field == "Acceptance Proof" and re.match(r"^(tests? pass(?:ed)?|unit tests? pass(?:ed)?|lint pass(?:ed)?|diff reviewed)$", value.strip(), re.I):
        return False, "Acceptance Proof must prove behavior, not only tests or diffs"
    return True, "passed"


def _required_fields(section: str, fields: list[str], label: str) -> tuple[bool, str, dict[str, str]]:
    values: dict[str, str] = {}
    for field in fields:
        value = field_value(section, field)
        ok, reason = _concrete(field, value)
        if not ok:
            return False, f"{label} {reason}", values
        values[field] = value or ""
    return True, "passed", values


def task_blocks(lines: list[str]) -> list[dict[str, Any]]:
    matches = []
    for index, line in enumerate(lines):
        match = re.match(r"^\s{0,3}#{2,4}\s+Task\s+(?P<number>\d+)\s*[:.-]\s*(?P<title>.+?)\s*$", line)
        if match:
            matches.append({"number": int(match.group("number")), "title": match.group("title").strip(), "start": index})
    return [
        {**item, "lines": lines[item["start"]:(matches[index + 1]["start"] if index + 1 < len(matches) else len(lines))]}
        for index, item in enumerate(matches)
    ]


def _use_cases(block: dict[str, Any]) -> list[str]:
    lines = block["lines"]
    start = next((index for index, line in enumerate(lines) if re.match(r"^\s*\*\*Use Cases:\*\*\s*$", line)), -1)
    if start < 0:
        return []
    cases = []
    for line in lines[start + 1:]:
        if re.match(r"^\s{0,3}#{1,6}\s+", line) or re.match(r"^\s*\*\*[^*]+:\*\*\s*$", line):
            break
        if re.match(r"^\s*[-*]\s+\S", line) or re.match(r"^\s*\d+\.\s+\S", line):
            cases.append(line.strip())
    return cases


def test_plan_outcome_proof(text: str) -> dict[str, Any]:
    outcome = markdown_section(text, "Outcome Proof")
    boundaries = markdown_section(text, "Implementation Boundaries")
    if outcome is None:
        return {"ok": False, "phase": "plan-outcome-proof", "reason": "missing ## Outcome Proof"}
    if boundaries is None:
        return {"ok": False, "phase": "plan-outcome-proof", "reason": "missing ## Implementation Boundaries"}
    ok, reason, outcome_values = _required_fields(outcome, OUTCOME_FIELDS, "Outcome Proof")
    if not ok:
        return {"ok": False, "phase": "plan-outcome-proof", "reason": reason}
    ok, reason, boundary_values = _required_fields(boundaries, BOUNDARY_FIELDS, "Implementation Boundaries")
    if not ok:
        return {"ok": False, "phase": "plan-outcome-proof", "reason": reason}
    cases = "\n".join(case for block in task_blocks(text.splitlines()) for case in _use_cases(block)).lower()
    if not cases or not re.search(r"acceptance|evidence|proof|validator|visible", cases) or not re.search(r"cutover|migration|duplicate|retire|redirect|delete", cases):
        return {"ok": False, "phase": "plan-outcome-proof", "reason": "Task use cases must cover evidence and displaced-path handling"}
    return {"ok": True, "phase": "plan-outcome-proof", "reason": "outcome proof passed", "fields": {"outcome_proof": outcome_values, "implementation_boundaries": boundary_values}}


def _artifact(root: Path, args: dict[str, Any], name: str) -> tuple[Path, str]:
    value = arg_value(args, name)
    if not value:
        raise ScriptError(f"{name} is required")
    path = project_path_for(root, str(value), name)
    if not path.is_file():
        raise ScriptError(f"artifact does not exist: {value}")
    return path, normalize_rel(path, root)


def command_validate_plan_task_use_cases(ctx: Context, args: dict[str, Any]) -> int:
    root = project_root_for(ctx, args)
    path, rel = _artifact(root, args, "PlanPath")
    blocks = task_blocks(read_text(path).splitlines())
    if not blocks:
        raise ScriptError("plan has no numbered Task sections")
    results = [{"task": f"Task {block['number']}", "title": block["title"], "use_case_count": len(_use_cases(block)), "ok": bool(_use_cases(block))} for block in blocks]
    ok = all(item["ok"] for item in results)
    return emit({"ok": ok, "phase": "plan-task-use-cases", "plan_path": rel, "task_count": len(blocks), "tasks": results}, 0 if ok else 1)


def command_validate_plan_outcome_proof(ctx: Context, args: dict[str, Any]) -> int:
    root = project_root_for(ctx, args)
    path, rel = _artifact(root, args, "PlanPath")
    result = test_plan_outcome_proof(read_text(path))
    result["plan_path"] = rel
    return emit(result, 0 if result["ok"] else 1)


def command_validate_skill_metadata_contract(ctx: Context, args: dict[str, Any]) -> int:
    root = project_root_for(ctx, args)
    findings = []
    files = sorted((root / "skills").glob("*/agents/openai.yaml"))
    if {path.parents[1].name for path in files} != SKILLS:
        findings.append({"reason": "metadata inventory must match the five skills"})
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
    if manifest.get("name") != "project-truss" or manifest.get("version") != "2.0.0":
        raise ScriptError("manifest identity must be project-truss 2.0.0")
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
            raise ScriptError(f"{filename} does not match the Project Truss 2.0 contract")
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
    skill_lines = sum(len(read_text(path).splitlines()) for path in (root / "skills").glob("*/SKILL.md"))
    script_files = [path for path in (root / "scripts").rglob("*") if path.is_file() and path.suffix in {".py", ".sh"}]
    test_files = list((root / "tests").glob("*.py"))
    values = {
        "skill_lines": skill_lines,
        "script_lines": sum(len(read_text(path).splitlines()) for path in script_files),
        "test_lines": sum(len(read_text(path).splitlines()) for path in test_files),
        "shell_files": sum(1 for path in script_files if path.suffix == ".sh") + sum(1 for path in (root / "skills").rglob("*.sh")),
    }
    limits = {"skill_lines": 300, "script_lines": 4050, "test_lines": 2200, "shell_files": 18}
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
        receipts = root / ".project-truss" / "runs" / "agent-trials" / "current"
        if receipts.is_dir():
            step("fresh-agent receipts", lambda: load_handlers()["command_validate_agent_usability_receipt"](ctx, {"RepoRoot": str(root), "ReceiptDir": str(receipts)}) == 0 or (_ for _ in ()).throw(ScriptError("agent receipts failed")))
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
