"""Idempotent repository configuration for the Project Truss facade."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Callable, Mapping

try:
    from .truss_policy import all_method_routes
except ImportError:
    from truss_policy import all_method_routes


_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_CHOICES = {
    "instruction_file": {"AGENTS.md", "CLAUDE.md"},
    "domain_layout": {"single-context", "multi-context"},
}
_TEMPLATES = Path(__file__).parents[2] / "skills/setup/assets"
_START, _END = "<!-- project-truss:setup:start -->", "<!-- project-truss:setup:end -->"


class SetupError(RuntimeError):
    def __init__(self, blocker: str, message: str):
        super().__init__(f"{blocker}: {message}")
        self.blocker = blocker


@dataclass(frozen=True)
class SetupRequest:
    repository: str
    instruction_file: str
    domain_layout: str
    triage_enabled: bool
    available_methods: tuple[str, ...]

    @classmethod
    def from_mapping(cls, data: Any) -> SetupRequest:
        fields = set(cls.__dataclass_fields__)
        if not isinstance(data, Mapping) or set(data) != fields:
            raise ValueError(f"setup requires exactly {', '.join(sorted(fields))}")
        string_fields = ("repository", *tuple(_CHOICES))
        if any(not isinstance(data[field], str) for field in string_fields):
            raise ValueError("repository, instruction_file, and domain_layout must be strings")
        values = {field: data[field].strip() for field in string_fields}
        methods = data["available_methods"]
        if not _REPOSITORY.fullmatch(values["repository"]):
            raise ValueError("repository must be a GitHub OWNER/REPO")
        for field, choices in _CHOICES.items():
            if values[field] not in choices:
                raise ValueError(f"{field} must be {' or '.join(sorted(choices))}")
        if type(data["triage_enabled"]) is not bool:
            raise ValueError("triage_enabled must be boolean")
        if not isinstance(methods, list) or any(not isinstance(method, str) or not method.strip() for method in methods):
            raise ValueError("available_methods must be an array of non-empty strings")
        normalized = tuple(method.strip() for method in methods)
        if len(normalized) != len(set(normalized)):
            raise ValueError("available_methods must not contain duplicates")
        return cls(*(values[field] for field in string_fields), data["triage_enabled"], normalized)


def _replace_agent_skills(text: str, block: str) -> str:
    matches = list(re.finditer(r"(?m)^## Agent skills\s*$", text))
    if len(matches) > 1:
        raise SetupError("state_contradiction", "instruction file has multiple Agent skills sections")
    match = matches[0] if matches else None
    if not match:
        return text.rstrip() + "\n\n## Agent skills\n\n" + _managed("", block)
    next_heading = re.search(r"(?m)^## (?!Agent skills\s*$).+$", text[match.end() :])
    end = match.end() + next_heading.start() if next_heading else len(text)
    prefix = text[: match.end()].rstrip() + "\n\n" + _managed(text[match.end():end], block).rstrip()
    suffix = text[end:].lstrip()
    return prefix + ("\n\n" + suffix if suffix else "\n")


def _template(name: str, **values: str) -> str:
    return (_TEMPLATES / name).read_text(encoding="utf-8").format(**values)


def _managed(text: str, block: str | None) -> str:
    if text.count(_START) != text.count(_END) or text.count(_START) > 1:
        raise SetupError("state_contradiction", "agent doc has malformed managed markers")
    managed = f"{_START}\n{block.rstrip()}\n{_END}" if block else ""
    if _START not in text:
        prefix = text.strip()
        return prefix + (("\n\n" if prefix else "") + managed + "\n" if managed else "\n")
    before, tail = text.split(_START)
    _, after = tail.split(_END)
    return (before.rstrip() + ("\n\n" + managed if managed else "") + after).strip() + "\n"


def validate_setup_target(root: Path, repository: str, runner: Callable[..., Any] = subprocess.run) -> dict[str, Any]:
    def run(command: list[str], blocker: str) -> str:
        try:
            result = runner(command, cwd=root, text=True, capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SetupError(blocker, f"command unavailable: {command[0]}") from exc
        if result.returncode:
            raise SetupError(blocker, result.stderr.strip() or f"{command[0]} failed")
        return result.stdout.strip()

    git_root = run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], "state_contradiction")
    if Path(git_root).resolve() != root.resolve():
        raise SetupError("state_contradiction", "RepoRoot is not the attached Git root")
    observed = run(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
                   "github_capability_missing")
    if observed.casefold() != repository.casefold():
        raise SetupError("github_capability_missing", "authenticated gh cannot verify repository")
    return {"repository": repository, "git_root": str(root.resolve())}


def _commit(root: Path, outputs: Mapping[Path, str | None]) -> list[str]:
    changed, staged, backups = [], {}, {}
    for path, text in outputs.items():
        cursor = root
        for part in path.relative_to(root).parts:
            cursor /= part
            if cursor.is_symlink():
                raise SetupError("state_contradiction", f"setup target is symlinked: {path}")
        try:
            path.resolve().relative_to(root)
        except ValueError as exc:
            raise SetupError("state_contradiction", f"setup target escapes RepoRoot: {path}") from exc
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current != text:
            changed.append(path)
    try:
        for path in changed:
            path.parent.mkdir(parents=True, exist_ok=True)
            for bucket, content in ((staged, outputs[path]), (backups, path.read_text() if path.is_file() else None)):
                if content is None:
                    bucket[path] = None
                    continue
                handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False)
                with handle:
                    handle.write(content)
                os.chmod(handle.name, path.stat().st_mode & 0o777 if path.exists() else 0o644)
                bucket[path] = Path(handle.name)
        applied = []
        for path in changed:
            if staged[path] is None:
                path.unlink(missing_ok=True)
            else:
                os.replace(staged[path], path)
            applied.append(path)
    except Exception as exc:
        recovery = []
        for path in reversed(locals().get("applied", [])):
            try:
                path.unlink(missing_ok=True) if backups[path] is None else os.replace(backups[path], path)
            except OSError:
                recovery.append(f"{path} <- {backups[path]}")
        if recovery:
            raise SetupError("state_contradiction", "setup and rollback failed; recover " + ", ".join(recovery)) from exc
        raise SetupError("state_contradiction", f"setup write failed: {exc}") from exc
    finally:
        for temporary in (*staged.values(), *backups.values()):
            if temporary and temporary.exists() and not any(str(temporary) in item for item in locals().get("recovery", [])):
                temporary.unlink(missing_ok=True)
    return [path.relative_to(root).as_posix() for path in changed]


def apply_setup(root: Path, request: SetupRequest) -> dict[str, Any]:
    root = root.resolve()
    instruction_files = [name for name in ("CLAUDE.md", "AGENTS.md") if (root / name).is_file()]
    contexts = sorted(path.relative_to(root).as_posix() for path in root.glob("*/CONTEXT.md"))
    multi_signals = [name for name in ("CONTEXT-MAP.md", "pnpm-workspace.yaml") if (root / name).is_file()]
    if instruction_files and request.instruction_file != instruction_files[0]:
        raise SetupError("state_contradiction", f"existing instruction preference is {instruction_files[0]}")
    if (multi_signals or len(contexts) > 1) and request.domain_layout != "multi-context":
        raise SetupError("state_contradiction", "repository evidence requires multi-context domain layout")
    observed = {
        "instruction_files": instruction_files,
        "agent_docs": sorted(path.name for path in (root / "docs/agents").glob("*.md")) if (root / "docs/agents").is_dir() else [],
        "context_files": [*sorted(path.name for path in root.glob("CONTEXT*.md")), *contexts],
        "domain_signals": multi_signals,
        "selected_domain_layout": request.domain_layout,
        "reported_available_methods": list(request.available_methods),
    }
    instruction = root / request.instruction_file
    original = instruction.read_text(encoding="utf-8") if instruction.is_file() else ""
    triage = "\n\n### Triage labels\n\nMatt triage roles map to descriptive labels only. See `docs/agents/triage-labels.md`." if request.triage_enabled else ""
    outputs = {
        instruction: _replace_agent_skills(original, _template("agent-skills.md", triage=triage)),
        root / "docs/agents/issue-tracker.md": _template("issue-tracker.md", repository=request.repository),
        root / "docs/agents/domain.md": _template(f"domain-{request.domain_layout}.md"),
    }
    for path in tuple(outputs)[1:]:
        current = path.read_text(encoding="utf-8") if path.is_file() else ""
        outputs[path] = _managed(current, outputs[path])
    triage_path = root / "docs/agents/triage-labels.md"
    triage_current = triage_path.read_text(encoding="utf-8") if triage_path.is_file() else ""
    triage_output = _managed(
        triage_current, _template("triage-labels.md") if request.triage_enabled else None
    )
    outputs[triage_path] = triage_output if triage_output.strip() else None
    changed = _commit(root, outputs)
    return {
        "changed": bool(changed),
        "changed_paths": changed,
        "instruction_file": request.instruction_file,
        "method_routes": all_method_routes(request.available_methods),
        "evidence": observed,
    }
