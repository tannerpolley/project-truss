"""Project Truss lifecycle and workspace handlers."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

try:
    from ..command_support import Context, ScriptError, arg_value, emit, has_switch, project_root_for, read_json_arg, resolve_under
    from ..git_lifecycle import (
        CleanupRequest, GitLifecycleError, GitSyncResult, cleanup_merged_outcome,
        synchronize_default, validate_preparation,
    )
    from ..truss_github import GitHubClient, GitHubObservationError, ProjectProjection, load_fixture
    from ..truss_setup import SetupError, SetupRequest, apply_setup, discover_context_files, discover_setup_request, validate_setup_target
    from ..truss_policy import (
        FinalHealth,
        ResolutionReceipt,
        WorkRequest,
        close_resolution_findings,
        closeout_findings,
        derive_digest,
        load_contract,
        parse_issue_contract,
        plan_resolution,
        plan_work,
    )
    from ..workspace_isolation import build_workspace_receipt, resolve_workspace_isolation, validate_workspace_receipt
except ImportError:
    from command_support import Context, ScriptError, arg_value, emit, has_switch, project_root_for, read_json_arg, resolve_under
    from git_lifecycle import (
        CleanupRequest, GitLifecycleError, GitSyncResult, cleanup_merged_outcome,
        synchronize_default, validate_preparation,
    )
    from truss_github import GitHubClient, GitHubObservationError, ProjectProjection, load_fixture
    from truss_setup import SetupError, SetupRequest, apply_setup, discover_context_files, discover_setup_request, validate_setup_target
    from truss_policy import (
        FinalHealth,
        ResolutionReceipt,
        WorkRequest,
        close_resolution_findings,
        closeout_findings,
        derive_digest,
        load_contract,
        parse_issue_contract,
        plan_resolution,
        plan_work,
    )
    from workspace_isolation import build_workspace_receipt, resolve_workspace_isolation, validate_workspace_receipt


def _validate_implementation_base(root, base: str) -> None:
    if re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", base) is None:
        raise ScriptError("ImplementationBase must be a full Git commit hash")
    result = subprocess.run(["git", "merge-base", "--is-ancestor", base, "HEAD"], cwd=root, text=True, capture_output=True, timeout=15)
    if result.returncode == 1:
        raise ScriptError("ImplementationBase is not an ancestor of the current HEAD")
    if result.returncode != 0:
        detail = result.stderr.strip() or "git merge-base failed"
        raise ScriptError(f"could not validate ImplementationBase: {detail}")


def _validate_resolution_workspace(root: Path, receipt: ResolutionReceipt) -> None:
    try:
        branch, worktree = _git_text(root, "branch", "--show-current"), Path(_git_text(root, "rev-parse", "--show-toplevel")).resolve()
    except ScriptError as exc:
        raise ScriptError("could not validate resolution workspace") from exc
    if branch != receipt.branch:
        raise ScriptError("resolution branch does not match the current branch")
    if worktree != Path(receipt.worktree).resolve():
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
    receipt = ResolutionReceipt.from_mapping({"issues": [issue], **resolution})
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
    preparation, _ = read_json_arg(root, args, "PreparationJson", "PreparationPath")
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
        raise ScriptError(f"{action} invocation cwd does not match the task-visible worktree")


def _git_text(root: Path, *command: str) -> str:
    result = subprocess.run(["git", *command], cwd=root, text=True, capture_output=True, timeout=15)
    if result.returncode:
        raise ScriptError(result.stderr.strip() or f"git {' '.join(command)} failed")
    return result.stdout.strip()


def _inferred_resolution(root: Path, args: dict[str, Any], issue: int, github: GitHubClient) -> ResolutionReceipt:
    raw_issues = arg_value(args, "Issues", "IssueSet", default="")
    if isinstance(raw_issues, list):
        numbers = [int(value) for value in raw_issues]
    elif raw_issues:
        numbers = [int(value.strip()) for value in str(raw_issues).split(",") if value.strip()]
    else:
        numbers = [issue]
    owner = str(arg_value(args, "Owner", default="")).strip() or github.current_user()
    branch = str(arg_value(args, "Branch", default="")).strip() or _git_text(root, "branch", "--show-current")
    if not branch:
        raise ScriptError("Claim requires a branch-bound checkout")
    worktree = str(arg_value(args, "Worktree", default="")).strip() or _git_text(root, "rev-parse", "--show-toplevel")
    base = str(arg_value(args, "ImplementationBase", default="")).strip() or _git_text(root, "rev-parse", "HEAD")
    pull_request = arg_value(args, "PullRequest")
    if pull_request not in (None, ""):
        pull_request = int(pull_request)
    return ResolutionReceipt.from_mapping({"issues": numbers, "owner": owner, "implementation_base": base,
                                           "branch": branch, "worktree": worktree, "pull_request": pull_request})


def _auto_health(root: Path, snapshots: list[Any], receipt: ResolutionReceipt | None = None) -> FinalHealth:
    contracts = [parse_issue_contract(snapshot.issue.body) for snapshot in snapshots]
    prs = [pr for snapshot in snapshots for pr in snapshot.closing_prs]
    if receipt and receipt.pull_request is not None:
        prs = [pr for pr in prs if pr.number == receipt.pull_request]
    merged = [pr for pr in prs if pr.merged and pr.state == "MERGED"]
    review_passed = bool(merged) and all(pr.review_decision not in {"CHANGES_REQUESTED", "REVIEW_REQUIRED"} for pr in merged)
    verification_passed = all(contract.acceptance_complete for contract in contracts)
    integration_healthy = all(not snapshot.provider_findings and not any(item.state != "CLOSED" for item in snapshot.blocked_by) for snapshot in snapshots)
    source_clean = not _git_text(root, "status", "--porcelain")
    head_sha = merged[0].head_sha if len(merged) == 1 else ""
    return FinalHealth(verification_passed, integration_healthy, source_clean, head_sha, review_passed)


def _continuation(
    *, next_skill: str = "start", next_action: str = "return to Start and re-read live state",
    blockers: tuple[str, ...] = (), evidence: dict[str, Any] | None = None,
    safe_retry_count: int = 0,
) -> dict[str, Any]:
    return {
        "status": "blocked" if blockers else "continue",
        "next_skill": next_skill,
        "next_action": next_action,
        "blockers": list(blockers),
        "evidence": evidence or {},
        "safe_retry_count": safe_retry_count,
    }


def _stage(
    payload: dict[str, Any], *, next_action: str, blockers: tuple[str, ...] = (),
    evidence: dict[str, Any] | None = None, exit_code: int = 0,
) -> int:
    payload = dict(payload)
    payload["continuation"] = _continuation(
        next_action=next_action, blockers=blockers, evidence=evidence,
    )
    return emit(payload, exit_code)


def command_workspace_isolation(ctx: Context, args: dict[str, Any]) -> int:
    root = project_root_for(ctx, args)
    request, _ = read_json_arg(root, args, "RequestJson", "RequestPath")
    capabilities, _ = read_json_arg(root, args, "CapabilitiesJson", "CapabilitiesPath")
    if not isinstance(request, dict) or not isinstance(capabilities, dict):
        raise ValueError("workspace isolation request and capabilities must be JSON objects")
    decision = resolve_workspace_isolation(request, capabilities)
    payload = {"ok": True, "phase": "workspace-isolation-decision", "untrusted_request": True, "decision": decision}
    observation = capabilities.get("observation") or capabilities.get("workspace_observation")
    if isinstance(observation, dict):
        receipt = build_workspace_receipt(request, decision, observation)
        current_head = observation.get("current_head", receipt.get("observed_head"))
        current_branch = observation.get("current_branch", receipt.get("branch") or "")
        publication = observation.get("publication", False)
        if type(publication) is not bool:
            raise ValueError("workspace observation publication must be boolean")
        expected = {
            field: receipt[field]
            for field in ("provider", "workspace_id", "repository_root", "git_common_dir", "issue_number", "task_id", "thread_id", "owner")
        }
        validate_workspace_receipt(
            receipt, expected, current_head=current_head, current_branch=current_branch,
            publication=publication,
        )
        payload["receipt"] = receipt
        payload["receipt_status"] = "verified"
    else:
        payload["receipt_status"] = "observation_required"
    return emit(payload)


def command_project_truss(ctx: Context, args: dict[str, Any]) -> int:
    load_contract(ctx.repo_root / "docs" / "project-truss" / "contract.yml")
    root = project_root_for(ctx, args)
    raw_action = str(arg_value(args, "Action", default="")).strip().casefold()
    if not raw_action and args.get("_positional"):
        raw_action = str(args["_positional"][0]).strip().casefold()
    action = {
        "start": "Plan", "claim": "Claim", "close": "Closeout", "status": "Status",
        "prepare": "Prepare", "cleanup": "Cleanup", "project": "Project",
        "setup": "Setup", "resolve": "Resolve",
    }.get(raw_action, raw_action.title())
    if action == "Plan":
        request, _ = read_json_arg(root, args, "RequestJson", "RequestPath", required=False)
        request_data = dict(request or {})
        if raw_action == "start":
            request_data.setdefault("explicit", True)
            request_data.setdefault("start_entry", True)
        repository, pull_request = str(arg_value(args, "Repository", default="")), arg_value(args, "PullRequest")
        if bool(repository) != (pull_request not in (None, "")):
            raise ScriptError("Repository and PullRequest must be provided together")
        if repository:
            request_data["start_entry"] = False
        elif request_data.get("start_entry"):
            context_files = discover_context_files(root)
            request_data.update({"context_available": bool(context_files), "context_files": list(context_files)})
        work = WorkRequest.from_mapping(request_data)
        if repository:
            try:
                number = int(pull_request)
            except (TypeError, ValueError) as exc:
                raise ScriptError("PullRequest must be a positive integer") from exc
            if number < 1:
                raise ScriptError("PullRequest must be a positive integer")
            governed = GitHubClient().pull_request_is_governed(repository, number)
            work = WorkRequest.from_mapping({**request_data, "mode": "governed", "merge_or_publication": True}) if governed else WorkRequest()
        result = plan_work(work).to_dict()
        return emit({"ok": True, "action": action, "source": "live" if repository else "policy", **result})
    if action == "Setup":
        _require_attached_cwd(ctx, root, action)
        setup, _ = read_json_arg(root, args, "SetupJson", "SetupPath", required=False)
        request = SetupRequest.from_mapping(setup) if setup is not None else discover_setup_request(root)
        try:
            evidence = validate_setup_target(root, request.repository)
            result = apply_setup(root, request, write=has_switch(args, "Apply"))
        except SetupError as exc:
            raise ScriptError(str(exc)) from exc
        result["evidence"] = {**evidence, **result["evidence"]}
        next_action = "continue with the planned work" if result["applied"] else "rerun Setup with -Apply true after reviewing the draft"
        return _stage({"ok": True, "action": action, "source": "local", "next_skill": "start", "next_action": next_action, **result},
                      next_action=next_action, evidence=result["evidence"])
    if action == "Project":
        projection, _ = read_json_arg(root, args, "ProjectionJson", "ProjectionPath")
        result = GitHubClient().project_membership(ProjectProjection.from_mapping(projection))
        return _stage({"ok": True, "action": action, "source": "live", "next_skill": "start", **result},
                      next_action="continue with the planned work", evidence=result)
    if action == "Prepare":
        _require_attached_cwd(ctx, root, action)
        try:
            result = synchronize_default(root)
        except GitLifecycleError as exc:
            raise ScriptError(f"{exc.blocker}: {exc}") from exc
        result_dict = result.to_dict()
        return _stage({"ok": True, "action": action, "source": "live", "next_skill": "start", **result_dict},
                      next_action="create the feature checkout from implementation_base", evidence=result_dict)
    repository = str(arg_value(args, "Repository", default=""))
    github = GitHubClient()
    if action in {"Claim", "Resolve", "Status", "Closeout", "Cleanup"} and not repository:
        repository = github.repository()
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
        return _stage({"ok": True, "action": action, "source": "live", "next_skill": "start", **result},
                      next_action="return to Start and re-read cleanup state", evidence=result)
    positional = args.get("_positional", [])
    issue_value = arg_value(args, "Issue", default=positional[1] if len(positional) > 1 else None)
    if not repository or issue_value in (None, ""):
        raise ScriptError("Repository and Issue are required")
    try:
        issue = int(issue_value)
    except (TypeError, ValueError) as exc:
        raise ScriptError("Issue must be a positive integer") from exc
    if action == "Claim":
        _require_attached_cwd(ctx, root, "claim")
        resolution_supplied = arg_value(args, "ResolutionJson") or arg_value(args, "ResolutionPath")
        receipt = _load_resolution(root, args, issue) if resolution_supplied else _inferred_resolution(root, args, issue, github)
        try:
            result = github.claim_resolution(repository, receipt)
        except GitHubObservationError as exc:
            raise ScriptError(f"{exc.code}: {exc}") from exc
        return _stage({"ok": True, "action": action, "source": "live", "next_skill": "start", **result},
                      next_action="return to Start and continue from the verified claim", evidence=result)
    if action == "Resolve":
        _require_attached_cwd(ctx, root, "resolution")
        require_recorded_value = str(arg_value(args, "RequireRecorded", default="false")).casefold()
        if require_recorded_value not in {"true", "false"}:
            raise ScriptError("RequireRecorded must be true or false")
        receipt = _load_resolution(root, args, issue)
        if require_recorded_value == "false":
            _validate_prepared_resolution(root, args, receipt)
        snapshots = [github.snapshot(repository, number) for number in receipt.issues]
        result = plan_resolution(
            snapshots,
            receipt,
            require_recorded=require_recorded_value == "true",
        )
        result_dict = result.to_dict()
        return _stage(
            {"ok": result.eligible, "action": action, "source": "live", "next_skill": "start", **result_dict},
            next_action="begin implementation in the attached checkout" if result.eligible else "repair the resolution blockers and retry",
            blockers=tuple(result.blockers), evidence=result_dict, exit_code=0 if result.eligible else 1,
        )
    snapshot_arg = arg_value(args, "SnapshotPath")
    if action == "Status":
        snapshot = load_fixture(resolve_under(root, str(snapshot_arg), "SnapshotPath")) if snapshot_arg else github.snapshot(repository, issue)
        implementation_base = str(arg_value(args, "ImplementationBase", default=""))
        code_leaf_started = not snapshot.children and bool(
            snapshot.assignees or snapshot.closing_prs or snapshot.issue.state == "CLOSED"
        )
        if code_leaf_started and not implementation_base:
            raise ScriptError("ImplementationBase is required after claim or implementation starts")
        if implementation_base:
            _validate_implementation_base(root, implementation_base)
        payload = {"ok": True, "action": action, "next_skill": "start", **derive_digest(snapshot).to_dict()}
        return _stage(payload, next_action="return to Start and continue from this status", evidence=payload)
    if action == "Closeout":
        if snapshot_arg:
            raise ScriptError("Closeout does not accept SnapshotPath")
        resolution_supplied = arg_value(args, "ResolutionJson") or arg_value(args, "ResolutionPath")
        if resolution_supplied:
            receipt = _load_resolution(
                root, args, issue, require_active_workspace=False
            )
            snapshots = [github.snapshot(repository, number) for number in receipt.issues]
            health, _ = read_json_arg(root, args, "HealthJson", "HealthPath", required=False)
            final_health = _auto_health(root, snapshots, receipt) if has_switch(args, "AutoHealth") or health is None else FinalHealth.from_mapping(health)
            findings = close_resolution_findings(snapshots, receipt, final_health)
            payload = {"ok": not findings, "action": action, "source": "live", "next_skill": "start",
                       "issues": list(receipt.issues), "findings": list(findings),
                       "receipt": receipt.to_dict(), "health": final_health.__dict__}
            return _stage(
                payload,
                next_action="run Cleanup after the merged PR and deleted head are confirmed" if not findings else "repair the closeout findings and retry",
                blockers=tuple(findings), evidence={"health": final_health.__dict__}, exit_code=0 if not findings else 1,
            )
        snapshot = github.snapshot(repository, issue)
        if not snapshot.children:
            raise ScriptError("ResolutionJson is required for code-leaf Closeout")
        implementation_base = str(arg_value(args, "ImplementationBase", default=""))
        if implementation_base:
            _validate_implementation_base(root, implementation_base)
        health, _ = read_json_arg(root, args, "HealthJson", "HealthPath", required=False)
        final_health = _auto_health(root, [snapshot]) if has_switch(args, "AutoHealth") or health is None else FinalHealth.from_mapping(health)
        findings = closeout_findings(snapshot, final_health)
        payload = {
            "ok": not findings,
            "action": action,
            "source": "live",
            "next_skill": "start",
            "findings": list(findings),
            "health": final_health.__dict__,
        }
        return _stage(
            payload,
            next_action="run Cleanup after the merged PR and deleted head are confirmed" if not findings else "repair the closeout findings and retry",
            blockers=tuple(findings), evidence={"health": final_health.__dict__}, exit_code=0 if not findings else 1,
        )
    raise ScriptError(
        "Action must be Plan, Setup, Prepare, Project, Claim, Resolve, Status, Closeout, or Cleanup"
    )


HANDLERS = {
    "command_project_truss": command_project_truss,
    "command_workspace_isolation": command_workspace_isolation,
}
