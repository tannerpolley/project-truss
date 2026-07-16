"""Hidden-worktree selection and observation checks for one Project Truss leaf."""
from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any


class WorkspaceIsolationError(ValueError):
    pass


_REQUEST_FIELDS = {"requirement", "repository_identity", "issue_number"}
_REQUIREMENTS = {"none", "preferred", "required"}
_RECEIPT_FIELDS = {
    "schema_version", "provider", "workspace_id", "repository_root", "git_common_dir", "issue_number",
    "task_id", "thread_id", "observed_head", "head_mode", "branch", "owner", "disposition",
}
_OWNERS = {"codex_managed_worktree": {"codex_app"}, "local_git_worktree": {"plugin", "user"}}


def _text(data: Mapping[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise WorkspaceIsolationError(f"missing required field: {field}")
    return value.strip()


def _issue(data: Mapping[str, Any]) -> int:
    value = data.get("issue_number")
    if type(value) is not int or value <= 0:
        raise WorkspaceIsolationError("issue_number must be a positive integer")
    return value


def resolve_workspace_isolation(request: Mapping[str, Any], capabilities: Mapping[str, Any]) -> dict[str, Any]:
    unsupported = sorted(set(request) - _REQUEST_FIELDS)
    if unsupported:
        raise WorkspaceIsolationError("unsupported request fields: " + ", ".join(unsupported))
    requirement = _text(request, "requirement")
    repository = _text(request, "repository_identity")
    issue_number = _issue(request)
    if requirement not in _REQUIREMENTS:
        raise WorkspaceIsolationError(f"unsupported isolation requirement: {requirement}")
    if requirement == "none":
        return {"provider": "current_checkout", "operation": "adopt", "reason": "isolation is not required"}
    status = capabilities.get("native_task_status")
    if status not in {"not_started", "created"}:
        raise WorkspaceIsolationError("native_task_status must be not_started or created")
    current = capabilities.get("current_workspace")
    if (
        isinstance(current, Mapping)
        and current.get("provider") == "codex_managed_worktree"
        and current.get("repository_identity") == repository
        and current.get("issue_number") == issue_number
        and isinstance(current.get("workspace_id"), str)
        and current.get("workspace_id")
    ):
        return {"provider": "codex_managed_worktree", "operation": "adopt", "workspace_id": current["workspace_id"], "reason": "matching Codex worktree is active"}
    if status == "created":
        raise WorkspaceIsolationError("another native task exists; local fallback is unsafe")
    if capabilities.get("codex_project_tasks") is True:
        return {"provider": "codex_managed_worktree", "operation": "fork_task" if capabilities.get("source_task_id") else "create_task", "reason": "native Codex worktrees are available"}
    if capabilities.get("local_git_worktrees") is True:
        return {"provider": "local_git_worktree", "operation": "invoke_vanilla_worktree_skill", "reason": "use the upstream hidden-worktree mechanic"}
    if requirement == "preferred":
        return {"provider": "current_checkout", "operation": "adopt", "reason": "no isolation provider is available"}
    raise WorkspaceIsolationError("required isolation has no available provider")


def validate_workspace_receipt(
    receipt: Mapping[str, Any],
    expected: Mapping[str, Any],
    *,
    current_head: str,
    current_branch: str,
    publication: bool,
    allowed_dispositions: set[str] | None = None,
) -> None:
    missing = sorted(_RECEIPT_FIELDS - set(receipt))
    unknown = sorted(set(receipt) - _RECEIPT_FIELDS)
    if missing or unknown:
        raise WorkspaceIsolationError(f"workspace receipt fields are invalid: missing={missing}, unknown={unknown}")
    if type(receipt["schema_version"]) is not int or receipt["schema_version"] != 1:
        raise WorkspaceIsolationError("workspace receipt schema_version must be 1")
    provider = receipt["provider"]
    if provider not in _OWNERS or receipt["owner"] not in _OWNERS[provider]:
        raise WorkspaceIsolationError("workspace provider and owner are incompatible")
    if receipt["disposition"] not in (allowed_dispositions or {"active", "integrated", "preserved"}):
        raise WorkspaceIsolationError("workspace disposition is invalid")
    _text(receipt, "workspace_id")
    _text(receipt, "repository_root")
    _text(receipt, "git_common_dir")
    _issue(receipt)
    if provider == "codex_managed_worktree" and (not isinstance(receipt["task_id"], str) or not receipt["task_id"] or not isinstance(receipt["thread_id"], str) or not receipt["thread_id"]):
        raise WorkspaceIsolationError("Codex workspace receipt requires task and thread identity")
    if provider == "local_git_worktree" and (receipt["task_id"] is not None or not isinstance(receipt["thread_id"], str) or not receipt["thread_id"]):
        raise WorkspaceIsolationError("local workspace receipt requires null task_id and a thread marker")
    if not isinstance(receipt["observed_head"], str) or not re.fullmatch(r"[0-9a-f]{40}", receipt["observed_head"]):
        raise WorkspaceIsolationError("observed_head must be a 40-character Git commit")
    for field, value in expected.items():
        if receipt.get(field) != value:
            raise WorkspaceIsolationError(f"workspace receipt {field} does not match the leaf binding")
    if receipt["observed_head"] != current_head:
        raise WorkspaceIsolationError("workspace receipt head is stale")
    mode = receipt["head_mode"]
    branch = receipt["branch"]
    if mode == "detached":
        if branch is not None:
            raise WorkspaceIsolationError("detached workspace cannot name a branch")
    elif mode == "branch":
        if not isinstance(branch, str) or branch != current_branch:
            raise WorkspaceIsolationError("workspace branch does not match current branch")
    else:
        raise WorkspaceIsolationError("workspace head_mode is invalid")
    if publication and mode != "branch":
        raise WorkspaceIsolationError("publication requires a branch-bound workspace")
