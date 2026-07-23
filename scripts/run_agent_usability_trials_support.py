"""Codex output contracts and observed metrics for installed-product trials."""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from pathlib import Path
import re
import shlex
import subprocess

WORKER_SCHEMA = {
    "type": "object",
    "required": ["observed_outcome", "friction", "blocker", "source_urls", "observed_skill_root", "claim"],
    "properties": {
        "observed_outcome": {"enum": ["pass", "blocked", "fail"]},
        "friction": {"type": "integer", "minimum": 1, "maximum": 5},
        "blocker": {"type": ["string", "null"]},
        "source_urls": {"type": "array", "items": {"type": "string"}},
        "observed_skill_root": {"type": "string"},
        "claim": {
            "type": "object",
            "required": ["summary"],
            "properties": {"summary": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}
VERIFIER_SCHEMA = {
    "type": "object",
    "required": ["decision", "reason"],
    "properties": {
        "decision": {"enum": ["pass", "blocked", "reject"]},
        "reason": {"type": "string"},
    },
    "additionalProperties": False,
}
_MUTATING_TOOL = re.compile(r"(?:^|[._:-])(?:create|update|edit|delete|remove|close|reopen|merge|push|publish|send)(?:[._:-]|$)", re.I)
_TOOL_TYPES = {"command_execution", "file_change", "mcp_tool_call", "request_user_input", "web_search"}
def build_worker_prompt(template: str, plugin_root: Path, output_path: str) -> str:
    return template.replace("{{PLUGIN_ROOT}}", str(plugin_root)) + f"\n\nCopied fixture files other than `{output_path}` are immutable inputs; preserve them unchanged.\n\nThe installed skill root is `{plugin_root}`. Inspect its manifest and report this exact path as `observed_skill_root`. Return the requested structured result; do not read any Project Truss source checkout."
def _initialize_trial_repository(project: Path) -> None:
    for command in (["git", "init", "-q"], ["git", "add", "."], ["git", "-c", "user.name=Project Truss Trial", "-c", "user.email=trial@example.com", "commit", "-qm", "fixture"]):
        result = subprocess.run(command, cwd=project, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(f"could not initialize trial Git repository: {result.stderr.strip() or result.returncode}")


def _tool_name(item: Mapping[str, object]) -> str:
    kind = str(item.get("type") or "")
    if kind == "mcp_tool_call":
        server = str(item.get("server") or "mcp")
        tool = str(item.get("tool") or item.get("name") or "unknown")
        return f"{server}.{tool}"
    return kind


def _mutates_externally(command: str) -> bool:
    try:
        words = shlex.split(command)
        if words and Path(words[0]).name in {"bash", "sh", "zsh"}:
            option = next((index for index, word in enumerate(words) if word.startswith("-") and "c" in word), -1)
            command = words[option + 1] if 0 <= option < len(words) - 1 else command
        lexer = shlex.shlex(command.replace("\n", ";"), posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        groups: list[list[str]] = [[]]
        for word in lexer:
            if word and all(char in ";&|" for char in word):
                groups.append([])
            else:
                groups[-1].append(word)
    except ValueError:
        return False
    for words in groups:
        while words and (words[0] in {"!", "command", "do", "elif", "else", "env", "if", "nohup", "sudo", "then", "time", "until", "while"} or re.match(r"^[A-Za-z_]\w*=", words[0])):
            words.pop(0)
        if not words:
            continue
        executable = Path(words[0]).name.lower()
        args = [word.lower() for word in words[1:]]
        if executable == "git" and args[:1] == ["push"]:
            return True
        if executable == "codex" and args[:2] in (["plugin", "add"], ["plugin", "remove"]):
            return True
        if executable == "gh" and len(args) >= 2:
            if args[:2] in (["repo", "rename"],) or (args[0] == "issue" and args[1] in {"create", "edit", "close", "reopen"}) or (args[0] == "pr" and args[1] in {"create", "merge", "close", "reopen"}):
                return True
            if args[0] == "api" and any(method in args for method in {"post", "put", "patch", "delete"}):
                return True
        if executable in {"curl", "wget"} and any(method in args for method in {"post", "put", "patch", "delete"}):
            return True
    return False


def summarize_observed_events(events: Sequence[Mapping[str, object]]) -> dict[str, object]:
    tool_calls: list[str] = []
    user_input_calls = 0
    external_mutations = 0
    for event in events:
        if event.get("type") != "item.completed":
            continue
        item = event.get("item")
        if not isinstance(item, Mapping):
            continue
        kind = str(item.get("type") or "")
        if kind == "error" and "request_user_input is not supported in exec mode" in str(item.get("message") or ""):
            tool_calls.append("request_user_input")
            user_input_calls += 1
            continue
        if kind not in _TOOL_TYPES:
            continue
        name = _tool_name(item)
        tool_calls.append(name)
        if kind == "request_user_input" or "request_user_input" in name:
            user_input_calls += 1
        command = item.get("command")
        command_text = " ".join(map(str, command)) if isinstance(command, Sequence) and not isinstance(command, str) else str(command or "")
        if (kind == "command_execution" and _mutates_externally(command_text)) or (kind == "mcp_tool_call" and _MUTATING_TOOL.search(name)):
            external_mutations += 1
    return {"tool_calls": tool_calls, "user_input_calls": user_input_calls, "external_mutations": external_mutations}
