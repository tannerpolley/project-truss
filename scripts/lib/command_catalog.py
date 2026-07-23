"""Typed ownership catalog for the compact Project Truss launchers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class ScriptError(Exception):
    pass


_COMMANDS: dict[str, str] = {
    "scripts/get-agent-plugin-version.sh": "command_get_agent_plugin_version",
    "scripts/install.sh": "command_install",
    "scripts/prepare-release.sh": "command_prepare_release",
    "scripts/project-truss.sh": "command_project_truss",
    "scripts/run-agent-usability-trials.sh": "command_run_agent_usability_trials",
    "scripts/sync-live.sh": "command_sync_live",
    "scripts/validate-agent-usability-receipt.sh": "command_validate_agent_usability_receipt",
    "scripts/validate-plan-outcome-proof.sh": "command_validate_plan_outcome_proof",
    "scripts/validate-plan-task-use-cases.sh": "command_validate_plan_task_use_cases",
    "scripts/validate-skill-metadata-contract.sh": "command_validate_skill_metadata_contract",
    "scripts/validate.sh": "command_validate",
    "scripts/workspace-isolation.sh": "command_workspace_isolation",
}


@dataclass(frozen=True)
class CommandSpec:
    path: str
    handler: str
    kind: str
    mutation: str


def _kind(path: str) -> str:
    name = Path(path).name
    if name.startswith("validate-") or name == "validate.sh":
        return "validator"
    if name in {"get-agent-plugin-version.sh", "install.sh", "prepare-release.sh", "sync-live.sh"}:
        return "distribution"
    return "project"


def _mutation(handler: str) -> str:
    if handler in {"command_install", "command_sync_live"}:
        return "deployment"
    if handler == "command_run_agent_usability_trials":
        return "project"
    if handler == "command_project_truss":
        return "external"
    return "none"


def load_command_catalog(plugin_root: Path) -> dict[str, CommandSpec]:
    discovered = {
        path.relative_to(plugin_root).as_posix()
        for base in (plugin_root / "scripts", plugin_root / "skills")
        for path in base.rglob("*.sh")
        if "/lib/" not in path.relative_to(plugin_root).as_posix()
        and path.relative_to(plugin_root).as_posix() != "scripts/lib/run-script.sh"
    }
    configured = set(_COMMANDS)
    if configured != discovered:
        raise ScriptError(
            f"command catalog drift: missing={sorted(discovered - configured)}, extra={sorted(configured - discovered)}"
        )
    return {
        path: CommandSpec(path=path, handler=handler, kind=_kind(path), mutation=_mutation(handler))
        for path, handler in _COMMANDS.items()
    }


def build_command_registry(plugin_root: Path) -> dict[str, str]:
    return {path: spec.handler for path, spec in load_command_catalog(plugin_root).items()}


def resolve_command(script_rel: str, plugin_root: Path) -> str:
    spec = load_command_catalog(plugin_root).get(script_rel)
    if spec is None:
        raise ScriptError(f"unregistered script path: {script_rel}")
    return spec.handler
