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
        self.remote, self.seed, self.repo = root / "remote.git", root / "seed", root / "repo"
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
        result = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True)
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

    def delete_remote(self, branch: str) -> None:
        self.git(self.seed, "push", "origin", "--delete", branch)


class GitHubRunner:
    def __init__(self, payload, *, rules=(), fail_remove=False):
        self.payload = {"headRepository": {"nameWithOwner": "owner/repo"}, **payload}
        self.rules, self.fail_remove = list(rules), fail_remove

    def __call__(self, command, cwd, timeout=30):
        if command[:3] == ["gh", "pr", "view"]:
            return subprocess.CompletedProcess(command, 0, json.dumps(self.payload), "")
        if command[:3] == ["git", "remote", "get-url"]:
            return subprocess.CompletedProcess(command, 0, "https://github.com/owner/repo.git\n", "")
        if command[:2] == ["gh", "api"]:
            return subprocess.CompletedProcess(command, 0, json.dumps(self.rules), "")
        if self.fail_remove and command[:3] == ["git", "worktree", "remove"]:
            return subprocess.CompletedProcess(command, 1, "", "simulated removal failure")
        return subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def merged(number: int, branch: str, head: str, base: str, *, state="MERGED") -> dict:
    return {
        "number": number,
        "state": state,
        "mergedAt": "2026-07-24T00:00:00Z",
        "headRefName": branch,
        "headRefOid": head,
        "baseRefName": base,
    }


class GitLifecycleTests(unittest.TestCase):
    def cleanup(self, fixture, number, branch, head, worktree=None, **runner):
        request = CleanupRequest(number, branch, str(worktree or fixture.repo), True)
        proof = merged(number, branch, head, fixture.default)
        return cleanup_merged_outcome(
            fixture.repo, "owner/repo", request, runner=GitHubRunner(proof, **runner)
        )

    def test_prepare_syncs_exact_base_and_revalidation_detects_staleness(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Repository(Path(directory))
            remote_head = fixture.advance()
            result = synchronize_default(fixture.repo)
            self.assertEqual(("origin", "trunk", remote_head), (
                result.primary_remote, result.default_branch, result.implementation_base))
            worktree = fixture.root / "issue"
            fixture.git(fixture.repo, "worktree", "add", "-b", "codex/issue", str(worktree),
                        result.implementation_base)
            self.assertEqual(remote_head, fixture.git(worktree, "rev-parse", "HEAD"))
            fixture.git(fixture.repo, "worktree", "remove", str(worktree))
            fixture.advance("later\n")
            with self.assertRaisesRegex(GitLifecycleError, "base is stale"):
                validate_preparation(result, fixture.repo)

    def test_dirty_diverged_and_foreign_checkouts_block(self):
        for mode in ("dirty", "diverged"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                fixture = Repository(Path(directory))
                (fixture.repo / mode).write_text(mode, encoding="utf-8")
                if mode == "diverged":
                    fixture.git(fixture.repo, "add", mode)
                    fixture.git(fixture.repo, "commit", "-m", mode)
                    fixture.advance()
                with self.assertRaisesRegex(GitLifecycleError, mode if mode == "dirty" else "fast-forwarded"):
                    synchronize_default(fixture.repo)
        with tempfile.TemporaryDirectory() as directory:
            first, second = Repository(Path(directory) / "first"), Repository(Path(directory) / "second")
            with self.assertRaisesRegex(GitLifecycleError, "different repository"):
                validate_preparation(synchronize_default(first.repo), second.repo)

    def test_multiple_remotes_use_the_tracked_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture, fork = Repository(root / "upstream"), Repository(root / "fork", "main")
            fixture.git(fixture.repo, "remote", "rename", "origin", "upstream")
            fixture.git(fixture.repo, "remote", "add", "origin", str(fork.remote))
            expected = fixture.advance("upstream\n")
            result = synchronize_default(fixture.repo)
            self.assertEqual(("upstream", "trunk", expected), (
                result.primary_remote, result.default_branch, result.implementation_base))

    def test_cleanup_requires_exact_merged_github_head(self):
        for head_matches, state, expected in (
            (True, "MERGED", "deleted_github_confirmed"),
            (False, "MERGED", "skipped_diverged_branch"),
            (True, "OPEN", "skipped_unverified_pull_request"),
        ):
            with self.subTest(head_matches=head_matches, state=state), tempfile.TemporaryDirectory() as directory:
                fixture, branch = Repository(Path(directory)), "codex/outcome"
                head = fixture.branch(branch)
                fixture.delete_remote(branch)
                proof = merged(42, branch, head if head_matches else "f" * 40, fixture.default, state=state)
                request = CleanupRequest(42, branch, str(fixture.repo), True)
                result = cleanup_merged_outcome(
                    fixture.repo, "owner/repo", request, runner=GitHubRunner(proof))
                self.assertEqual(expected, result["cleanup"])
                self.assertEqual(expected != "deleted_github_confirmed",
                                 bool(fixture.git(fixture.repo, "branch", "--list", branch)))

    def test_linked_worktree_cleanup_rolls_back_if_removal_fails(self):
        for remove_fails in (False, True):
            with self.subTest(remove_fails=remove_fails), tempfile.TemporaryDirectory() as directory:
                fixture, branch = Repository(Path(directory)), "codex/linked"
                head, linked = fixture.branch(branch), fixture.root / "linked"
                fixture.git(fixture.repo, "worktree", "add", str(linked), branch)
                fixture.delete_remote(branch)
                result = self.cleanup(
                    fixture, 43, branch, head, linked, fail_remove=remove_fails)
                expected = "skipped_worktree_removal_failed" if remove_fails else "deleted_github_confirmed"
                self.assertEqual(expected, result["cleanup"])
                self.assertEqual(remove_fails, linked.exists())
                self.assertEqual(remove_fails, bool(fixture.git(fixture.repo, "branch", "--list", branch)))

    def test_active_protected_and_dirty_worktrees_are_preserved(self):
        for mode, expected in (
            ("active", "skipped_checked_out_worktree"),
            ("protected", "skipped_protected_branch"),
            ("dirty", "skipped_dirty_worktree"),
        ):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                fixture, branch = Repository(Path(directory)), f"codex/{mode}"
                head, linked = fixture.branch(branch), fixture.root / "linked"
                fixture.git(fixture.repo, "worktree", "add", str(linked), branch)
                if mode == "dirty":
                    (linked / "dirty").write_text("dirty", encoding="utf-8")
                fixture.delete_remote(branch)
                worktree = fixture.repo if mode == "active" else linked
                rules = ({"type": "deletion"},) if mode == "protected" else ()
                self.assertEqual(expected, self.cleanup(
                    fixture, 44, branch, head, worktree, rules=rules)["cleanup"])
                self.assertTrue(linked.exists())

    def test_no_cleanup_authority_still_synchronizes_default(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture, branch = Repository(Path(directory)), "codex/no-authority"
            head = fixture.branch(branch)
            fixture.delete_remote(branch)
            remote_head = fixture.advance()
            request = CleanupRequest(45, branch, str(fixture.repo), False)
            result = cleanup_merged_outcome(
                fixture.repo, "owner/repo", request,
                runner=GitHubRunner(merged(45, branch, head, fixture.default)))
            self.assertEqual(
                {"canonical_checkout", "primary_remote", "default_branch",
                 "implementation_base", "cleanup", "detail"}, set(result))
            self.assertEqual("skipped_not_authorized", result["cleanup"])
            self.assertEqual(remote_head, fixture.git(fixture.repo, "rev-parse", "HEAD"))
            self.assertTrue(fixture.git(fixture.repo, "branch", "--list", branch))

    def test_cleanup_can_return_a_clean_canonical_outcome_checkout_to_default(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture, branch = Repository(Path(directory)), "codex/current-outcome"
            head = fixture.branch(branch)
            fixture.git(fixture.repo, "switch", branch)
            fixture.delete_remote(branch)
            result = cleanup_merged_outcome(
                fixture.repo,
                "owner/repo",
                CleanupRequest(46, branch, None, True),
                runner=GitHubRunner(merged(46, branch, head, fixture.default)),
            )
            self.assertEqual("deleted_github_confirmed", result["cleanup"])
            self.assertEqual(fixture.default, fixture.git(fixture.repo, "branch", "--show-current"))
            self.assertFalse(fixture.git(fixture.repo, "branch", "--list", branch))

    def test_runtime_documents_explicit_lifecycle_and_hook_limits(self):
        text = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in (
            "skills/start/SKILL.md", "skills/resolve/SKILL.md", "skills/close/SKILL.md",
            "docs/project-truss/README.md"))
        for phrase in ("-Action Prepare", "PreparationJson", "-Action Cleanup", "post-fetch", "post-merge"):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
