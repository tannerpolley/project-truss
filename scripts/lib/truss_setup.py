"""Idempotent repository configuration for Project Truss."""
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
    "repository_profile": {"general", "application-development", "scientific-computing"},
}
_TEMPLATES = Path(__file__).parents[2] / "skills/setup/assets"
_START, _END = "<!-- project-truss:setup:start -->", "<!-- project-truss:setup:end -->"
_SCIENTIFIC_LISTS = (
    "benchmark_roots", "research_roots", "canonical_data_roots", "publication_locks",
    "validation_commands", "experimental_artifact_roots",
)
_SCIENTIFIC_FIELDS = {*_SCIENTIFIC_LISTS, "tolerance_policy", "compatibility_policy", "git_history_preserves_retired_science"}


class SetupError(RuntimeError):
    def __init__(self, blocker: str, message: str):
        super().__init__(f"{blocker}: {message}")
        self.blocker = blocker


def discover_context_files(root: Path) -> tuple[str, ...]:
    """Return the repository's shared-language files in stable relative order."""
    root = root.resolve()
    candidates = (root / "CONTEXT.md", root / "CONTEXT-MAP.md", *root.glob("*/CONTEXT.md"))
    return tuple(sorted({path.relative_to(root).as_posix() for path in candidates if path.is_file()}))


@dataclass(frozen=True)
class SetupRequest:
    repository: str
    repository_profile: str
    instruction_file: str
    domain_layout: str
    triage_enabled: bool
    available_methods: tuple[str, ...]
    scientific: Mapping[str, Any] | None = None

    @classmethod
    def from_mapping(cls, data: Any) -> SetupRequest:
        fields = set(cls.__dataclass_fields__)
        required = fields - {"scientific"}
        if not isinstance(data, Mapping) or not required <= set(data) or set(data) - fields:
            raise ValueError(f"setup requires {', '.join(sorted(required))} and optional scientific")
        string_fields = ("repository", "repository_profile", "instruction_file", "domain_layout")
        if any(not isinstance(data[field], str) for field in string_fields):
            raise ValueError("repository, repository_profile, instruction_file, and domain_layout must be strings")
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
        scientific = data.get("scientific")
        if scientific is not None:
            if values["repository_profile"] != "scientific-computing" or not isinstance(scientific, Mapping) or set(scientific) != _SCIENTIFIC_FIELDS:
                raise ValueError("scientific must be the complete scientific-computing setup object")
            normalized_science: dict[str, Any] = {}
            for field in _SCIENTIFIC_LISTS:
                items = scientific[field]
                if not isinstance(items, list) or any(not isinstance(item, str) or not item.strip() for item in items):
                    raise ValueError(f"scientific {field} must be an array of non-empty strings")
                values_list = [item.strip() for item in items]
                if len(values_list) != len(set(values_list)):
                    raise ValueError(f"scientific {field} must not contain duplicates")
                normalized_science[field] = values_list
            for field in ("tolerance_policy", "compatibility_policy"):
                if not isinstance(scientific[field], str) or not scientific[field].strip():
                    raise ValueError(f"scientific {field} must be non-empty")
                normalized_science[field] = scientific[field].strip()
            if type(scientific["git_history_preserves_retired_science"]) is not bool:
                raise ValueError("scientific git_history_preserves_retired_science must be boolean")
            normalized_science["git_history_preserves_retired_science"] = scientific["git_history_preserves_retired_science"]
            scientific = normalized_science
        return cls(*(values[field] for field in string_fields), data["triage_enabled"], normalized, scientific)


def _repository_profile(root: Path, instruction_files: list[str]) -> str:
    profiles = {
        match.group(1)
        for name in instruction_files
        for match in re.finditer(
            r"(?im)^[ \t]*Repository Profile:[ \t]*(general|application-development|scientific-computing)[ \t]*$",
            (root / name).read_text(encoding="utf-8"),
        )
    }
    if len(profiles) > 1:
        raise SetupError("state_contradiction", "instruction files declare conflicting repository profiles")
    return next(iter(profiles), "general")


def discover_repository_profile(root: Path) -> str:
    return _repository_profile(root, [name for name in ("CLAUDE.md", "AGENTS.md") if (root / name).is_file()])


def _set_repository_profile(text: str, profile: str) -> str:
    marker = re.compile(r"(?im)^[ \t]*Repository Profile:[ \t]*(?:general|application-development|scientific-computing)[ \t]*$")
    if marker.search(text):
        return marker.sub(f"Repository Profile: {profile}", text)
    prefix = text.rstrip()
    return prefix + ("\n\n" if prefix else "") + f"Repository Profile: {profile}\n"


def _scientific_repository(root: Path) -> dict[str, Any]:
    def existing(*candidates: str) -> list[str]:
        return [name for name in candidates if (root / name).exists()]

    return {
        "benchmark_roots": existing("validation", "tests/benchmarks", "benchmarks"),
        "research_roots": existing("docs/research", "research", "lab", "notebooks"),
        "canonical_data_roots": existing("data", "datasets"),
        "publication_locks": existing("validation/locks", "tests/reference", "data/reference"),
        "validation_commands": [
            command for path, command in (
                ("tools/check-affected.sh", "./tools/check-affected.sh"),
                ("tools/check-all.sh", "./tools/check-all.sh"),
                ("scripts/validate.sh", "./scripts/validate.sh"),
            ) if (root / path).is_file()
        ],
        "experimental_artifact_roots": existing("lab", "notebooks"),
        "tolerance_policy": "claim-specific atol/rtol with a named numerical or physical basis",
        "compatibility_policy": "repository-defined only; change-detection snapshots are not scientific oracles",
        "git_history_preserves_retired_science": True,
    }


def _markdown_list(values: list[str], empty: str) -> str:
    return "\n".join(f"- `{value}`" for value in values) if values else f"- {empty}"


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


def _command_output(root: Path, runner: Callable[..., Any], command: list[str], blocker: str) -> str:
    try:
        result = runner(command, cwd=root, text=True, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SetupError(blocker, f"command unavailable: {command[0]}") from exc
    if result.returncode:
        raise SetupError(blocker, result.stderr.strip() or f"{command[0]} failed")
    return result.stdout.strip()


def validate_setup_target(root: Path, repository: str, runner: Callable[..., Any] = subprocess.run) -> dict[str, Any]:
    root = root.resolve()
    git_root = _command_output(root, runner, ["git", "-C", str(root), "rev-parse", "--show-toplevel"], "state_contradiction")
    if Path(git_root).resolve() != root.resolve():
        raise SetupError("state_contradiction", "RepoRoot is not the attached Git root")
    observed = _command_output(root, runner, ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"], "github_capability_missing")
    if observed.casefold() != repository.casefold():
        raise SetupError("github_capability_missing", "authenticated gh cannot verify repository")
    return {"repository": repository, "git_root": str(root.resolve())}


def discover_setup_request(root: Path, runner: Callable[..., Any] = subprocess.run) -> SetupRequest:
    """Infer safe repository defaults; method availability remains an explicit observation."""
    root = root.resolve()

    observed_root = _command_output(root, runner, ["git", "-C", str(root), "rev-parse", "--show-toplevel"], "state_contradiction")
    if Path(observed_root).resolve() != root:
        raise SetupError("state_contradiction", "RepoRoot is not the attached Git root")
    repository = _command_output(root, runner, ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"], "github_capability_missing")
    instruction_files = [name for name in ("CLAUDE.md", "AGENTS.md") if (root / name).is_file()]
    context_files = discover_context_files(root)
    contexts = [path for path in context_files if Path(path).name == "CONTEXT.md"]
    signals = "CONTEXT-MAP.md" in context_files or (root / "pnpm-workspace.yaml").is_file() or len(contexts) > 1
    triage = (root / "docs/agents/triage-labels.md").is_file()
    profile = discover_repository_profile(root)
    return SetupRequest(
        repository=repository,
        repository_profile=profile,
        instruction_file=instruction_files[0] if instruction_files else "AGENTS.md",
        domain_layout="multi-context" if signals else "single-context",
        triage_enabled=triage,
        available_methods=(),
        scientific=_scientific_repository(root) if profile == "scientific-computing" else None,
    )


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


def apply_setup(root: Path, request: SetupRequest, *, write: bool = True) -> dict[str, Any]:
    root = root.resolve()
    instruction_files = [name for name in ("CLAUDE.md", "AGENTS.md") if (root / name).is_file()]
    context_files = discover_context_files(root)
    contexts = [path for path in context_files if Path(path).name == "CONTEXT.md"]
    multi_signals = [name for name in ("CONTEXT-MAP.md", "pnpm-workspace.yaml") if (root / name).is_file()]
    if instruction_files and request.instruction_file != instruction_files[0]:
        raise SetupError("state_contradiction", f"existing instruction preference is {instruction_files[0]}")
    if (multi_signals or len(contexts) > 1) and request.domain_layout != "multi-context":
        raise SetupError("state_contradiction", "repository evidence requires multi-context domain layout")
    scientific = dict(request.scientific or _scientific_repository(root)) if request.repository_profile == "scientific-computing" else None
    observed = {
        "instruction_files": instruction_files,
        "agent_docs": sorted(path.name for path in (root / "docs/agents").glob("*.md")) if (root / "docs/agents").is_dir() else [],
        "context_files": list(context_files),
        "domain_signals": multi_signals,
        "selected_domain_layout": request.domain_layout,
        "repository_profile": request.repository_profile,
        "scientific_repository": scientific,
        "reported_available_methods": list(request.available_methods),
    }
    instruction = root / request.instruction_file
    original = instruction.read_text(encoding="utf-8") if instruction.is_file() else ""
    triage = "\n\n### Triage labels\n\nMatt triage roles map to descriptive labels only. See `docs/agents/triage-labels.md`." if request.triage_enabled else ""
    configured = _replace_agent_skills(
        _set_repository_profile(original, request.repository_profile),
        _template("agent-skills.md", triage=triage, profile=request.repository_profile),
    )
    outputs = {
        instruction: configured,
        root / "docs/agents/issue-tracker.md": _template(
            "issue-tracker.md", repository=request.repository, profile=request.repository_profile
        ),
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
    science_path = root / "docs/agents/scientific-computing.md"
    science_current = science_path.read_text(encoding="utf-8") if science_path.is_file() else ""
    science_block = None
    if scientific:
        science_block = _template(
            "scientific-computing.md",
            benchmark_roots=_markdown_list(scientific["benchmark_roots"], "No benchmark root discovered; define one before publishing durable cases."),
            research_roots=_markdown_list(scientific["research_roots"], "No research workspace discovered; use repository-approved locations."),
            data_roots=_markdown_list(scientific["canonical_data_roots"], "No canonical data root discovered; identify source locations per claim."),
            publication_locks=_markdown_list(scientific["publication_locks"], "No locked publication or validated-release artifacts discovered."),
            validation_commands=_markdown_list(scientific["validation_commands"], "No repository validation command discovered; record exact commands in each evidence packet."),
            experimental_roots=_markdown_list(scientific["experimental_artifact_roots"], "No experimental artifact root discovered; use repository-approved temporary locations."),
            tolerance_policy=scientific["tolerance_policy"],
            compatibility_policy=scientific["compatibility_policy"],
            history_policy="yes" if scientific["git_history_preserves_retired_science"] else "no",
        )
    science_output = _managed(science_current, science_block)
    outputs[science_path] = science_output if science_output.strip() else None
    changed = [path.relative_to(root).as_posix() for path, text in outputs.items() if (
        (path.read_text(encoding="utf-8") if path.is_file() else None) != text
    )]
    if write:
        changed = _commit(root, outputs)
    return {
        "changed": bool(changed),
        "changed_paths": changed,
        "applied": write,
        "instruction_file": request.instruction_file,
        "repository_profile": request.repository_profile,
        "method_routes": all_method_routes(request.available_methods),
        "evidence": observed,
    }
