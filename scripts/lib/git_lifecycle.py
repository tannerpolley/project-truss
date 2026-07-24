"""Fail-closed Git synchronization and merged-outcome retirement."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Mapping
from urllib.parse import quote


Runner = Callable[[list[str], Path, int], subprocess.CompletedProcess[str]]


class GitLifecycleError(RuntimeError):
    def __init__(self, blocker: str, message: str):
        self.blocker = blocker
        super().__init__(message)


@dataclass(frozen=True)
class GitSyncResult:
    canonical_checkout: str
    primary_remote: str
    default_branch: str
    remote_ref: str
    implementation_base: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, data: Any) -> "GitSyncResult":
        expected = set(cls.__dataclass_fields__)
        if not isinstance(data, Mapping) or set(data) != expected:
            raise ValueError(
                "preparation requires exactly canonical_checkout, primary_remote, "
                "default_branch, remote_ref, and implementation_base"
            )
        if any(not isinstance(data[field], str) for field in expected):
            raise ValueError("preparation fields must be strings")
        values = {field: data[field].strip() for field in expected}
        if not all(values.values()) or any(
            any(ord(character) < 32 for character in value)
            for value in values.values()
        ):
            raise ValueError("preparation fields must be non-empty strings")
        if re.fullmatch(
            r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})",
            values["implementation_base"],
        ) is None:
            raise ValueError("preparation implementation_base must be a full Git commit")
        return cls(**values)


@dataclass(frozen=True)
class CleanupRequest:
    pull_request: int
    branch: str
    worktree: str
    cleanup_authorized: bool

    @classmethod
    def from_mapping(cls, data: Any) -> "CleanupRequest":
        expected = {"pull_request", "branch", "worktree", "cleanup_authorized"}
        if not isinstance(data, Mapping) or set(data) != expected:
            raise ValueError(
                "cleanup request requires exactly pull_request, branch, worktree, and cleanup_authorized"
            )
        if type(data["pull_request"]) is not int or data["pull_request"] < 1:
            raise ValueError("cleanup pull_request must be a positive integer")
        if not isinstance(data["branch"], str) or not isinstance(
            data["worktree"], str
        ):
            raise ValueError("cleanup branch and worktree must be strings")
        branch = data["branch"].strip()
        worktree = data["worktree"].strip()
        if not branch or not worktree:
            raise ValueError("cleanup branch and worktree are required")
        if any(ord(character) < 32 for character in branch + worktree):
            raise ValueError("cleanup branch and worktree contain control characters")
        if not Path(worktree).is_absolute():
            raise ValueError("cleanup worktree must be an absolute path")
        if type(data["cleanup_authorized"]) is not bool:
            raise ValueError("cleanup_authorized must be boolean")
        return cls(data["pull_request"], branch, worktree, data["cleanup_authorized"])


@dataclass(frozen=True)
class CleanupResult:
    canonical_checkout: str
    primary_remote: str
    default_branch: str
    implementation_base: str
    cleanup: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class _RepositoryState:
    canonical_checkout: Path
    primary_remote: str
    default_branch: str
    remote_ref: str


@dataclass(frozen=True)
class _Worktree:
    path: Path
    branch: str | None


def _default_runner(
    command: list[str], cwd: Path, timeout: int = 30
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _run(
    runner: Runner,
    command: list[str],
    cwd: Path,
    *,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    try:
        return runner(command, cwd, timeout)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise GitLifecycleError("external_state_unavailable", str(exc)) from exc


def _checked(
    runner: Runner,
    command: list[str],
    cwd: Path,
    *,
    blocker: str = "external_state_unavailable",
) -> str:
    result = _run(runner, command, cwd)
    if result.returncode:
        detail = (result.stderr or result.stdout or "command failed").strip()
        raise GitLifecycleError(blocker, detail)
    return result.stdout.strip()


def _git(
    runner: Runner,
    cwd: Path,
    *args: str,
    blocker: str = "external_state_unavailable",
) -> str:
    return _checked(runner, ["git", *args], cwd, blocker=blocker)


def _worktrees(runner: Runner, repo_root: Path) -> list[_Worktree]:
    output = _git(runner, repo_root, "worktree", "list", "--porcelain")
    worktrees: list[_Worktree] = []
    path: Path | None = None
    branch: str | None = None
    for line in [*output.splitlines(), ""]:
        if line.startswith("worktree "):
            if path is not None:
                worktrees.append(_Worktree(path, branch))
            path = Path(line.removeprefix("worktree ")).resolve()
            branch = None
        elif line.startswith("branch refs/heads/"):
            branch = line.removeprefix("branch refs/heads/")
        elif not line and path is not None:
            worktrees.append(_Worktree(path, branch))
            path = None
            branch = None
    if not worktrees:
        raise GitLifecycleError(
            "state_contradiction", "Git did not report a canonical checkout"
        )
    return worktrees


def _remote_default(
    runner: Runner, canonical: Path, remote: str
) -> str | None:
    result = _run(
        runner, ["git", "ls-remote", "--symref", remote, "HEAD"], canonical
    )
    if result.returncode:
        return None
    for line in result.stdout.splitlines():
        match = re.fullmatch(r"ref:\s+refs/heads/(.+)\s+HEAD", line.strip())
        if match:
            return match.group(1)
    return None


def _config(
    runner: Runner, canonical: Path, key: str
) -> str:
    result = _run(runner, ["git", "config", "--get", key], canonical)
    return result.stdout.strip() if result.returncode == 0 else ""


def _local_branch_exists(
    runner: Runner, canonical: Path, branch: str
) -> bool:
    result = _run(
        runner,
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        canonical,
    )
    return result.returncode == 0


def _github_repository(remote_url: str) -> str | None:
    patterns = (
        r"https?://github\.com/(?P<repo>[^/]+/[^/]+?)(?:\.git)?/?$",
        r"git@github\.com:(?P<repo>[^/]+/[^/]+?)(?:\.git)?$",
        r"ssh://git@github\.com/(?P<repo>[^/]+/[^/]+?)(?:\.git)?/?$",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, remote_url.strip(), re.IGNORECASE)
        if match:
            return match.group("repo")
    return None


def _discover_repository(
    repo_root: Path, runner: Runner
) -> _RepositoryState:
    root = repo_root.resolve()
    worktrees = _worktrees(runner, root)
    canonical = worktrees[0].path
    remotes = _git(runner, canonical, "remote").splitlines()
    if not remotes:
        raise GitLifecycleError(
            "external_state_unavailable", "repository has no configured remotes"
        )

    defaults = {
        remote: default
        for remote in remotes
        if (default := _remote_default(runner, canonical, remote))
    }
    candidates: list[tuple[str, str]] = []
    for remote, default in defaults.items():
        if not _local_branch_exists(runner, canonical, default):
            continue
        if (
            _config(runner, canonical, f"branch.{default}.remote") == remote
            and _config(runner, canonical, f"branch.{default}.merge")
            == f"refs/heads/{default}"
        ):
            candidates.append((remote, default))

    if len(candidates) > 1:
        preferred = _config(runner, canonical, "remote.pushDefault")
        selected = [candidate for candidate in candidates if candidate[0] == preferred]
        if len(selected) == 1:
            candidates = selected
    if len(candidates) != 1:
        raise GitLifecycleError(
            "state_contradiction",
            "primary remote and default branch are ambiguous or untracked",
        )
    remote, default = candidates[0]
    return _RepositoryState(
        canonical_checkout=canonical,
        primary_remote=remote,
        default_branch=default,
        remote_ref=f"refs/remotes/{remote}/{default}",
    )


def synchronize_default(
    repo_root: Path,
    *,
    runner: Runner = _default_runner,
) -> GitSyncResult:
    state = _discover_repository(repo_root, runner)
    canonical = state.canonical_checkout
    if repo_root.resolve() != canonical:
        raise GitLifecycleError(
            "state_contradiction",
            "Prepare must run from the canonical checkout",
        )
    current = _git(runner, canonical, "branch", "--show-current")
    if current != state.default_branch:
        raise GitLifecycleError(
            "state_contradiction",
            "canonical checkout is not on the discovered default branch",
        )
    if _git(runner, canonical, "status", "--porcelain"):
        raise GitLifecycleError(
            "state_contradiction", "canonical checkout is dirty"
        )

    _git(
        runner,
        canonical,
        "fetch",
        "--prune",
        state.primary_remote,
        blocker="external_state_unavailable",
    )
    refreshed_default = _remote_default(
        runner, canonical, state.primary_remote
    )
    if refreshed_default != state.default_branch:
        raise GitLifecycleError(
            "state_contradiction",
            "primary remote default branch changed during synchronization",
        )
    if not _run(
        runner,
        ["git", "show-ref", "--verify", "--quiet", state.remote_ref],
        canonical,
    ).returncode == 0:
        raise GitLifecycleError(
            "external_state_unavailable",
            f"remote-tracking default branch is missing: {state.remote_ref}",
        )

    merge = _run(
        runner,
        ["git", "merge", "--ff-only", state.remote_ref],
        canonical,
    )
    if merge.returncode:
        raise GitLifecycleError(
            "state_contradiction",
            "canonical default branch cannot be fast-forwarded",
        )
    local_head = _git(runner, canonical, "rev-parse", "HEAD")
    remote_head = _git(runner, canonical, "rev-parse", state.remote_ref)
    if local_head != remote_head:
        raise GitLifecycleError(
            "state_contradiction",
            "canonical default branch cannot be fast-forwarded to exact remote state",
        )
    if _git(runner, canonical, "status", "--porcelain"):
        raise GitLifecycleError(
            "state_contradiction",
            "canonical checkout changed outside the fast-forward",
        )
    return GitSyncResult(
        canonical_checkout=str(canonical),
        primary_remote=state.primary_remote,
        default_branch=state.default_branch,
        remote_ref=state.remote_ref,
        implementation_base=local_head,
    )


def validate_preparation(
    preparation: GitSyncResult,
    *,
    active_branch: str | None = None,
    runner: Runner = _default_runner,
) -> None:
    canonical = Path(preparation.canonical_checkout).resolve()
    state = _discover_repository(canonical, runner)
    if (
        state.canonical_checkout != canonical
        or state.primary_remote != preparation.primary_remote
        or state.default_branch != preparation.default_branch
        or state.remote_ref != preparation.remote_ref
    ):
        raise GitLifecycleError(
            "state_contradiction", "preparation no longer matches live Git identity"
        )
    current = _git(runner, canonical, "branch", "--show-current")
    if current not in {preparation.default_branch, active_branch}:
        raise GitLifecycleError(
            "state_contradiction", "prepared canonical checkout changed branches"
        )
    if _git(runner, canonical, "status", "--porcelain"):
        raise GitLifecycleError(
            "state_contradiction", "prepared canonical checkout is dirty"
        )
    _git(
        runner,
        canonical,
        "fetch",
        "--prune",
        preparation.primary_remote,
        blocker="external_state_unavailable",
    )
    local_default = _git(
        runner, canonical, "rev-parse", f"refs/heads/{preparation.default_branch}"
    )
    remote_default = _git(runner, canonical, "rev-parse", preparation.remote_ref)
    if (
        local_default != preparation.implementation_base
        or remote_default != preparation.implementation_base
    ):
        raise GitLifecycleError(
            "state_contradiction", "prepared implementation base is stale"
        )


def _pull_request_proof(
    runner: Runner,
    cwd: Path,
    repository: str,
    request: CleanupRequest,
) -> tuple[Mapping[str, Any], str | None]:
    fields = (
        "number,state,mergedAt,headRefName,headRefOid,"
        "baseRefName,headRepository,url"
    )
    output = _checked(
        runner,
        [
            "gh",
            "pr",
            "view",
            str(request.pull_request),
            "--repo",
            repository,
            "--json",
            fields,
        ],
        cwd,
        blocker="external_state_unavailable",
    )
    try:
        payload = json.loads(output)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise GitLifecycleError(
            "external_state_unavailable", f"invalid pull request JSON: {exc}"
        ) from exc
    required = {
        "number",
        "state",
        "mergedAt",
        "headRefName",
        "headRefOid",
        "baseRefName",
        "headRepository",
        "url",
    }
    if not isinstance(payload, Mapping) or not required.issubset(payload):
        raise GitLifecycleError(
            "github_capability_missing", "pull request proof is incomplete"
        )
    head_repository = payload["headRepository"]
    head_name = (
        head_repository.get("nameWithOwner")
        if isinstance(head_repository, Mapping)
        else None
    )
    if (
        payload["number"] != request.pull_request
        or str(payload["state"]).upper() != "MERGED"
        or not payload["mergedAt"]
        or payload["headRefName"] != request.branch
        or not isinstance(head_name, str)
        or head_name.casefold() != repository.casefold()
    ):
        return payload, "pull request merge/head repository proof is unverified"
    return payload, None


def _sync_snapshot(state: _RepositoryState, runner: Runner) -> GitSyncResult:
    canonical = state.canonical_checkout
    if _git(runner, canonical, "branch", "--show-current") != state.default_branch:
        raise GitLifecycleError(
            "state_contradiction",
            "canonical checkout is not on the discovered default branch",
        )
    if _git(runner, canonical, "status", "--porcelain"):
        raise GitLifecycleError("state_contradiction", "canonical checkout is dirty")
    return GitSyncResult(
        str(canonical),
        state.primary_remote,
        state.default_branch,
        state.remote_ref,
        _git(runner, canonical, "rev-parse", f"refs/heads/{state.default_branch}"),
    )


def _repository_snapshot(
    state: _RepositoryState, runner: Runner
) -> GitSyncResult:
    return GitSyncResult(
        str(state.canonical_checkout),
        state.primary_remote,
        state.default_branch,
        state.remote_ref,
        _git(
            runner,
            state.canonical_checkout,
            "rev-parse",
            f"refs/heads/{state.default_branch}",
        ),
    )


def _cleanup_result(
    synced: GitSyncResult, cleanup: str, detail: str
) -> CleanupResult:
    return CleanupResult(
        synced.canonical_checkout,
        synced.primary_remote,
        synced.default_branch,
        synced.implementation_base,
        cleanup,
        detail,
    )


def _branch_has_rules(
    runner: Runner, canonical: Path, repository: str, branch: str
) -> bool:
    output = _checked(
        runner,
        [
            "gh",
            "api",
            f"repos/{repository}/rules/branches/{quote(branch, safe='')}",
        ],
        canonical,
        blocker="external_state_unavailable",
    )
    try:
        rules = json.loads(output)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise GitLifecycleError(
            "external_state_unavailable", f"invalid branch rules JSON: {exc}"
        ) from exc
    if not isinstance(rules, list):
        raise GitLifecycleError(
            "github_capability_missing", "branch rules proof is incomplete"
        )
    return bool(rules)


def _remote_branch_exists(
    runner: Runner, canonical: Path, remote: str, branch: str
) -> bool:
    result = _run(
        runner,
        ["git", "ls-remote", "--heads", remote, f"refs/heads/{branch}"],
        canonical,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise GitLifecycleError("external_state_unavailable", detail)
    return bool(result.stdout.strip())


def _restore_branch(
    runner: Runner, canonical: Path, branch: str, head: str
) -> None:
    restored = _run(
        runner,
        [
            "git",
            "update-ref",
            f"refs/heads/{branch}",
            head,
            "0" * len(head),
        ],
        canonical,
    )
    if restored.returncode:
        raise GitLifecycleError(
            "state_contradiction", "deleted branch ref could not be restored"
        )


def cleanup_merged_outcome(
    repo_root: Path,
    repository: str,
    request: CleanupRequest,
    *,
    runner: Runner = _default_runner,
) -> CleanupResult:
    root = repo_root.resolve()
    discovered = _discover_repository(root, runner)
    if root != discovered.canonical_checkout:
        raise GitLifecycleError(
            "state_contradiction",
            "Cleanup must run from the canonical checkout",
        )
    try:
        current = _sync_snapshot(discovered, runner)
    except GitLifecycleError as exc:
        if exc.blocker != "state_contradiction":
            raise
        return _cleanup_result(
            _repository_snapshot(discovered, runner),
            "skipped_unsafe_canonical",
            str(exc),
        )
    proof, unverified = _pull_request_proof(runner, root, repository, request)
    if unverified:
        return _cleanup_result(
            current, "skipped_unverified_pull_request", unverified
        )
    if _remote_branch_exists(
        runner,
        discovered.canonical_checkout,
        discovered.primary_remote,
        request.branch,
    ):
        raise GitLifecycleError(
            "state_contradiction",
            "pull request head branch still exists on the primary remote",
        )

    try:
        synced = synchronize_default(root, runner=runner)
    except GitLifecycleError as exc:
        if exc.blocker != "state_contradiction":
            raise
        return _cleanup_result(
            _repository_snapshot(discovered, runner),
            "skipped_unsafe_canonical",
            str(exc),
        )
    if _remote_branch_exists(
        runner,
        Path(synced.canonical_checkout),
        synced.primary_remote,
        request.branch,
    ):
        return _cleanup_result(
            synced,
            "skipped_remote_branch_recreated",
            "pull request head branch was recreated during synchronization",
        )
    if proof["baseRefName"] != synced.default_branch:
        raise GitLifecycleError(
            "state_contradiction",
            "pull request base does not match the discovered default branch",
        )
    if not request.cleanup_authorized:
        return _cleanup_result(
            synced,
            "skipped_not_authorized",
            "default branch synchronized; local cleanup authority was not granted",
        )
    canonical = Path(synced.canonical_checkout)
    remote_url = _git(
        runner,
        canonical,
        "remote",
        "get-url",
        synced.primary_remote,
    )
    github_repository = _github_repository(remote_url)
    if (
        github_repository is None
        or github_repository.casefold() != repository.casefold()
    ):
        return _cleanup_result(
            synced,
            "skipped_non_github_remote",
            "primary remote is not the GitHub repository that supplied merge proof",
        )
    if request.branch == synced.default_branch or _branch_has_rules(
        runner, canonical, repository, request.branch
    ):
        return _cleanup_result(
            synced,
            "skipped_protected_branch",
            "default or GitHub-rules-protected branches are never cleanup targets",
        )

    worktrees = _worktrees(runner, root)
    checked_out = next(
        (worktree for worktree in worktrees if worktree.branch == request.branch),
        None,
    )
    requested_worktree = Path(request.worktree).resolve()
    if not _local_branch_exists(runner, canonical, request.branch):
        return _cleanup_result(
            synced,
            "skipped_branch_absent",
            "local outcome branch is already absent",
        )
    if (
        _config(runner, canonical, f"branch.{request.branch}.remote")
        != synced.primary_remote
        or _config(runner, canonical, f"branch.{request.branch}.merge")
        != f"refs/heads/{request.branch}"
    ):
        return _cleanup_result(
            synced,
            "skipped_unverified_branch",
            "local branch is not bound to the deleted primary-remote head",
        )
    local_head = _git(runner, canonical, "rev-parse", request.branch)
    if local_head != proof["headRefOid"]:
        return _cleanup_result(
            synced,
            "skipped_diverged_branch",
            "local outcome branch no longer matches the merged pull request head",
        )
    if checked_out is not None:
        if checked_out.path != requested_worktree or checked_out.path == canonical:
            return _cleanup_result(
                synced,
                "skipped_checked_out_worktree",
                f"branch is still checked out in {checked_out.path}",
            )
        if _git(runner, checked_out.path, "status", "--porcelain"):
            return _cleanup_result(
                synced,
                "skipped_dirty_worktree",
                f"outcome worktree is dirty: {checked_out.path}",
            )
    elif requested_worktree != canonical:
        return _cleanup_result(
            synced,
            "skipped_worktree_absent",
            "recorded non-canonical outcome worktree is not registered",
        )

    graph_merged = _run(
        runner,
        [
            "git",
            "merge-base",
            "--is-ancestor",
            request.branch,
            synced.default_branch,
        ],
        canonical,
    )
    if graph_merged.returncode not in {0, 1}:
        raise GitLifecycleError(
            "external_state_unavailable", "could not inspect branch ancestry"
        )
    final_worktrees = _worktrees(runner, root)
    final_checked_out = next(
        (worktree for worktree in final_worktrees if worktree.branch == request.branch),
        None,
    )
    if final_checked_out != checked_out:
        return _cleanup_result(
            synced,
            "skipped_checked_out_worktree",
            "outcome branch worktree occupancy changed during cleanup",
        )
    if _remote_branch_exists(
        runner, canonical, synced.primary_remote, request.branch
    ):
        return _cleanup_result(
            synced,
            "skipped_remote_branch_recreated",
            "pull request head branch was recreated before deletion",
        )
    deleted = _run(
        runner,
        [
            "git",
            "update-ref",
            "-d",
            f"refs/heads/{request.branch}",
            local_head,
        ],
        canonical,
    )
    if deleted.returncode:
        return _cleanup_result(
            synced,
            "skipped_diverged_branch",
            "outcome branch moved during compare-and-delete",
        )
    if _remote_branch_exists(
        runner, canonical, synced.primary_remote, request.branch
    ):
        _restore_branch(runner, canonical, request.branch, local_head)
        return _cleanup_result(
            synced,
            "skipped_remote_branch_recreated",
            "pull request head branch was recreated during deletion",
        )
    after_delete_worktree = next(
        (
            worktree
            for worktree in _worktrees(runner, root)
            if worktree.branch == request.branch
        ),
        None,
    )
    if after_delete_worktree != checked_out:
        _restore_branch(runner, canonical, request.branch, local_head)
        return _cleanup_result(
            synced,
            "skipped_checked_out_worktree",
            "outcome branch worktree occupancy changed during deletion",
        )
    if checked_out is not None:
        removal = _run(
            runner,
            ["git", "worktree", "remove", str(checked_out.path)],
            canonical,
        )
        if removal.returncode:
            _restore_branch(runner, canonical, request.branch, local_head)
            detail = (removal.stderr or removal.stdout).strip()
            return _cleanup_result(
                synced, "skipped_worktree_removal_failed", detail
            )
    if graph_merged.returncode == 0:
        return _cleanup_result(
            synced,
            "deleted_graph_merged",
            "deleted graph-merged outcome branch; retained inert tracking config",
        )
    return _cleanup_result(
        synced,
        "deleted_github_confirmed",
        "deleted squash/rebase branch using exact merged pull request proof; "
        "retained inert tracking config",
    )
