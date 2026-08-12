from contextlib import redirect_stdout
from io import StringIO
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.lib.command_support import Context
from scripts.lib.command_support import ScriptError
from scripts.lib.commands.project import command_project_truss
from scripts.lib.truss_policy import (
    FinalHealth,
    OutcomeSnapshot,
    ResolutionReceipt,
    close_resolution_findings,
    plan_resolution,
)


ROOT = Path(__file__).resolve().parents[1]
LEAF_BODY = """## Parent

#10

## What to build

Ship one vertical slice.

## Acceptance criteria

- [ ] The slice is verified.

## Blocked by

None — can start immediately.
"""


def snapshot(
    number: int,
    *,
    assignees=(),
    blocked_by=(),
    closing_prs=(),
    comments=(),
    issue_state="OPEN",
    body=LEAF_BODY,
):
    return OutcomeSnapshot.from_mapping(
        {
            "authoritative": True,
            "observed_at": "2026-07-23T00:00:00Z",
            "repository": "tannerpolley/project-truss",
            "issue": {
                "number": number,
                "title": f"Leaf {number}",
                "state": issue_state,
                "body": body,
                "url": f"https://github.example/issues/{number}",
            },
            "assignees": list(assignees),
            "children": [],
            "blocked_by": list(blocked_by),
            "blocking": [],
            "closing_prs": list(closing_prs),
            "comments": list(comments),
            "source_urls": [f"https://github.example/issues/{number}"],
            "provider_findings": [],
            "parent": {
                "number": 10,
                "title": "Parent",
                "state": "OPEN",
                "url": "https://github.example/issues/10",
            },
        }
    )


def blocker(number: int):
    return {
        "number": number,
        "title": f"Blocker {number}",
        "state": "OPEN",
        "url": f"https://github.example/issues/{number}",
    }


def passing_pr(number=12, head="b" * 40):
    return {
        "number": number,
        "state": "MERGED",
        "url": f"https://github.example/pull/{number}",
        "merged": True,
        "merged_at": "2026-07-23T01:00:00Z",
        "head_sha": head,
        "checks_complete": True,
        "checks_successful": True,
        "review_decision": "APPROVED",
    }


def graphql_payload(number, receipt, *, closed=False):
    def connection(nodes):
        return {"nodes": nodes, "pageInfo": {"hasNextPage": False}}
    issue_url = f"https://github.example/issues/{number}"
    node = {
        "id": f"I_{number}", "number": number, "title": f"Leaf {number}",
        "state": "CLOSED" if closed else "OPEN",
        "body": LEAF_BODY.replace("[ ]", "[x]") if closed else LEAF_BODY,
        "url": issue_url, "updatedAt": "2026-07-23T00:00:00Z",
        "assignees": connection([{"login": "tannerpolley"}]), "milestone": None,
        "parent": {"number": 10, "title": "Parent", "state": "OPEN",
                   "url": "https://github.example/issues/10"},
        "subIssues": connection([]), "blockedBy": connection([]), "blocking": connection([]),
        "closedByPullRequestsReferences": connection([{"number": 12}] if closed else []),
        "comments": connection([{"author": {"login": "tannerpolley"},
                                 "body": receipt.comment(),
                                 "createdAt": "2026-07-23T00:00:00Z",
                                 "url": f"{issue_url}#comment"}]),
    }
    return {"data": {"repository": {"issue": node}}}


class ResolutionSetTests(unittest.TestCase):
    def test_explicit_set_allows_internal_blockers_and_rejects_external_blockers(self):
        receipt = ResolutionReceipt.from_mapping(
            {
                "issues": [9, 11],
                "owner": "tannerpolley",
                "implementation_base": "a" * 40,
                "branch": "codex/issue-10",
                "worktree": "/tmp/issue-10",
            }
        )
        internal = plan_resolution(
            [snapshot(9), snapshot(11, blocked_by=[blocker(9)])],
            receipt,
        )
        self.assertTrue(internal.eligible)
        self.assertEqual(((11, 9),), internal.internal_dependencies)
        self.assertEqual((), internal.blockers)

        external = plan_resolution(
            [snapshot(9), snapshot(11, blocked_by=[blocker(8)])],
            receipt,
        )
        self.assertFalse(external.eligible)
        self.assertEqual(("dependency_blocked",), external.blockers)
        self.assertEqual((8,), external.external_blockers)

    def test_recorded_resolution_receipts_must_match_every_selected_leaf(self):
        receipt = ResolutionReceipt.from_mapping(
            {
                "issues": [9, 11],
                "owner": "tannerpolley",
                "implementation_base": "a" * 40,
                "branch": "codex/issue-10",
                "worktree": "/tmp/issue-10",
            }
        )

        def comment(body, author="tannerpolley"):
            return {
                "author": author,
                "body": body,
                "created_at": "2026-07-23T00:00:00Z",
                "url": "https://github.example/comment/1",
            }

        matching = [
            snapshot(9, assignees=["tannerpolley"], comments=[comment(receipt.comment())]),
            snapshot(11, assignees=["tannerpolley"], comments=[comment(receipt.comment())]),
        ]
        self.assertTrue(plan_resolution(matching, receipt, require_recorded=True).eligible)

        partial_claim = [
            matching[0],
            snapshot(11, comments=[comment(receipt.comment())]),
        ]
        self.assertEqual(
            ("claim_conflict",),
            plan_resolution(partial_claim, receipt, require_recorded=True).blockers,
        )

        foreign_pr = [
            matching[0],
            snapshot(
                11,
                assignees=["tannerpolley"],
                closing_prs=[passing_pr(number=13)],
                comments=[comment(receipt.comment())],
            ),
        ]
        self.assertEqual(
            ("state_contradiction",),
            plan_resolution(foreign_pr, receipt, require_recorded=True).blockers,
        )

        foreign_receipt = [
            matching[0],
            snapshot(
                11,
                assignees=["tannerpolley"],
                comments=[comment(receipt.comment(), author="other-owner")],
            ),
        ]
        self.assertEqual(
            ("claim_conflict", "state_contradiction"),
            plan_resolution(foreign_receipt, receipt, require_recorded=True).blockers,
        )

        conflicting = ResolutionReceipt.from_mapping(
            {**receipt.to_dict(), "branch": "codex/different"}
        )
        mismatched = [
            matching[0],
            snapshot(
                11,
                assignees=["tannerpolley"],
                comments=[comment(conflicting.comment())],
            ),
        ]
        result = plan_resolution(mismatched, receipt, require_recorded=True)
        self.assertFalse(result.eligible)
        self.assertEqual(("state_contradiction",), result.blockers)

    def test_atomic_receipt_can_name_advisory_collaborators(self):
        receipt = ResolutionReceipt.from_mapping(
            {
                "issues": [9], "owner": "tannerpolley", "collaborators": ["pair"],
                "implementation_base": "a" * 40, "branch": "codex/issue-9", "worktree": "/tmp/issue-9",
            }
        )
        comment = {
            "author": "tannerpolley", "body": receipt.comment(),
            "created_at": "2026-07-23T00:00:00Z", "url": "https://github.example/comment/1",
        }
        result = plan_resolution(
            [snapshot(9, assignees=["tannerpolley", "pair"], comments=[comment])],
            receipt, require_recorded=True,
        )
        self.assertTrue(result.eligible)

    def test_resolve_action_defaults_to_one_leaf_and_requires_explicit_multi_selection(self):
        context = Context(
            ROOT / "scripts/project-truss.sh",
            ROOT,
            "scripts/project-truss.sh",
            "project-truss.sh",
            [],
            invocation_cwd=ROOT,
        )

        def resolve(payload, issue=9):
            output = StringIO()
            with patch("scripts.lib.commands.project.GitHubClient") as github, patch(
                "scripts.lib.commands.project._validate_implementation_base"
            ), patch(
                "scripts.lib.commands.project._validate_resolution_workspace"
            ), patch(
                "scripts.lib.commands.project.validate_preparation"
            ), redirect_stdout(output):
                github.return_value.snapshot.side_effect = lambda repository, number: snapshot(number)
                preparation = {
                    "canonical_checkout": str(ROOT),
                    "primary_remote": "origin",
                    "default_branch": "main",
                    "remote_ref": "refs/remotes/origin/main",
                    "implementation_base": payload["implementation_base"],
                }
                code = command_project_truss(
                    context,
                    {
                        "Action": "Resolve",
                        "Repository": "tannerpolley/project-truss",
                        "Issue": issue,
                        "ResolutionJson": json.dumps(payload),
                        "PreparationJson": json.dumps(preparation),
                    },
                )
            return code, json.loads(output.getvalue())

        shared = {
            "owner": "tannerpolley",
            "implementation_base": "a" * 40,
            "branch": "codex/issue-10",
            "worktree": str(ROOT),
        }
        singleton_code, singleton = resolve(shared)
        self.assertEqual((0, [9], True), (singleton_code, singleton["issues"], singleton["eligible"]))

        multi_code, multi = resolve({**shared, "issues": [9, 11]}, issue=10)
        self.assertEqual((0, [9, 11], True), (multi_code, multi["issues"], multi["eligible"]))
    def test_resolve_action_rejects_stale_base_or_wrong_workspace(self):
        context = Context(
            ROOT / "scripts/project-truss.sh",
            ROOT,
            "scripts/project-truss.sh",
            "project-truss.sh",
            [],
            invocation_cwd=ROOT,
        )
        payload = {
            "owner": "tannerpolley",
            "implementation_base": "a" * 40,
            "branch": "codex/issue-10",
            "worktree": str(ROOT),
        }
        preparation = {
            "canonical_checkout": str(ROOT),
            "primary_remote": "origin",
            "default_branch": "main",
            "remote_ref": "refs/remotes/origin/main",
            "implementation_base": "a" * 40,
        }
        with patch(
            "scripts.lib.commands.project._validate_implementation_base",
            side_effect=ScriptError("ImplementationBase is not an ancestor"),
        ), self.assertRaisesRegex(ScriptError, "not an ancestor"):
            command_project_truss(
                context,
                {
                    "Action": "Resolve",
                    "Repository": "tannerpolley/project-truss",
                    "Issue": 9,
                    "ResolutionJson": json.dumps(payload),
                    "PreparationJson": json.dumps(preparation),
                },
            )
        with patch("scripts.lib.commands.project._validate_implementation_base"), patch(
            "scripts.lib.commands.project.validate_preparation"
        ):
            with self.assertRaisesRegex(ScriptError, "branch does not match"):
                command_project_truss(context, {
                    "Action": "Resolve", "Repository": "tannerpolley/project-truss",
                    "Issue": 9, "ResolutionJson": json.dumps(payload),
                    "PreparationJson": json.dumps(preparation),
                })

    def test_resolution_launchers_assemble_git_provider_and_policy_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"; project.mkdir()
            def git(*args):
                return subprocess.run(["git", *args], cwd=project, text=True, check=True,
                                      capture_output=True).stdout.strip()
            git("init", "-q")
            git("config", "user.name", "Project Truss Test")
            git("config", "user.email", "project-truss@example.com")
            (project / "README.md").write_text("assembled boundary\n", encoding="utf-8")
            git("add", "README.md")
            git("commit", "-qm", "base")
            git("branch", "-m", "codex/issue-10")
            base = git("rev-parse", "HEAD")
            shared = {"issues": [9, 11], "owner": "tannerpolley",
                      "implementation_base": base, "branch": "codex/issue-10",
                      "worktree": str(project.resolve())}
            claim = ResolutionReceipt.from_mapping(shared)
            close = ResolutionReceipt.from_mapping({**shared, "pull_request": 12})
            payloads = {
                **{f"claim-{n}": graphql_payload(n, claim) for n in claim.issues},
                **{f"close-{n}": graphql_payload(n, close, closed=True) for n in close.issues},
                "pr": {"number": 12, "state": "MERGED", "mergedAt": "2026-07-23T01:00:00Z",
                       "mergeCommit": {"oid": "c" * 40}, "url": "https://github.example/pull/12",
                       "headRefOid": "b" * 40, "reviewDecision": "APPROVED",
                       "statusCheckRollup": [{"__typename": "CheckRun", "status": "COMPLETED",
                                             "conclusion": "SUCCESS"}]},
            }
            fake_bin = project.parent / "bin"
            fake_bin.mkdir()
            fake_gh = fake_bin / "gh"
            fake_gh.write_text(
                "#!/usr/bin/env python3\nimport json, os, sys\n"
                f"payloads = json.loads({json.dumps(payloads)!r})\n"
                "key = 'pr' if sys.argv[1:3] == ['pr', 'view'] else os.environ['TRUSS_TEST_PHASE'] + '-' + next(v.split('=', 1)[1] for v in sys.argv if v.startswith('number='))\n"
                "print(json.dumps(payloads[key]))\n", encoding="utf-8")
            fake_gh.chmod(0o755)
            environment = dict(os.environ)
            environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
            prefix = ["bash", str(ROOT / "scripts/project-truss.sh"), "-RepoRoot", str(project),
                      "-Repository", "tannerpolley/project-truss", "-Issue", "10"]
            def launch(phase, *args):
                environment["TRUSS_TEST_PHASE"] = phase
                result = subprocess.run([*prefix, *args], cwd=project, env=environment,
                                        text=True, capture_output=True)
                return result, json.loads(result.stdout)
            resolved, resolve_payload = launch("claim", "-Action", "Resolve",
                "-ResolutionJson", json.dumps(claim.to_dict()), "-RequireRecorded", "true")
            git("branch", "-m", "main")
            self.assertFalse(git("branch", "--list", "codex/issue-10"))
            health = {"verification_passed": True, "review_passed": True,
                      "integration_healthy": True, "source_clean": True, "head_sha": "b" * 40}
            closed, close_payload = launch("close", "-Action", "Closeout",
                "-ResolutionJson", json.dumps(close.to_dict()), "-HealthJson", json.dumps(health))
        self.assertEqual((0, True, [9, 11], "start"), (
            resolved.returncode, resolve_payload["eligible"], resolve_payload["issues"], resolve_payload["next_skill"]))
        self.assertEqual((0, True, [], "start"), (
            closed.returncode, close_payload["ok"], close_payload["findings"], close_payload["next_skill"]))

    def test_resolution_closeout_requires_one_shared_verified_pull_request(self):
        receipt = ResolutionReceipt.from_mapping(
            {
                "issues": [9, 11],
                "owner": "tannerpolley",
                "implementation_base": "a" * 40,
                "branch": "codex/issue-10",
                "worktree": "/tmp/issue-10",
                "pull_request": 12,
            }
        )
        receipt_comment = {
            "author": "tannerpolley",
            "body": receipt.comment(),
            "created_at": "2026-07-23T00:00:00Z",
            "url": "https://github.example/comment/1",
        }
        closed = {
            "assignees": ["tannerpolley"],
            "closing_prs": [passing_pr()],
            "comments": [receipt_comment],
            "issue_state": "CLOSED",
            "body": LEAF_BODY.replace("[ ]", "[x]"),
        }
        members = [snapshot(9, **closed), snapshot(11, **closed)]
        health = FinalHealth(
            True,
            True,
            True,
            "b" * 40,
            review_passed=True,
        )
        self.assertEqual((), close_resolution_findings(members, receipt, health))
        self.assertEqual(
            ("verification_failed",),
            close_resolution_findings(
                members,
                receipt,
                FinalHealth(True, True, True, "b" * 40),
            ),
        )

        mismatched = [
            members[0],
            snapshot(
                11,
                **{
                    **closed,
                    "closing_prs": [passing_pr(number=13)],
                },
            ),
        ]
        self.assertEqual(
            ("state_contradiction",),
            close_resolution_findings(mismatched, receipt, health),
        )

if __name__ == "__main__":
    unittest.main()
