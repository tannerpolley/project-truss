"""Project Truss lifecycle and workspace handlers."""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
from typing import Any

try:
    from ..command_support import Context, ScriptError, arg_value, emit, project_root_for, read_json_arg, resolve_under
    from ..truss_github import GitHubClient, load_fixture
    from ..truss_policy import BLOCKERS, FinalHealth, WorkRequest, closeout_findings, derive_digest, load_contract, plan_work
    from ..workspace_isolation import resolve_workspace_isolation
except ImportError:
    from command_support import Context, ScriptError, arg_value, emit, project_root_for, read_json_arg, resolve_under
    from truss_github import GitHubClient, load_fixture
    from truss_policy import BLOCKERS, FinalHealth, WorkRequest, closeout_findings, derive_digest, load_contract, plan_work
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


def _implementation_artifact_history(root: Path, base: str) -> tuple[str, ...]:
    if not base:
        return ()
    if re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", base) is None:
        raise ScriptError("ImplementationBase must be a full Git commit hash")
    result = subprocess.run(
        ["git", "log", "--format=", "--name-only", f"{base}..HEAD", "--", *_SUPERPOWERS_WORKING_DIRS],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise ScriptError(f"could not inspect implementation artifact history: {result.stderr.strip()}")
    return tuple(sorted({line.strip() for line in result.stdout.splitlines() if line.strip()}))


def _with_blocker(blockers: list[str], added: str) -> list[str]:
    selected = {*blockers, added}
    trailing = [value for value in blockers if value not in BLOCKERS]
    return [value for value in BLOCKERS if value in selected] + trailing


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
        implementation_base = str(arg_value(args, "ImplementationBase", default=""))
        code_leaf_started = not snapshot.children and bool(
            snapshot.assignees or snapshot.closing_prs or snapshot.issue.state == "CLOSED"
        )
        if code_leaf_started and not implementation_base:
            raise ScriptError("ImplementationBase is required after claim or implementation starts")
        payload = {"ok": True, "action": action, **derive_digest(snapshot).to_dict()}
        artifacts = _unretired_working_artifacts(root)
        history = _implementation_artifact_history(root, implementation_base)
        payload["unretired_artifacts"] = list(artifacts)
        payload["implementation_artifact_history"] = list(history)
        if artifacts or history:
            payload["ready_frontier"] = []
            payload["blockers_or_decisions"] = _with_blocker(payload["blockers_or_decisions"], "integration_unhealthy")
            if not snapshot.authoritative:
                payload["next_safe_action"] = (
                    "Re-read live GitHub and verify the issue contract before retiring any listed "
                    "Superpowers working artifact."
                )
            elif history:
                payload["next_safe_action"] = (
                    "Recreate the implementation branch from its verified base without Superpowers "
                    "working-artifact commits."
                )
            else:
                payload["next_safe_action"] = (
                    "Verify the GitHub issue contract, then retire the listed Superpowers working artifacts "
                    "before claim or implementation."
                )
        return emit(payload)
    if action == "Closeout":
        if snapshot_arg:
            raise ScriptError("Closeout does not accept SnapshotPath")
        snapshot = GitHubClient().snapshot(repository, issue)
        implementation_base = str(arg_value(args, "ImplementationBase", default=""))
        if not snapshot.children and not implementation_base:
            raise ScriptError("ImplementationBase is required for code-leaf Closeout")
        health, _ = read_json_arg(root, args, "HealthJson", "HealthPath")
        final_health = FinalHealth.from_mapping(health)
        artifacts = _unretired_working_artifacts(root)
        history = _implementation_artifact_history(root, implementation_base)
        effective_health = FinalHealth(
            final_health.verification_passed,
            final_health.integration_healthy and not artifacts and not history,
            final_health.source_clean,
            final_health.head_sha,
        )
        findings = closeout_findings(snapshot, effective_health)
        payload = {
            "ok": not findings,
            "action": action,
            "source": "live",
            "findings": list(findings),
            "unretired_artifacts": list(artifacts),
            "implementation_artifact_history": list(history),
        }
        return emit(payload, 0 if not findings else 1)
    raise ScriptError("Action must be Plan, Status, or Closeout")


HANDLERS = {
    "command_project_truss": command_project_truss,
    "command_workspace_isolation": command_workspace_isolation,
}
