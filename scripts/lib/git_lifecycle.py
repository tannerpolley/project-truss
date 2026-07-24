"""Synchronize the canonical default branch and retire one merged outcome."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Mapping


Runner = Callable[[list[str], Path, int], subprocess.CompletedProcess[str]]
_SHA = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")


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
        fields = tuple(cls.__dataclass_fields__)
        if not isinstance(data, Mapping) or set(data) != set(fields):
            raise ValueError(f"preparation requires exactly {', '.join(fields)}")
        if any(not isinstance(data[field], str) for field in fields):
            raise ValueError("preparation fields must be strings")
        values = {field: data[field].strip() for field in fields}
        if not all(values.values()) or not _SHA.fullmatch(values["implementation_base"]):
            raise ValueError("preparation fields and full implementation-base commit are required")
        return cls(**values)


@dataclass(frozen=True)
class CleanupRequest:
    pull_request: int
    branch: str
    worktree: str
    cleanup_authorized: bool

    @classmethod
    def from_mapping(cls, data: Any) -> "CleanupRequest":
        fields = tuple(cls.__dataclass_fields__)
        if not isinstance(data, Mapping) or set(data) != set(fields):
            raise ValueError(f"cleanup request requires exactly {', '.join(fields)}")
        pull_request = data["pull_request"]
        branch, worktree = data["branch"], data["worktree"]
        authorized = data["cleanup_authorized"]
        if type(pull_request) is not int or pull_request < 1:
            raise ValueError("cleanup pull_request must be a positive integer")
        if not isinstance(branch, str) or not isinstance(worktree, str):
            raise ValueError("cleanup branch and worktree must be strings")
        branch, worktree = branch.strip(), worktree.strip()
        if (
            not branch
            or not worktree
            or any(ord(character) < 32 for character in branch + worktree)
        ):
            raise ValueError("cleanup branch and worktree must be safe non-empty strings")
        if not Path(worktree).is_absolute():
            raise ValueError("cleanup worktree must be an absolute path")
        if type(authorized) is not bool:
            raise ValueError("cleanup_authorized must be boolean")
        return cls(pull_request, branch, worktree, authorized)


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
class _Repository:
    canonical: Path
    remote: str
    default: str

    @property
    def remote_ref(self) -> str:
        return f"refs/remotes/{self.remote}/{self.default}"


@dataclass(frozen=True)
class _Worktree:
    path: Path
    branch: str | None


def _default_runner(
    command: list[str], cwd: Path, timeout: int = 30
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False
    )


def _run(runner: Runner, cwd: Path, *command: str) -> subprocess.CompletedProcess[str]:
    try:
        return runner(list(command), cwd, 30)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise GitLifecycleError("external_state_unavailable", str(exc)) from exc


def _checked(
    runner: Runner,
    cwd: Path,
    *command: str,
    blocker: str = "external_state_unavailable",
) -> str:
    result = _run(runner, cwd, *command)
    if result.returncode:
        detail = (result.stderr or result.stdout or "command failed").strip()
        raise GitLifecycleError(blocker, detail)
    return result.stdout.strip()


def _git(
    runner: Runner, cwd: Path, *args: str, blocker: str = "external_state_unavailable"
) -> str:
    return _checked(runner, cwd, "git", *args, blocker=blocker)


def _worktrees(runner: Runner, root: Path) -> list[_Worktree]:
    records: list[_Worktree] = []
    path: Path | None = None
    branch: str | None = None
    for line in [*_git(runner, root, "worktree", "list", "--porcelain").splitlines(), ""]:
        if line.startswith("worktree "):
            if path:
                records.append(_Worktree(path, branch))
            path, branch = Path(line[9:]).resolve(), None
        elif line.startswith("branch refs/heads/"):
            branch = line[18:]
        elif not line and path:
            records.append(_Worktree(path, branch))
            path = None
    if not records:
        raise GitLifecycleError("state_contradiction", "Git reported no canonical checkout")
    return records


def _config(runner: Runner, root: Path, key: str) -> str:
    result = _run(runner, root, "git", "config", "--get", key)
    return result.stdout.strip() if result.returncode == 0 else ""


def _remote_default(runner: Runner, root: Path, remote: str) -> str | None:
    result = _run(runner, root, "git", "ls-remote", "--symref", remote, "HEAD")
    if result.returncode:
        return None
    match = re.search(r"^ref:\s+refs/heads/(.+)\s+HEAD$", result.stdout, re.MULTILINE)
    return match.group(1) if match else None


def _discover(root: Path, runner: Runner) -> _Repository:
    canonical = _worktrees(runner, root)[0].path
    candidates: list[tuple[str, str]] = []
    for remote in _git(runner, canonical, "remote").splitlines():
        default = _remote_default(runner, canonical, remote)
        if (
            default
            and _config(runner, canonical, f"branch.{default}.remote") == remote
            and _config(runner, canonical, f"branch.{default}.merge")
            == f"refs/heads/{default}"
        ):
            candidates.append((remote, default))
    if len(candidates) > 1:
        preferred = _config(runner, canonical, "remote.pushDefault")
        candidates = [candidate for candidate in candidates if candidate[0] == preferred]
    if len(candidates) != 1:
        raise GitLifecycleError(
            "state_contradiction",
            "primary remote and default branch are ambiguous or untracked",
        )
    return _Repository(canonical, *candidates[0])


def _clean_default(repository: _Repository, runner: Runner) -> None:
    if _git(runner, repository.canonical, "branch", "--show-current") != repository.default:
        raise GitLifecycleError(
            "state_contradiction",
            "canonical checkout is not on the discovered default branch",
        )
    if _git(runner, repository.canonical, "status", "--porcelain"):
        raise GitLifecycleError("state_contradiction", "canonical checkout is dirty")


def _snapshot(repository: _Repository, runner: Runner) -> GitSyncResult:
    return GitSyncResult(
        str(repository.canonical),
        repository.remote,
        repository.default,
        repository.remote_ref,
        _git(runner, repository.canonical, "rev-parse", f"refs/heads/{repository.default}"),
    )


def synchronize_default(
    repo_root: Path, *, runner: Runner = _default_runner
) -> GitSyncResult:
    root = repo_root.resolve()
    repository = _discover(root, runner)
    if root != repository.canonical:
        raise GitLifecycleError(
            "state_contradiction", "Prepare must run from the canonical checkout"
        )
    _clean_default(repository, runner)
    _git(runner, root, "fetch", "--prune", repository.remote)
    if _remote_default(runner, root, repository.remote) != repository.default:
        raise GitLifecycleError(
            "state_contradiction", "remote default branch changed during synchronization"
        )
    merge = _run(runner, root, "git", "merge", "--ff-only", repository.remote_ref)
    if merge.returncode:
        raise GitLifecycleError(
            "state_contradiction", "canonical default branch cannot be fast-forwarded"
        )
    result = _snapshot(repository, runner)
    if (
        result.implementation_base != _git(runner, root, "rev-parse", repository.remote_ref)
        or _git(runner, root, "status", "--porcelain")
    ):
        raise GitLifecycleError(
            "state_contradiction", "canonical default branch is not the exact clean remote state"
        )
    return result


def validate_preparation(
    preparation: GitSyncResult,
    *,
    active_branch: str | None = None,
    runner: Runner = _default_runner,
) -> None:
    canonical = Path(preparation.canonical_checkout).resolve()
    repository = _discover(canonical, runner)
    if (
        repository.canonical != canonical
        or repository.remote != preparation.primary_remote
        or repository.default != preparation.default_branch
        or repository.remote_ref != preparation.remote_ref
    ):
        raise GitLifecycleError(
            "state_contradiction", "preparation no longer matches live Git identity"
        )
    if _git(runner, canonical, "branch", "--show-current") not in {
        preparation.default_branch,
        active_branch,
    }:
        raise GitLifecycleError(
            "state_contradiction", "prepared canonical checkout changed branches"
        )
    if _git(runner, canonical, "status", "--porcelain"):
        raise GitLifecycleError("state_contradiction", "prepared canonical checkout is dirty")
    _git(runner, canonical, "fetch", "--prune", preparation.primary_remote)
    heads = (
        _git(runner, canonical, "rev-parse", f"refs/heads/{preparation.default_branch}"),
        _git(runner, canonical, "rev-parse", preparation.remote_ref),
    )
    if heads != (preparation.implementation_base,) * 2:
        raise GitLifecycleError("state_contradiction", "prepared implementation base is stale")


def _github_repository(remote_url: str) -> str | None:
    match = re.fullmatch(
        r"(?:https?://github\.com/|git@github\.com:|ssh://git@github\.com/)"
        r"([^/]+/[^/]+?)(?:\.git)?/?",
        remote_url.strip(),
        re.IGNORECASE,
    )
    return match.group(1) if match else None


def _pull_request(
    runner: Runner, root: Path, repository: str, request: CleanupRequest
) -> Mapping[str, Any] | None:
    output = _checked(
        runner,
        root,
        "gh",
        "pr",
        "view",
        str(request.pull_request),
        "--repo",
        repository,
        "--json",
        "number,state,mergedAt,headRefName,headRefOid,baseRefName,headRepository",
    )
    try:
        payload = json.loads(output)
    except (TypeError, ValueError) as exc:
        raise GitLifecycleError("external_state_unavailable", "invalid pull request JSON") from exc
    head = payload.get("headRepository") if isinstance(payload, Mapping) else None
    valid = (
        isinstance(payload, Mapping)
        and payload.get("number") == request.pull_request
        and str(payload.get("state")).upper() == "MERGED"
        and bool(payload.get("mergedAt"))
        and payload.get("headRefName") == request.branch
        and isinstance(head, Mapping)
        and str(head.get("nameWithOwner", "")).casefold() == repository.casefold()
        and bool(_SHA.fullmatch(str(payload.get("headRefOid", ""))))
    )
    return payload if valid else None


def _remote_branch_exists(
    runner: Runner, root: Path, remote: str, branch: str
) -> bool:
    result = _run(
        runner, root, "git", "ls-remote", "--heads", remote, f"refs/heads/{branch}"
    )
    if result.returncode:
        raise GitLifecycleError(
            "external_state_unavailable",
            (result.stderr or result.stdout or "git ls-remote failed").strip(),
        )
    return bool(result.stdout.strip())


def _result(sync: GitSyncResult, cleanup: str, detail: str) -> CleanupResult:
    return CleanupResult(
        sync.canonical_checkout,
        sync.primary_remote,
        sync.default_branch,
        sync.implementation_base,
        cleanup,
        detail,
    )


def cleanup_merged_outcome(
    repo_root: Path,
    repository: str,
    request: CleanupRequest,
    *,
    runner: Runner = _default_runner,
) -> CleanupResult:
    root = repo_root.resolve()
    discovered = _discover(root, runner)
    if root != discovered.canonical:
        raise GitLifecycleError(
            "state_contradiction", "Cleanup must run from the canonical checkout"
        )
    proof = _pull_request(runner, root, repository, request)
    if proof is None:
        return _result(
            _snapshot(discovered, runner),
            "skipped_unverified_pull_request",
            "exact merged pull request proof is unavailable",
        )
    if _remote_branch_exists(runner, root, discovered.remote, request.branch):
        raise GitLifecycleError(
            "state_contradiction", "pull request head branch still exists on the primary remote"
        )
    try:
        sync = synchronize_default(root, runner=runner)
    except GitLifecycleError as exc:
        if exc.blocker != "state_contradiction":
            raise
        return _result(
            _snapshot(discovered, runner), "skipped_unsafe_canonical", str(exc)
        )
    if proof.get("baseRefName") != sync.default_branch:
        raise GitLifecycleError(
            "state_contradiction",
            "pull request base does not match the discovered default branch",
        )
    if not request.cleanup_authorized:
        return _result(
            sync, "skipped_not_authorized", "default synchronized; local cleanup was not authorized"
        )
    canonical = Path(sync.canonical_checkout)
    remote_url = _git(runner, canonical, "remote", "get-url", sync.primary_remote)
    if (_github_repository(remote_url) or "").casefold() != repository.casefold():
        return _result(
            sync,
            "skipped_non_github_remote",
            "primary remote does not match the GitHub merge proof",
        )
    if request.branch == sync.default_branch:
        return _result(sync, "skipped_protected_branch", "default branch is protected")
    if _remote_branch_exists(runner, canonical, sync.primary_remote, request.branch):
        return _result(sync, "skipped_remote_branch_recreated", "remote branch was recreated")

    branch_ref = f"refs/heads/{request.branch}"
    exists = _run(runner, canonical, "git", "show-ref", "--verify", "--quiet", branch_ref)
    if exists.returncode:
        return _result(sync, "skipped_branch_absent", "local branch is absent")
    if (
        _config(runner, canonical, f"branch.{request.branch}.remote")
        != sync.primary_remote
        or _config(runner, canonical, f"branch.{request.branch}.merge")
        != f"refs/heads/{request.branch}"
    ):
        return _result(
            sync, "skipped_unverified_branch", "branch is not bound to the deleted remote head"
        )
    local_head = _git(runner, canonical, "rev-parse", branch_ref)
    if local_head != proof["headRefOid"]:
        return _result(sync, "skipped_diverged_branch", "branch differs from merged PR head")

    recorded = Path(request.worktree).resolve()
    checked_out = next(
        (item for item in _worktrees(runner, root) if item.branch == request.branch), None
    )
    if checked_out:
        if checked_out.path != recorded or checked_out.path == canonical:
            return _result(
                sync,
                "skipped_checked_out_worktree",
                f"branch is active in {checked_out.path}",
            )
        if _git(runner, checked_out.path, "status", "--porcelain"):
            return _result(
                sync, "skipped_dirty_worktree", f"worktree is dirty: {checked_out.path}"
            )
        removal = _run(runner, canonical, "git", "worktree", "remove", str(checked_out.path))
        if removal.returncode:
            return _result(
                sync,
                "skipped_worktree_removal_failed",
                (removal.stderr or removal.stdout).strip(),
            )
    elif recorded != canonical:
        return _result(sync, "skipped_worktree_absent", "recorded outcome worktree is absent")

    graph_merged = _run(
        runner,
        canonical,
        "git",
        "merge-base",
        "--is-ancestor",
        branch_ref,
        sync.default_branch,
    )
    if graph_merged.returncode not in {0, 1}:
        raise GitLifecycleError("external_state_unavailable", "could not inspect ancestry")
    if graph_merged.returncode == 0:
        deleted = _run(runner, canonical, "git", "branch", "-d", request.branch)
        cleanup = "deleted_graph_merged"
    else:
        deleted = _run(runner, canonical, "git", "update-ref", "-d", branch_ref, local_head)
        cleanup = "deleted_github_confirmed"
    if deleted.returncode:
        return _result(
            sync, "skipped_diverged_branch", "branch moved or could not be safely deleted"
        )
    return _result(sync, cleanup, "deleted the verified merged outcome")
