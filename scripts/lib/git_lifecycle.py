"""Synchronize the canonical default branch and retire one merged outcome."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Mapping
from urllib.parse import quote

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
    def from_mapping(cls, data: Any) -> GitSyncResult:
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
    def from_mapping(cls, data: Any) -> CleanupRequest:
        fields = tuple(cls.__dataclass_fields__)
        if not isinstance(data, Mapping) or set(data) != set(fields):
            raise ValueError(f"cleanup request requires exactly {', '.join(fields)}")
        number, branch, worktree, authorized = (
            data["pull_request"], data["branch"], data["worktree"], data["cleanup_authorized"])
        if type(number) is not int or number < 1:
            raise ValueError("cleanup pull_request must be a positive integer")
        if not isinstance(branch, str) or not isinstance(worktree, str):
            raise ValueError("cleanup branch and worktree must be strings")
        branch, worktree = branch.strip(), worktree.strip()
        if not branch or not worktree or any(ord(char) < 32 for char in branch + worktree):
            raise ValueError("cleanup branch and worktree must be safe non-empty strings")
        if not Path(worktree).is_absolute():
            raise ValueError("cleanup worktree must be an absolute path")
        if type(authorized) is not bool:
            raise ValueError("cleanup_authorized must be boolean")
        return cls(number, branch, worktree, authorized)


@dataclass(frozen=True)
class _Repository:
    canonical: Path
    remote: str
    default: str

    @property
    def remote_ref(self) -> str:
        return f"refs/remotes/{self.remote}/{self.default}"

def _default_runner(command: list[str], cwd: Path, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)


def _run(runner: Runner, cwd: Path, *command: str) -> subprocess.CompletedProcess[str]:
    try:
        return runner(list(command), cwd, 30)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise GitLifecycleError("external_state_unavailable", str(exc)) from exc


def _checked(runner: Runner, cwd: Path, *command: str) -> str:
    result = _run(runner, cwd, *command)
    if result.returncode:
        detail = (result.stderr or result.stdout or "command failed").strip()
        raise GitLifecycleError("external_state_unavailable", detail)
    return result.stdout.strip()


def _git(runner: Runner, cwd: Path, *args: str) -> str:
    return _checked(runner, cwd, "git", *args)


def _worktrees(runner: Runner, root: Path) -> list[tuple[Path, str | None]]:
    records = []
    for record in _git(runner, root, "worktree", "list", "--porcelain").split("\n\n"):
        fields = dict(line.partition(" ")[::2] for line in record.splitlines() if " " in line)
        if "worktree" in fields:
            branch = fields.get("branch")
            records.append((Path(fields["worktree"]).resolve(), branch[11:] if branch else None))
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


def _common_dir(runner: Runner, root: Path) -> Path:
    return Path(_git(runner, root, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()


def _discover(root: Path, runner: Runner) -> _Repository:
    canonical = _worktrees(runner, root)[0][0]
    candidates = []
    for remote in _git(runner, canonical, "remote").splitlines():
        default = _remote_default(runner, canonical, remote)
        tracks_default = default and (
            _config(runner, canonical, f"branch.{default}.remote"),
            _config(runner, canonical, f"branch.{default}.merge"),
        ) == (remote, f"refs/heads/{default}")
        if tracks_default:
            candidates.append((remote, default))
    if len(candidates) > 1:
        preferred = _config(runner, canonical, "remote.pushDefault")
        candidates = [item for item in candidates if item[0] == preferred]
    if len(candidates) != 1:
        raise GitLifecycleError(
            "state_contradiction", "primary remote and default branch are ambiguous or untracked"
        )
    return _Repository(canonical, *candidates[0])


def _clean_default(repository: _Repository, runner: Runner) -> None:
    if _git(runner, repository.canonical, "branch", "--show-current") != repository.default:
        raise GitLifecycleError(
            "state_contradiction", "canonical checkout is not on the discovered default branch"
        )
    if _git(runner, repository.canonical, "status", "--porcelain"):
        raise GitLifecycleError("state_contradiction", "canonical checkout is dirty")


def _snapshot(repository: _Repository, runner: Runner) -> GitSyncResult:
    base = _git(runner, repository.canonical, "rev-parse", f"refs/heads/{repository.default}")
    return GitSyncResult(
        str(repository.canonical), repository.remote, repository.default, repository.remote_ref, base
    )


def synchronize_default(repo_root: Path, *, runner: Runner = _default_runner) -> GitSyncResult:
    root = repo_root.resolve()
    repository = _discover(root, runner)
    if root != repository.canonical:
        raise GitLifecycleError("state_contradiction", "Prepare must run from the canonical checkout")
    _clean_default(repository, runner)
    _git(runner, root, "fetch", "--prune", repository.remote)
    if _remote_default(runner, root, repository.remote) != repository.default:
        raise GitLifecycleError(
            "state_contradiction", "remote default branch changed during synchronization"
        )
    if _run(runner, root, "git", "merge", "--ff-only", repository.remote_ref).returncode:
        raise GitLifecycleError(
            "state_contradiction", "canonical default branch cannot be fast-forwarded"
        )
    result = _snapshot(repository, runner)
    remote_head = _git(runner, root, "rev-parse", repository.remote_ref)
    if result.implementation_base != remote_head or _git(runner, root, "status", "--porcelain"):
        raise GitLifecycleError(
            "state_contradiction", "canonical default branch is not the exact clean remote state"
        )
    return result


def validate_preparation(
    preparation: GitSyncResult,
    repo_root: Path,
    *,
    active_branch: str | None = None,
    runner: Runner = _default_runner,
) -> None:
    canonical = Path(preparation.canonical_checkout).resolve()
    if _common_dir(runner, repo_root.resolve()) != _common_dir(runner, canonical):
        raise GitLifecycleError("state_contradiction", "preparation belongs to a different repository")
    repository = _discover(canonical, runner)
    live = (repository.canonical, repository.remote, repository.default, repository.remote_ref)
    recorded = (
        canonical,
        preparation.primary_remote,
        preparation.default_branch,
        preparation.remote_ref,
    )
    if live != recorded:
        raise GitLifecycleError(
            "state_contradiction", "preparation no longer matches live Git identity"
        )
    if _git(runner, canonical, "branch", "--show-current") not in {
        preparation.default_branch,
        active_branch,
    }:
        raise GitLifecycleError("state_contradiction", "prepared canonical checkout changed branches")
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
        "gh", "pr", "view", str(request.pull_request),
        "--repo", repository,
        "--json", "number,state,mergedAt,headRefName,headRefOid,baseRefName,headRepository",
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


def _remote_branch_exists(runner: Runner, root: Path, remote: str, branch: str) -> bool:
    result = _run(runner, root, "git", "ls-remote", "--heads", remote, f"refs/heads/{branch}")
    if result.returncode:
        detail = (result.stderr or result.stdout or "git ls-remote failed").strip()
        raise GitLifecycleError("external_state_unavailable", detail)
    return bool(result.stdout.strip())


def _branch_has_rules(runner: Runner, root: Path, repository: str, branch: str) -> bool:
    endpoint = f"repos/{repository}/rules/branches/{quote(branch, safe='')}"
    try:
        rules = json.loads(_checked(runner, root, "gh", "api", endpoint))
    except (TypeError, ValueError) as exc:
        raise GitLifecycleError("external_state_unavailable", "invalid branch rules JSON") from exc
    if not isinstance(rules, list):
        raise GitLifecycleError("github_capability_missing", "branch rules proof is incomplete")
    return bool(rules)


def _result(sync: GitSyncResult, cleanup: str, detail: str) -> dict[str, Any]:
    return {key: value for key, value in sync.to_dict().items() if key != "remote_ref"} | {"cleanup": cleanup, "detail": detail}
def cleanup_merged_outcome(
    repo_root: Path,
    repository: str,
    request: CleanupRequest,
    *,
    runner: Runner = _default_runner,
) -> dict[str, Any]:
    root = repo_root.resolve()
    discovered = _discover(root, runner)
    if root != discovered.canonical:
        raise GitLifecycleError("state_contradiction", "Cleanup must run from the canonical checkout")
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
        return _result(_snapshot(discovered, runner), "skipped_unsafe_canonical", str(exc))
    if proof.get("baseRefName") != sync.default_branch:
        raise GitLifecycleError(
            "state_contradiction", "pull request base does not match the discovered default branch"
        )
    if not request.cleanup_authorized:
        return _result(
            sync, "skipped_not_authorized", "default synchronized; local cleanup was not authorized"
        )

    canonical = Path(sync.canonical_checkout)
    remote_url = _git(runner, canonical, "remote", "get-url", sync.primary_remote)
    if (_github_repository(remote_url) or "").casefold() != repository.casefold():
        return _result(
            sync, "skipped_non_github_remote", "primary remote does not match the GitHub merge proof"
        )
    if request.branch == sync.default_branch or _branch_has_rules(
        runner, canonical, repository, request.branch
    ):
        return _result(sync, "skipped_protected_branch", "branch is protected")
    if _remote_branch_exists(runner, canonical, sync.primary_remote, request.branch):
        return _result(sync, "skipped_remote_branch_recreated", "remote branch was recreated")

    branch_ref = f"refs/heads/{request.branch}"
    if _run(runner, canonical, "git", "show-ref", "--verify", "--quiet", branch_ref).returncode:
        return _result(sync, "skipped_branch_absent", "local branch is absent")
    tracking = (
        _config(runner, canonical, f"branch.{request.branch}.remote"),
        _config(runner, canonical, f"branch.{request.branch}.merge"),
    )
    if tracking != (sync.primary_remote, f"refs/heads/{request.branch}"):
        return _result(
            sync, "skipped_unverified_branch", "branch is not bound to the deleted remote head"
        )
    local_head = _git(runner, canonical, "rev-parse", branch_ref)
    if local_head != proof["headRefOid"]:
        return _result(sync, "skipped_diverged_branch", "branch differs from merged PR head")

    recorded = Path(request.worktree).resolve()
    checked_out = next(
        ((path, branch) for path, branch in _worktrees(runner, root) if branch == request.branch),
        None,
    )
    if checked_out:
        path, _ = checked_out
        if path != recorded or path == canonical:
            return _result(sync, "skipped_checked_out_worktree", f"branch is active in {path}")
        if _git(runner, path, "status", "--porcelain"):
            return _result(sync, "skipped_dirty_worktree", f"worktree is dirty: {path}")
    elif recorded != canonical:
        return _result(sync, "skipped_worktree_absent", "recorded outcome worktree is absent")

    graph_merged = _run(
        runner, canonical, "git", "merge-base", "--is-ancestor", branch_ref, sync.default_branch
    )
    if graph_merged.returncode not in {0, 1}:
        raise GitLifecycleError("external_state_unavailable", "could not inspect ancestry")
    if checked_out:
        detached = _run(runner, path, "git", "switch", "--detach", local_head)
        if detached.returncode:
            return _result(
                sync, "skipped_worktree_detach_failed", (detached.stderr or detached.stdout).strip()
            )

    deleted = _run(runner, canonical, "git", "update-ref", "-d", branch_ref, local_head)
    if deleted.returncode:
        if checked_out and _run(runner, path, "git", "switch", request.branch).returncode:
            raise GitLifecycleError(
                "state_contradiction", "worktree could not be reattached after cleanup conflict"
            )
        return _result(sync, "skipped_diverged_branch", "branch moved or could not be safely deleted")
    if checked_out:
        removal = _run(runner, canonical, "git", "worktree", "remove", str(path))
        if removal.returncode:
            restored = _run(
                runner, canonical, "git", "update-ref", branch_ref, local_head, "0" * len(local_head)
            )
            if restored.returncode:
                raise GitLifecycleError(
                    "state_contradiction", "branch could not be restored after cleanup failure"
                )
            if _run(runner, path, "git", "switch", request.branch).returncode:
                raise GitLifecycleError(
                    "state_contradiction", "worktree could not be reattached after cleanup failure"
                )
            detail = (removal.stderr or removal.stdout).strip()
            return _result(sync, "skipped_worktree_removal_failed", detail)
    cleanup = "deleted_graph_merged" if graph_merged.returncode == 0 else "deleted_github_confirmed"
    return _result(sync, cleanup, "deleted the verified merged outcome")
