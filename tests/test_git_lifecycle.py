from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.lib.git_lifecycle import (
    CleanupRequest,
    GitLifecycleError,
    cleanup_merged_outcome,
    synchronize_default,
    validate_preparation,
)


ROOT = Path(__file__).resolve().parents[1]


class Repository:
    def __init__(self, root: Path, default: str = "trunk"):
        self.root, self.default = root, default
        self.remote, self.seed, self.repo = (
            root / "remote.git",
            root / "seed",
            root / "repo",
        )
        root.mkdir(parents=True, exist_ok=True)
        self.git(root, "init", "--bare", f"--initial-branch={default}", str(self.remote))
        self.git(root, "clone", str(self.remote), str(self.seed))
        self.configure(self.seed)
        (self.seed / "README.md").write_text("base\n", encoding="utf-8")
        self.git(self.seed, "add", "README.md")
        self.git(self.seed, "commit", "-m", "base")
        self.git(self.seed, "push", "-u", "origin", default)
        self.git(root, "clone", str(self.remote), str(self.repo))
        self.configure(self.repo)

    @staticmethod
    def git(cwd: Path, *args: str, check: bool = True) -> str:
        result = subprocess.run(
            ["git", *args], cwd=cwd, text=True, capture_output=True, check=False
        )
        if check and result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return result.stdout.strip()

    def configure(self, path: Path) -> None:
        self.git(path, "config", "user.name", "Project Truss Test")
        self.git(path, "config", "user.email", "project-truss@example.com")

    def advance(self, text: str = "remote\n") -> str:
        (self.seed / "README.md").write_text(text, encoding="utf-8")
        self.git(self.seed, "add", "README.md")
        self.git(self.seed, "commit", "-m", text.strip())
        self.git(self.seed, "push", "origin", self.default)
        return self.git(self.seed, "rev-parse", "HEAD")

    def branch(self, name: str) -> str:
        self.git(self.repo, "switch", "-c", name)
        (self.repo / "change.txt").write_text(name, encoding="utf-8")
        self.git(self.repo, "add", "change.txt")
        self.git(self.repo, "commit", "-m", name)
        head = self.git(self.repo, "rev-parse", "HEAD")
        self.git(self.repo, "push", "-u", "origin", name)
        self.git(self.repo, "switch", self.default)
        return head

    def delete_remote(self, name: str) -> None:
        self.git(self.seed, "push", "origin", "--delete", name)


class GitHubRunner:
    def __init__(
        self, payload, remote_url="https://github.com/owner/repo.git", rules=()
    ):
        self.payload = {
            "headRepository": {"nameWithOwner": "owner/repo"},
            **payload,
        }
        self.remote_url = remote_url
        self.rules = list(rules)

    def __call__(self, command, cwd, timeout=30):
        if command[:3] == ["gh", "pr", "view"]:
            return subprocess.CompletedProcess(command, 0, json.dumps(self.payload), "")
        if command[:3] == ["git", "remote", "get-url"]:
            return subprocess.CompletedProcess(command, 0, self.remote_url + "\n", "")
        if command[:2] == ["gh", "api"]:
            return subprocess.CompletedProcess(command, 0, json.dumps(self.rules), "")
        return subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )


def merged(number: int, branch: str, head: str, base: str) -> dict:
    return {
        "number": number,
        "state": "MERGED",
        "mergedAt": "2026-07-24T00:00:00Z",
        "headRefName": branch,
        "headRefOid": head,
        "baseRefName": base,
    }


class GitLifecycleTests(unittest.TestCase):
    def test_stale_default_fast_forwards_and_preparation_detects_new_remote_work(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Repository(Path(directory))
            remote_head = fixture.advance()
            result = synchronize_default(fixture.repo)
            self.assertEqual(("origin", "trunk"), (result.primary_remote, result.default_branch))
            self.assertEqual(remote_head, result.implementation_base)
            self.assertEqual(remote_head, fixture.git(fixture.repo, "rev-parse", "HEAD"))
            fixture.advance("later\n")
            with self.assertRaisesRegex(GitLifecycleError, "base is stale"):
                validate_preparation(result, fixture.repo)

    def test_dirty_and_diverged_canonical_checkouts_block(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Repository(Path(directory))
            (fixture.repo / "dirty").write_text("dirty", encoding="utf-8")
            with self.assertRaisesRegex(GitLifecycleError, "dirty"):
                synchronize_default(fixture.repo)
        with tempfile.TemporaryDirectory() as directory:
            fixture = Repository(Path(directory))
            (fixture.repo / "local").write_text("local", encoding="utf-8")
            fixture.git(fixture.repo, "add", "local")
            fixture.git(fixture.repo, "commit", "-m", "local")
            fixture.advance()
            with self.assertRaisesRegex(GitLifecycleError, "fast-forwarded"):
                synchronize_default(fixture.repo)

    def test_new_worktree_starts_at_the_synchronized_remote_base(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Repository(Path(directory))
            remote_head = fixture.advance()
            sync = synchronize_default(fixture.repo)
            worktree = fixture.root / "issue"
            fixture.git(
                fixture.repo,
                "worktree",
                "add",
                "-b",
                "codex/issue-17",
                str(worktree),
                sync.implementation_base,
            )
            self.assertEqual(remote_head, fixture.git(worktree, "rev-parse", "HEAD"))

    def test_primary_remote_and_default_are_discovered_with_multiple_remotes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = Repository(root / "upstream")
            fork = Repository(root / "fork", "main")
            fixture.git(fixture.repo, "remote", "rename", "origin", "upstream")
            fixture.git(fixture.repo, "remote", "add", "origin", str(fork.remote))
            expected = fixture.advance("upstream\n")
            result = synchronize_default(fixture.repo)
            self.assertEqual(("upstream", "trunk"), (result.primary_remote, result.default_branch))
            self.assertEqual(expected, result.implementation_base)

    def test_squash_or_rebase_cleanup_requires_exact_github_head(self):
        for exact in (True, False):
            with self.subTest(exact=exact), tempfile.TemporaryDirectory() as directory:
                fixture = Repository(Path(directory))
                branch = "codex/outcome"
                head = fixture.branch(branch)
                fixture.delete_remote(branch)
                proof_head = head if exact else "f" * 40
                result = cleanup_merged_outcome(
                    fixture.repo,
                    "owner/repo",
                    CleanupRequest(42, branch, str(fixture.repo), True),
                    runner=GitHubRunner(merged(42, branch, proof_head, fixture.default)),
                )
                self.assertEqual(
                    "deleted_github_confirmed" if exact else "skipped_diverged_branch",
                    result.cleanup,
                )
                self.assertEqual(
                    not exact, bool(fixture.git(fixture.repo, "branch", "--list", branch))
                )

    def test_clean_recorded_worktree_is_removed_before_its_merged_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Repository(Path(directory))
            branch = "codex/linked"
            head = fixture.branch(branch)
            linked = fixture.root / "linked"
            fixture.git(fixture.repo, "worktree", "add", str(linked), branch)
            fixture.delete_remote(branch)
            result = cleanup_merged_outcome(
                fixture.repo,
                "owner/repo",
                CleanupRequest(43, branch, str(linked), True),
                runner=GitHubRunner(merged(43, branch, head, fixture.default)),
            )
            self.assertEqual("deleted_github_confirmed", result.cleanup)
            self.assertFalse(linked.exists())
            self.assertFalse(fixture.git(fixture.repo, "branch", "--list", branch))

    def test_preparation_from_another_repository_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Repository(Path(directory) / "first")
            second = Repository(Path(directory) / "second")
            preparation = synchronize_default(first.repo)
            with self.assertRaisesRegex(GitLifecycleError, "different repository"):
                validate_preparation(preparation, second.repo)

    def test_active_or_unverified_branches_are_left_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Repository(Path(directory))
            branch = "codex/active"
            head = fixture.branch(branch)
            linked = fixture.root / "linked"
            fixture.git(fixture.repo, "worktree", "add", str(linked), branch)
            fixture.delete_remote(branch)
            active = cleanup_merged_outcome(
                fixture.repo,
                "owner/repo",
                CleanupRequest(44, branch, str(fixture.repo), True),
                runner=GitHubRunner(merged(44, branch, head, fixture.default)),
            )
            self.assertEqual("skipped_checked_out_worktree", active.cleanup)
            self.assertTrue(linked.exists())

        with tempfile.TemporaryDirectory() as directory:
            fixture = Repository(Path(directory))
            branch = "codex/unverified"
            head = fixture.branch(branch)
            fixture.delete_remote(branch)
            payload = {**merged(45, branch, head, fixture.default), "state": "OPEN"}
            unverified = cleanup_merged_outcome(
                fixture.repo,
                "owner/repo",
                CleanupRequest(45, branch, str(fixture.repo), True),
                runner=GitHubRunner(payload),
            )
            self.assertEqual("skipped_unverified_pull_request", unverified.cleanup)
            self.assertTrue(fixture.git(fixture.repo, "branch", "--list", branch))

    def test_no_authority_syncs_but_preserves_the_local_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Repository(Path(directory))
            branch = "codex/no-authority"
            head = fixture.branch(branch)
            fixture.delete_remote(branch)
            fixture.advance()
            result = cleanup_merged_outcome(
                fixture.repo,
                "owner/repo",
                CleanupRequest(46, branch, str(fixture.repo), False),
                runner=GitHubRunner(merged(46, branch, head, fixture.default)),
            )
            self.assertEqual("skipped_not_authorized", result.cleanup)
            self.assertEqual(
                fixture.git(fixture.seed, "rev-parse", "HEAD"),
                fixture.git(fixture.repo, "rev-parse", "HEAD"),
            )

    def test_protected_or_dirty_outcomes_are_preserved(self):
        for protected in (True, False):
            with self.subTest(protected=protected), tempfile.TemporaryDirectory() as directory:
                fixture = Repository(Path(directory))
                branch = "codex/protected" if protected else "codex/dirty"
                head = fixture.branch(branch)
                linked = fixture.root / "linked"
                fixture.git(fixture.repo, "worktree", "add", str(linked), branch)
                if not protected:
                    (linked / "dirty").write_text("dirty", encoding="utf-8")
                fixture.delete_remote(branch)
                result = cleanup_merged_outcome(
                    fixture.repo,
                    "owner/repo",
                    CleanupRequest(47, branch, str(linked), True),
                    runner=GitHubRunner(
                        merged(47, branch, head, fixture.default),
                        rules=({"type": "deletion"},) if protected else (),
                    ),
                )
                self.assertEqual(
                    "skipped_protected_branch" if protected else "skipped_dirty_worktree",
                    result.cleanup,
                )
                self.assertTrue(linked.exists())

    def test_runtime_documents_explicit_lifecycle_and_no_complete_hook(self):
        text = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in (
                "skills/start/SKILL.md",
                "skills/resolve/SKILL.md",
                "skills/close/SKILL.md",
                "docs/project-truss/README.md",
            )
        )
        for phrase in (
            "-Action Prepare",
            "PreparationJson",
            "-Action Cleanup",
            "post-fetch",
            "post-merge",
        ):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
