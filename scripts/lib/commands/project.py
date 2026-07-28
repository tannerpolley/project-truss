"""Project Truss lifecycle and workspace handlers."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

try:
    from ..command_support import Context, ScriptError, arg_value, emit, project_root_for, read_json_arg, resolve_under
    from ..git_lifecycle import (
        CleanupRequest, GitLifecycleError, GitSyncResult, cleanup_merged_outcome,
        synchronize_default, validate_preparation,
    )
    from ..truss_github import GitHubClient, ProjectProjection, load_fixture
    from ..truss_setup import SetupError, SetupRequest, apply_setup, validate_setup_target
    from ..truss_policy import (
        FinalHealth,
        ResolutionReceipt,
        WorkRequest,
        close_resolution_findings,
        closeout_findings,
        derive_digest,
        load_contract,
        plan_resolution,
        plan_work,
    )
    from ..workspace_isolation import resolve_workspace_isolation
except ImportError:
    from command_support import Context, ScriptError, arg_value, emit, project_root_for, read_json_arg, resolve_under
    from git_lifecycle import (
        CleanupRequest, GitLifecycleError, GitSyncResult, cleanup_merged_outcome,
        synchronize_default, validate_preparation,
    )
    from truss_github import GitHubClient, ProjectProjection, load_fixture
    from truss_setup import SetupError, SetupRequest, apply_setup, validate_setup_target
    from truss_policy import (
        FinalHealth,
        ResolutionReceipt,
        WorkRequest,
        close_resolution_findings,
        closeout_findings,
        derive_digest,
        load_contract,
        plan_resolution,
        plan_work,
    )
    from workspace_isolation import resolve_workspace_isolation


def _validate_implementation_base(root, base: str) -> None:
    if re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", base) is None:
        raise ScriptError("ImplementationBase must be a full Git commit hash")
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", base, "HEAD"],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=15,
    )
    if result.returncode == 1:
        raise ScriptError("ImplementationBase is not an ancestor of the current HEAD")
    if result.returncode != 0:
        detail = result.stderr.strip() or "git merge-base failed"
        raise ScriptError(f"could not validate ImplementationBase: {detail}")


def _validate_resolution_workspace(root: Path, receipt: ResolutionReceipt) -> None:
    branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=root, text=True, capture_output=True, timeout=15,
    )
    top = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=root, text=True, capture_output=True, timeout=15,
    )
    if branch.returncode or top.returncode:
        raise ScriptError("could not validate resolution workspace")
    worktree = Path(top.stdout.strip()).resolve()
    if branch.stdout.strip() != receipt.branch:
        raise ScriptError("resolution branch does not match the current branch")
    if Path(receipt.worktree).resolve() != worktree:
        raise ScriptError("resolution worktree does not match the current worktree")


def _load_resolution(
    root: Path,
    args: dict[str, Any],
    issue: int,
    *,
    require_active_workspace: bool = True,
) -> ResolutionReceipt:
    resolution, _ = read_json_arg(root, args, "ResolutionJson", "ResolutionPath")
    if not isinstance(resolution, dict):
        raise ValueError("resolution must be a JSON object")
    values = dict(resolution)
    values.setdefault("issues", [issue])
    receipt = ResolutionReceipt.from_mapping(values)
    supplied = str(arg_value(args, "ImplementationBase", default=""))
    if supplied and supplied != receipt.implementation_base:
        raise ScriptError("ImplementationBase conflicts with the resolution receipt")
    _validate_implementation_base(root, receipt.implementation_base)
    if require_active_workspace:
        _validate_resolution_workspace(root, receipt)
    return receipt


def _validate_prepared_resolution(
    root: Path, args: dict[str, Any], receipt: ResolutionReceipt
) -> None:
    preparation, _ = read_json_arg(
        root, args, "PreparationJson", "PreparationPath"
    )
    prepared = GitSyncResult.from_mapping(preparation)
    if prepared.implementation_base != receipt.implementation_base:
        raise ScriptError(
            "Preparation implementation base conflicts with the resolution receipt"
        )
    try:
        validate_preparation(prepared, root, active_branch=receipt.branch)
    except GitLifecycleError as exc:
        raise ScriptError(f"{exc.blocker}: {exc}") from exc


def _require_attached_cwd(ctx: Context, root: Path, action: str) -> None:
    invocation_cwd = (ctx.invocation_cwd or Path.cwd()).resolve()
    if invocation_cwd != root.resolve():
        raise ScriptError(
            f"{action} invocation cwd does not match the task-visible worktree"
        )


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
    if action == "Setup":
        _require_attached_cwd(ctx, root, action)
        setup, _ = read_json_arg(root, args, "SetupJson", "SetupPath")
        request = SetupRequest.from_mapping(setup)
        try:
            evidence = validate_setup_target(root, request.repository)
            result = apply_setup(root, request)
        except SetupError as exc:
            raise ScriptError(str(exc)) from exc
        result["evidence"] = {**evidence, **result["evidence"]}
        return emit({"ok": True, "action": action, "source": "local", **result})
    if action == "Project":
        projection, _ = read_json_arg(root, args, "ProjectionJson", "ProjectionPath")
        result = GitHubClient().project_membership(ProjectProjection.from_mapping(projection))
        return emit({"ok": True, "action": action, "source": "live", **result})
    if action == "Prepare":
        _require_attached_cwd(ctx, root, action)
        try:
            result = synchronize_default(root)
        except GitLifecycleError as exc:
            raise ScriptError(f"{exc.blocker}: {exc}") from exc
        return emit({"ok": True, "action": action, "source": "live", **result.to_dict()})
    repository = str(arg_value(args, "Repository", default=""))
    if action == "Cleanup":
        _require_attached_cwd(ctx, root, action)
        if not repository:
            raise ScriptError("Repository is required")
        cleanup, _ = read_json_arg(root, args, "CleanupJson", "CleanupPath")
        try:
            request = CleanupRequest.from_mapping(cleanup)
            result = cleanup_merged_outcome(root, repository, request)
        except GitLifecycleError as exc:
            raise ScriptError(f"{exc.blocker}: {exc}") from exc
        return emit({"ok": True, "action": action, "source": "live", **result})
    issue_value = arg_value(args, "Issue")
    if not repository or issue_value in (None, ""):
        raise ScriptError("Repository and Issue are required")
    try:
        issue = int(issue_value)
    except (TypeError, ValueError) as exc:
        raise ScriptError("Issue must be a positive integer") from exc
    if action == "Resolve":
        _require_attached_cwd(ctx, root, "resolution")
        require_recorded_value = str(arg_value(args, "RequireRecorded", default="false")).casefold()
        if require_recorded_value not in {"true", "false"}:
            raise ScriptError("RequireRecorded must be true or false")
        receipt = _load_resolution(root, args, issue)
        if require_recorded_value == "false":
            _validate_prepared_resolution(root, args, receipt)
        github = GitHubClient()
        snapshots = [github.snapshot(repository, number) for number in receipt.issues]
        result = plan_resolution(
            snapshots,
            receipt,
            require_recorded=require_recorded_value == "true",
        )
        return emit(
            {"ok": result.eligible, "action": action, "source": "live", **result.to_dict()},
            0 if result.eligible else 1,
        )
    snapshot_arg = arg_value(args, "SnapshotPath")
    if action == "Status":
        snapshot = load_fixture(resolve_under(root, str(snapshot_arg), "SnapshotPath")) if snapshot_arg else GitHubClient().snapshot(repository, issue)
        implementation_base = str(arg_value(args, "ImplementationBase", default=""))
        code_leaf_started = not snapshot.children and bool(
            snapshot.assignees or snapshot.closing_prs or snapshot.issue.state == "CLOSED"
        )
        if code_leaf_started and not implementation_base:
            raise ScriptError("ImplementationBase is required after claim or implementation starts")
        if implementation_base:
            _validate_implementation_base(root, implementation_base)
        payload = {"ok": True, "action": action, **derive_digest(snapshot).to_dict()}
        return emit(payload)
    if action == "Closeout":
        if snapshot_arg:
            raise ScriptError("Closeout does not accept SnapshotPath")
        resolution_supplied = arg_value(args, "ResolutionJson") or arg_value(args, "ResolutionPath")
        if resolution_supplied:
            receipt = _load_resolution(
                root, args, issue, require_active_workspace=False
            )
            health, _ = read_json_arg(root, args, "HealthJson", "HealthPath")
            github = GitHubClient()
            snapshots = [github.snapshot(repository, number) for number in receipt.issues]
            findings = close_resolution_findings(snapshots, receipt, FinalHealth.from_mapping(health))
            payload = {"ok": not findings, "action": action, "source": "live",
                       "issues": list(receipt.issues), "findings": list(findings),
                       "receipt": receipt.to_dict()}
            return emit(payload, 0 if not findings else 1)
        snapshot = GitHubClient().snapshot(repository, issue)
        if not snapshot.children:
            raise ScriptError("ResolutionJson is required for code-leaf Closeout")
        implementation_base = str(arg_value(args, "ImplementationBase", default=""))
        if implementation_base:
            _validate_implementation_base(root, implementation_base)
        health, _ = read_json_arg(root, args, "HealthJson", "HealthPath")
        final_health = FinalHealth.from_mapping(health)
        findings = closeout_findings(snapshot, final_health)
        payload = {
            "ok": not findings,
            "action": action,
            "source": "live",
            "findings": list(findings),
        }
        return emit(payload, 0 if not findings else 1)
    raise ScriptError(
        "Action must be Plan, Setup, Prepare, Project, Resolve, Status, Closeout, or Cleanup"
    )


HANDLERS = {
    "command_project_truss": command_project_truss,
    "command_workspace_isolation": command_workspace_isolation,
}
