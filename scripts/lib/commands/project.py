"""Project Truss lifecycle and workspace handlers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from ..command_support import Context, ScriptError, arg_value, emit, project_root_for, read_json_arg, resolve_under
    from ..truss_github import GitHubClient, load_fixture
    from ..truss_policy import FinalHealth, WorkRequest, closeout_findings, derive_digest, load_contract, plan_work
    from ..workspace_isolation import resolve_workspace_isolation
except ImportError:
    from command_support import Context, ScriptError, arg_value, emit, project_root_for, read_json_arg, resolve_under
    from truss_github import GitHubClient, load_fixture
    from truss_policy import FinalHealth, WorkRequest, closeout_findings, derive_digest, load_contract, plan_work
    from workspace_isolation import resolve_workspace_isolation


_SUPERPOWERS_WORKING_DIRS = ("docs/superpowers/specs", "docs/superpowers/plans")


def _unretired_working_artifacts(root: Path) -> tuple[str, ...]:
    artifacts = []
    for relative in _SUPERPOWERS_WORKING_DIRS:
        directory = root / relative
        if directory.is_symlink():
            artifacts.append(relative)
        elif directory.is_dir():
            artifacts.extend(path.relative_to(root).as_posix() for path in directory.rglob("*") if path.is_file() or path.is_symlink())
        elif directory.exists():
            artifacts.append(relative)
    return tuple(sorted(artifacts))


def command_workspace_isolation(ctx: Context, args: dict[str, Any]) -> int:
    root = project_root_for(ctx, args)
    request, _ = read_json_arg(root, args, "RequestJson", "RequestPath")
    capabilities, _ = read_json_arg(root, args, "CapabilitiesJson", "CapabilitiesPath")
    if not isinstance(request, dict) or not isinstance(capabilities, dict):
        raise ValueError("workspace isolation request and capabilities must be JSON objects")
    decision = resolve_workspace_isolation(request, capabilities)
    return emit({"ok": True, "phase": "workspace-isolation-decision", "untrusted_request": True, "decision": decision})


def command_project_truss(ctx: Context, args: dict[str, Any]) -> int:
    load_contract(ctx.repo_root / "docs" / "project-truss" / "contract.yml")
    root = project_root_for(ctx, args)
    action = str(arg_value(args, "Action", default="")).title()
    if action == "Plan":
        request, _ = read_json_arg(root, args, "RequestJson", "RequestPath", required=False)
        result = plan_work(WorkRequest.from_mapping(request or {})).to_dict()
        return emit({"ok": True, "action": action, "source": "policy", **result})
    repository = str(arg_value(args, "Repository", default=""))
    issue_value = arg_value(args, "Issue")
    if not repository or issue_value in (None, ""):
        raise ScriptError("Repository and Issue are required")
    try:
        issue = int(issue_value)
    except (TypeError, ValueError) as exc:
        raise ScriptError("Issue must be a positive integer") from exc
    snapshot_arg = arg_value(args, "SnapshotPath")
    if action == "Status":
        snapshot = load_fixture(resolve_under(root, str(snapshot_arg), "SnapshotPath")) if snapshot_arg else GitHubClient().snapshot(repository, issue)
        return emit({"ok": True, "action": action, **derive_digest(snapshot).to_dict()})
    if action == "Closeout":
        if snapshot_arg:
            raise ScriptError("Closeout does not accept SnapshotPath")
        health, _ = read_json_arg(root, args, "HealthJson", "HealthPath")
        final_health = FinalHealth.from_mapping(health)
        artifacts = _unretired_working_artifacts(root)
        effective_health = FinalHealth(
            final_health.verification_passed,
            final_health.integration_healthy and not artifacts,
            final_health.source_clean,
            final_health.head_sha,
        )
        findings = closeout_findings(GitHubClient().snapshot(repository, issue), effective_health)
        payload = {"ok": not findings, "action": action, "source": "live", "findings": list(findings), "unretired_artifacts": list(artifacts)}
        return emit(payload, 0 if not findings else 1)
    raise ScriptError("Action must be Plan, Status, or Closeout")


HANDLERS = {
    "command_project_truss": command_project_truss,
    "command_workspace_isolation": command_workspace_isolation,
}
