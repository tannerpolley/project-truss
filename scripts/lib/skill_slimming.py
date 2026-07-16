"""Lean-surface checks for Project Truss skills."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


SKILLS = {"start", "shape", "deliver", "close", "advanced-user-input"}
STALE = (
    "$superpowers" + "-project:",
    "Manual" + " Mode",
    "Auto" + " Mode",
    "Looping" + " Mode",
    "run" + " ledger",
    "issue" + " mirror",
)


def validate_skill_slimming(root: Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    findings: list[dict[str, str]] = []
    skill_files = sorted((root / "skills").glob("*/SKILL.md"))
    names = {path.parent.name for path in skill_files}
    if names != SKILLS:
        findings.append({"code": "skill-inventory", "actual": ",".join(sorted(names))})
    metadata_names = {path.parents[1].name for path in (root / "skills").glob("*/agents/openai.yaml")}
    if metadata_names != SKILLS:
        findings.append({"code": "metadata-inventory", "actual": ",".join(sorted(metadata_names))})
    lines = 0
    for path in skill_files:
        text = path.read_text(encoding="utf-8")
        lines += len(text.splitlines())
        for phrase in STALE:
            if phrase in text:
                findings.append({"code": "stale-language", "path": path.relative_to(root).as_posix(), "phrase": phrase})
        metadata = path.parent / "agents" / "openai.yaml"
        if not metadata.is_file():
            continue
        value = yaml.safe_load(metadata.read_text(encoding="utf-8")) or {}
        interface = value.get("interface", {}) if isinstance(value, dict) else {}
        for field in ("display_name", "short_description", "default_prompt"):
            if not interface.get(field):
                findings.append({"code": "metadata-field", "path": metadata.relative_to(root).as_posix(), "field": field})
    if lines > 300:
        findings.append({"code": "skill-line-budget", "actual": str(lines), "target": "300"})
    return findings, {"skill_count": len(names), "skill_lines": lines, "target_skill_lines": 300}
