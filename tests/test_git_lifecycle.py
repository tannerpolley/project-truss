from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.lib.command_support import Context, ScriptError
from scripts.lib.commands.project import command_project_truss
from scripts.lib.git_lifecycle import (
    CleanupRequest,
    CleanupResult,
    GitLifecycleError,
    GitSyncResult,
    cleanup_merged_outcome,
    synchronize_default,
)

ROOT = Path(__file__).resolve().parents[1]


class FakeGitHubRunner:
    def __init__(
        self,
        payload,
        *,
        remote_url="https://github.com/owner/repo.git",
        rules=(),
        before_delete=None,
    ):
        self.payload = {
            "headRepository": {"nameWithOwner": "owner/repo"},
            **payload,
        }
        self.remote_url = remote_url
        self.rules = list(rules)
        self.before_delete = before_delete

    def __call__(self, command, cwd, timeout=30):
        if command[:3] == ["gh", "pr", "view"]:
            return subprocess.CompletedProcess(
                command, 0, stdout=json.dumps(self.payload), stderr=""
            )
        if command[:3] == ["git", "remote", "get-url"]:
            return subprocess.CompletedProcess(
                command, 0, stdout=f"{self.remote_url}\n", stderr=""
            )
        if command[:2] == ["gh", "api"]:
            return subprocess.CompletedProcess(
                command, 0, stdout=json.dumps(self.rules), stderr=""
            )
        if command[:3] == ["git", "update-ref", "-d"] and self.before_delete:
            callback, self.before_delete = self.before_delete, None
            callback()
        return subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )


class GitRepositoryFixture:
    def __init__(self, root: Path, *, default_branch: str = "trunk"):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.default_branch = default_branch
        self.remote = root / "remote.git"
        self.seed = root / "seed"
        self.repo = root / "repo"
        self.git(root, "init", "--bare", f"--initial-branch={default_branch}", str(self.remote))
        self.git(root, "clone", str(self.remote), str(self.seed))
        self.configure(self.seed)
        (self.seed / "README.md").write_text("base\n", encoding="utf-8")
        self.git(self.seed, "add", "README.md")
        self.git(self.seed, "commit", "-m", "base")
        self.git(self.seed, "push", "-u", "origin", default_branch)
        self.git(root, "clone", str(self.remote), str(self.repo))
        self.configure(self.repo)

    @staticmethod
    def git(cwd: Path, *args: str, check: bool = True) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
        if check and result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return result.stdout.strip()

    def configure(self, repo: Path) -> None:
        self.git(repo, "config", "user.name", "Project Truss Test")
        self.git(repo, "config", "user.email", "project-truss@example.com")

    def advance_remote(self, text: str = "remote\n") -> str:
        (self.seed / "README.md").write_text(text, encoding="utf-8")
        self.git(self.seed, "add", "README.md")
        self.git(self.seed, "commit", "-m", text.strip())
        self.git(self.seed, "push", "origin", self.default_branch)
        return self.git(self.seed, "rev-parse", "HEAD")

    def create_remote_branch(self, branch: str) -> str:
        self.git(self.repo, "switch", "-c", branch)
        path = self.repo / f"{branch.replace('/', '-')}.txt"
        path.write_text(f"{branch}\n", encoding="utf-8")
        self.git(self.repo, "add", path.name)
        self.git(self.repo, "commit", "-m", branch)
        head = self.git(self.repo, "rev-parse", "HEAD")
        self.git(self.repo, "push", "-u", "origin", branch)
        self.git(self.repo, "switch", self.default_branch)
        return head

    def delete_remote_branch(self, branch: str) -> None:
        self.git(self.seed, "push", "origin", "--delete", branch)


class GitLifecycleTests(unittest.TestCase):
    def command(self, args):
        context = Context(
            Path(__file__),
            Path.cwd(),
            "scripts/project-truss.sh",
            "project-truss.sh",
            [],
            invocation_cwd=Path.cwd(),
        )
        stream = StringIO()
        with redirect_stdout(stream):
            code = command_project_truss(context, args)
        return code, json.loads(stream.getvalue())

    def test_prepare_and_cleanup_actions_expose_the_git_lifecycle(self):
        sync = GitSyncResult(
            "/repo", "upstream", "trunk", "refs/remotes/upstream/trunk", "a" * 40
        )
        cleanup = CleanupResult(
            "/repo",
            "upstream",
            "trunk",
            "b" * 40,
            "deleted_github_confirmed",
            "deleted squash/rebase branch using exact merged pull request proof",
        )
        with patch(
            "scripts.lib.commands.project.synchronize_default", return_value=sync
        ):
            code, payload = self.command({"Action": "Prepare", "RepoRoot": "."})
        self.assertEqual((0, True, "Prepare"), (code, payload["ok"], payload["action"]))
        self.assertEqual("a" * 40, payload["implementation_base"])

        request = {
            "pull_request": 42,
            "branch": "codex/issue-17",
            "worktree": "/repo/worktree",
            "cleanup_authorized": True,
        }
        with patch(
            "scripts.lib.commands.project.cleanup_merged_outcome",
            return_value=cleanup,
        ):
            code, payload = self.command(
                {
                    "Action": "Cleanup",
                    "RepoRoot": ".",
                    "Repository": "owner/repo",
                    "CleanupJson": json.dumps(request),
                }
            )
        self.assertEqual((0, True, "Cleanup"), (code, payload["ok"], payload["action"]))
        self.assertEqual("deleted_github_confirmed", payload["cleanup"])

    def test_resolve_rejects_an_invocation_cwd_outside_the_recorded_worktree(self):
        context = Context(
            Path(__file__),
            Path.cwd(),
            "scripts/project-truss.sh",
            "project-truss.sh",
            [],
            invocation_cwd=Path.cwd().parent,
        )
        receipt = {
            "issues": [17],
            "owner": "tannerpolley",
            "implementation_base": "a" * 40,
            "branch": "codex/issue-17",
            "worktree": str(Path.cwd()),
            "pull_request": None,
        }
        with self.assertRaisesRegex(ScriptError, "invocation cwd"):
            command_project_truss(
                context,
                {
                    "Action": "Resolve",
                    "RepoRoot": str(Path.cwd()),
                    "Repository": "owner/repo",
                    "Issue": 17,
                    "ResolutionJson": json.dumps(receipt),
                },
            )

    def test_initial_resolve_requires_prepare_evidence(self):
        root = Path.cwd()
        context = Context(
            Path(__file__),
            root,
            "scripts/project-truss.sh",
            "project-truss.sh",
            [],
            invocation_cwd=root,
        )
        receipt = {
            "issues": [17],
            "owner": "tannerpolley",
            "implementation_base": subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                text=True,
                check=True,
                capture_output=True,
            ).stdout.strip(),
            "branch": subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=root,
                text=True,
                check=True,
                capture_output=True,
            ).stdout.strip(),
            "worktree": str(root),
            "pull_request": None,
        }
        with self.assertRaisesRegex(ScriptError, "PreparationJson"):
            command_project_truss(
                context,
                {
                    "Action": "Resolve",
                    "Repository": "owner/repo",
                    "Issue": 17,
                    "ResolutionJson": json.dumps(receipt),
                },
            )

    def test_runtime_surfaces_publish_prepare_cleanup_and_hook_boundaries(self):
        start = (ROOT / "skills/start/SKILL.md").read_text(encoding="utf-8")
        resolve = (ROOT / "skills/resolve/SKILL.md").read_text(encoding="utf-8")
        close = (ROOT / "skills/close/SKILL.md").read_text(encoding="utf-8")
        runtime = (ROOT / "docs/project-truss/README.md").read_text(encoding="utf-8")

        self.assertIn("-Action Prepare", start)
        self.assertIn("-Action Prepare", resolve)
        self.assertIn("PreparationJson", resolve)
        self.assertIn("-Action Cleanup", close)
        self.assertIn("-Action Prepare", runtime)
        self.assertIn("-Action Cleanup", runtime)
        self.assertIn("post-fetch", runtime)
        self.assertIn("post-merge", runtime)

    def test_stale_default_fast_forwards_and_returns_remote_base(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = GitRepositoryFixture(Path(directory))
            remote_head = fixture.advance_remote()

            result = synchronize_default(fixture.repo)

            self.assertEqual("origin", result.primary_remote)
            self.assertEqual("trunk", result.default_branch)
            self.assertEqual(remote_head, result.implementation_base)
            self.assertEqual(remote_head, fixture.git(fixture.repo, "rev-parse", "HEAD"))

    def test_up_to_date_default_synchronizes_without_changing_the_base(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = GitRepositoryFixture(Path(directory))
            original = fixture.git(fixture.repo, "rev-parse", "HEAD")

            result = synchronize_default(fixture.repo)

            self.assertEqual(original, result.implementation_base)
            self.assertEqual(original, fixture.git(fixture.repo, "rev-parse", "HEAD"))

    def test_dirty_and_diverged_canonical_checkouts_are_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = GitRepositoryFixture(Path(directory))
            (fixture.repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            with self.assertRaisesRegex(GitLifecycleError, "canonical checkout is dirty"):
                synchronize_default(fixture.repo)

        with tempfile.TemporaryDirectory() as directory:
            fixture = GitRepositoryFixture(Path(directory))
            (fixture.repo / "local.txt").write_text("local\n", encoding="utf-8")
            fixture.git(fixture.repo, "add", "local.txt")
            fixture.git(fixture.repo, "commit", "-m", "local")
            fixture.advance_remote()
            with self.assertRaisesRegex(GitLifecycleError, "cannot be fast-forwarded"):
                synchronize_default(fixture.repo)

    def test_worktree_branch_can_be_created_from_synchronized_remote_base(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = GitRepositoryFixture(Path(directory))
            remote_head = fixture.advance_remote()
            result = synchronize_default(fixture.repo)
            worktree = fixture.root / "issue-worktree"

            fixture.git(
                fixture.repo,
                "worktree",
                "add",
                "-b",
                "codex/issue-17",
                str(worktree),
                result.implementation_base,
            )

            self.assertEqual(remote_head, fixture.git(worktree, "rev-parse", "HEAD"))
            self.assertEqual(
                "codex/issue-17", fixture.git(worktree, "branch", "--show-current")
            )

    def test_primary_remote_and_default_branch_are_discovered_with_multiple_remotes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = GitRepositoryFixture(root / "upstream", default_branch="trunk")
            fork = GitRepositoryFixture(root / "fork", default_branch="main")
            fixture.git(fixture.repo, "remote", "rename", "origin", "upstream")
            fixture.git(fixture.repo, "remote", "add", "origin", str(fork.remote))
            remote_head = fixture.advance_remote("upstream\n")

            result = synchronize_default(fixture.repo)

            self.assertEqual("upstream", result.primary_remote)
            self.assertEqual("trunk", result.default_branch)
            self.assertEqual(remote_head, result.implementation_base)

    def test_squash_and_rebase_branches_use_exact_merged_pr_proof(self):
        for mode in ("squash", "rebase"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                fixture = GitRepositoryFixture(Path(directory))
                branch = f"codex/{mode}-merge"
                head = fixture.create_remote_branch(branch)
                fixture.delete_remote_branch(branch)
                runner = FakeGitHubRunner(
                    {
                        "number": 42,
                        "state": "MERGED",
                        "mergedAt": "2026-07-24T00:00:00Z",
                        "headRefName": branch,
                        "headRefOid": head,
                        "baseRefName": fixture.default_branch,
                        "url": "https://github.example/pull/42",
                    }
                )

                result = cleanup_merged_outcome(
                    fixture.repo,
                    "owner/repo",
                    CleanupRequest(42, branch, str(fixture.repo), True),
                    runner=runner,
                )

                self.assertEqual("deleted_github_confirmed", result.cleanup)
                self.assertEqual(
                    "",
                    fixture.git(
                        fixture.repo,
                        "branch",
                        "--list",
                        branch,
                    ),
                )

    def test_active_worktrees_and_unverified_deleted_branches_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = GitRepositoryFixture(Path(directory))
            branch = "codex/active"
            head = fixture.create_remote_branch(branch)
            linked = fixture.root / "linked"
            fixture.git(fixture.repo, "worktree", "add", str(linked), branch)
            fixture.delete_remote_branch(branch)
            runner = FakeGitHubRunner(
                {
                    "number": 43,
                    "state": "MERGED",
                    "mergedAt": "2026-07-24T00:00:00Z",
                    "headRefName": branch,
                    "headRefOid": head,
                    "baseRefName": fixture.default_branch,
                    "url": "https://github.example/pull/43",
                }
            )

            result = cleanup_merged_outcome(
                fixture.repo,
                "owner/repo",
                CleanupRequest(43, branch, str(fixture.repo), True),
                runner=runner,
            )

            self.assertEqual("skipped_checked_out_worktree", result.cleanup)
            self.assertEqual(branch, fixture.git(linked, "branch", "--show-current"))

        with tempfile.TemporaryDirectory() as directory:
            fixture = GitRepositoryFixture(Path(directory))
            branch = "codex/diverged-worktree"
            head = fixture.create_remote_branch(branch)
            linked = fixture.root / "linked"
            fixture.git(fixture.repo, "worktree", "add", str(linked), branch)
            (linked / "later.txt").write_text("later\n", encoding="utf-8")
            fixture.git(linked, "add", "later.txt")
            fixture.git(linked, "commit", "-m", "later")
            fixture.delete_remote_branch(branch)
            runner = FakeGitHubRunner(
                {
                    "number": 46,
                    "state": "MERGED",
                    "mergedAt": "2026-07-24T00:00:00Z",
                    "headRefName": branch,
                    "headRefOid": head,
                    "baseRefName": fixture.default_branch,
                    "url": "https://github.example/pull/46",
                }
            )
            result = cleanup_merged_outcome(
                fixture.repo,
                "owner/repo",
                CleanupRequest(46, branch, str(linked), True),
                runner=runner,
            )
            self.assertEqual("skipped_diverged_branch", result.cleanup)
            self.assertTrue(linked.exists())

        with tempfile.TemporaryDirectory() as directory:
            fixture = GitRepositoryFixture(Path(directory))
            branch = "codex/unverified"
            head = fixture.create_remote_branch(branch)
            fixture.delete_remote_branch(branch)
            runner = FakeGitHubRunner(
                {
                    "number": 44,
                    "state": "OPEN",
                    "mergedAt": None,
                    "headRefName": branch,
                    "headRefOid": head,
                    "baseRefName": fixture.default_branch,
                    "url": "https://github.example/pull/44",
                }
            )

            result = cleanup_merged_outcome(
                fixture.repo,
                "owner/repo",
                CleanupRequest(44, branch, str(fixture.repo), True),
                runner=runner,
            )
            self.assertEqual("skipped_unverified_pull_request", result.cleanup)
            self.assertEqual(
                branch,
                fixture.git(fixture.repo, "branch", "--list", branch).lstrip("* "),
            )

    def test_non_github_primary_remote_is_synchronized_but_not_cleaned(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = GitRepositoryFixture(Path(directory))
            branch = "codex/non-github"
            head = fixture.create_remote_branch(branch)
            fixture.delete_remote_branch(branch)
            runner = FakeGitHubRunner(
                {
                    "number": 45,
                    "state": "MERGED",
                    "mergedAt": "2026-07-24T00:00:00Z",
                    "headRefName": branch,
                    "headRefOid": head,
                    "baseRefName": fixture.default_branch,
                    "url": "https://github.example/pull/45",
                },
                remote_url=str(fixture.remote),
            )

            result = cleanup_merged_outcome(
                fixture.repo,
                "owner/repo",
                CleanupRequest(45, branch, str(fixture.repo), True),
                runner=runner,
            )

            self.assertEqual("skipped_non_github_remote", result.cleanup)
            self.assertEqual(
                branch,
                fixture.git(fixture.repo, "branch", "--list", branch).lstrip("* "),
            )

    def test_prepare_blocks_ahead_detached_ambiguous_and_noncanonical_checkouts(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = GitRepositoryFixture(Path(directory))
            (fixture.repo / "ahead.txt").write_text("ahead\n", encoding="utf-8")
            fixture.git(fixture.repo, "add", "ahead.txt")
            fixture.git(fixture.repo, "commit", "-m", "ahead")
            with self.assertRaisesRegex(GitLifecycleError, "exact remote state"):
                synchronize_default(fixture.repo)

        with tempfile.TemporaryDirectory() as directory:
            fixture = GitRepositoryFixture(Path(directory))
            fixture.git(fixture.repo, "switch", "--detach")
            with self.assertRaisesRegex(GitLifecycleError, "not on the discovered default"):
                synchronize_default(fixture.repo)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = GitRepositoryFixture(root / "primary")
            mirror = GitRepositoryFixture(root / "mirror", default_branch="main")
            fixture.git(fixture.repo, "remote", "add", "mirror", str(mirror.remote))
            fixture.git(fixture.repo, "fetch", "mirror")
            fixture.git(fixture.repo, "branch", "main", "mirror/main")
            fixture.git(fixture.repo, "config", "branch.main.remote", "mirror")
            fixture.git(fixture.repo, "config", "branch.main.merge", "refs/heads/main")
            with self.assertRaisesRegex(GitLifecycleError, "ambiguous or untracked"):
                synchronize_default(fixture.repo)

        with tempfile.TemporaryDirectory() as directory:
            fixture = GitRepositoryFixture(Path(directory))
            linked = fixture.root / "linked"
            fixture.git(
                fixture.repo, "worktree", "add", "-b", "codex/linked", str(linked)
            )
            with self.assertRaisesRegex(GitLifecycleError, "canonical checkout"):
                synchronize_default(linked)

    def test_cleanup_skips_remote_present_no_authority_protected_and_dirty_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = GitRepositoryFixture(Path(directory))
            branch = "codex/present"
            head = fixture.create_remote_branch(branch)
            runner = FakeGitHubRunner(
                {
                    "number": 50,
                    "state": "MERGED",
                    "mergedAt": "2026-07-24T00:00:00Z",
                    "headRefName": branch,
                    "headRefOid": head,
                    "baseRefName": fixture.default_branch,
                    "url": "https://github.example/pull/50",
                }
            )
            with self.assertRaisesRegex(GitLifecycleError, "still exists"):
                cleanup_merged_outcome(
                    fixture.repo,
                    "owner/repo",
                    CleanupRequest(50, branch, str(fixture.repo), True),
                    runner=runner,
                )

        for expected, authorized, rules in (
            ("skipped_not_authorized", False, ()),
            ("skipped_protected_branch", True, ({"type": "deletion"},)),
        ):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                fixture = GitRepositoryFixture(Path(directory))
                branch = f"codex/{expected}"
                head = fixture.create_remote_branch(branch)
                fixture.delete_remote_branch(branch)
                runner = FakeGitHubRunner(
                    {
                        "number": 51,
                        "state": "MERGED",
                        "mergedAt": "2026-07-24T00:00:00Z",
                        "headRefName": branch,
                        "headRefOid": head,
                        "baseRefName": fixture.default_branch,
                        "url": "https://github.example/pull/51",
                    },
                    rules=rules,
                )
                result = cleanup_merged_outcome(
                    fixture.repo,
                    "owner/repo",
                    CleanupRequest(51, branch, str(fixture.repo), authorized),
                    runner=runner,
                )
                self.assertEqual(expected, result.cleanup)

        with tempfile.TemporaryDirectory() as directory:
            fixture = GitRepositoryFixture(Path(directory))
            branch = "codex/dirty-worktree"
            head = fixture.create_remote_branch(branch)
            linked = fixture.root / "linked"
            fixture.git(fixture.repo, "worktree", "add", str(linked), branch)
            (linked / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            fixture.delete_remote_branch(branch)
            runner = FakeGitHubRunner(
                {
                    "number": 52,
                    "state": "MERGED",
                    "mergedAt": "2026-07-24T00:00:00Z",
                    "headRefName": branch,
                    "headRefOid": head,
                    "baseRefName": fixture.default_branch,
                    "url": "https://github.example/pull/52",
                }
            )
            result = cleanup_merged_outcome(
                fixture.repo,
                "owner/repo",
                CleanupRequest(52, branch, str(linked), True),
                runner=runner,
            )
            self.assertEqual("skipped_dirty_worktree", result.cleanup)
            self.assertTrue(linked.exists())

    def test_graph_merge_and_concurrent_branch_move_use_compare_and_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = GitRepositoryFixture(Path(directory))
            branch = "codex/graph"
            head = fixture.create_remote_branch(branch)
            fixture.git(fixture.repo, "merge", "--ff-only", branch)
            fixture.git(fixture.repo, "push", "origin", fixture.default_branch)
            fixture.delete_remote_branch(branch)
            runner = FakeGitHubRunner(
                {
                    "number": 53,
                    "state": "MERGED",
                    "mergedAt": "2026-07-24T00:00:00Z",
                    "headRefName": branch,
                    "headRefOid": head,
                    "baseRefName": fixture.default_branch,
                    "url": "https://github.example/pull/53",
                }
            )
            result = cleanup_merged_outcome(
                fixture.repo,
                "owner/repo",
                CleanupRequest(53, branch, str(fixture.repo), True),
                runner=runner,
            )
            self.assertEqual("deleted_graph_merged", result.cleanup)

        with tempfile.TemporaryDirectory() as directory:
            fixture = GitRepositoryFixture(Path(directory))
            branch = "codex/race"
            head = fixture.create_remote_branch(branch)
            fixture.delete_remote_branch(branch)
            moved = fixture.advance_remote("moved\n")
            runner = FakeGitHubRunner(
                {
                    "number": 54,
                    "state": "MERGED",
                    "mergedAt": "2026-07-24T00:00:00Z",
                    "headRefName": branch,
                    "headRefOid": head,
                    "baseRefName": fixture.default_branch,
                    "url": "https://github.example/pull/54",
                },
                before_delete=lambda: fixture.git(
                    fixture.repo, "branch", "-f", branch, moved
                ),
            )
            result = cleanup_merged_outcome(
                fixture.repo,
                "owner/repo",
                CleanupRequest(54, branch, str(fixture.repo), True),
                runner=runner,
            )
            self.assertEqual("skipped_diverged_branch", result.cleanup)
            self.assertEqual(moved, fixture.git(fixture.repo, "rev-parse", branch))

    def test_fork_pull_request_head_is_not_accepted_as_primary_remote_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = GitRepositoryFixture(Path(directory))
            branch = "codex/fork"
            head = fixture.create_remote_branch(branch)
            fixture.delete_remote_branch(branch)
            runner = FakeGitHubRunner(
                {
                    "number": 55,
                    "state": "MERGED",
                    "mergedAt": "2026-07-24T00:00:00Z",
                    "headRefName": branch,
                    "headRefOid": head,
                    "baseRefName": fixture.default_branch,
                    "headRepository": {"nameWithOwner": "fork/repo"},
                    "url": "https://github.example/pull/55",
                }
            )
            result = cleanup_merged_outcome(
                fixture.repo,
                "owner/repo",
                CleanupRequest(55, branch, str(fixture.repo), True),
                runner=runner,
            )
            self.assertEqual("skipped_unverified_pull_request", result.cleanup)


if __name__ == "__main__":
    unittest.main()
