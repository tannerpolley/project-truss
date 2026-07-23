from contextlib import redirect_stdout
from io import StringIO
import json
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


class ResolutionSetTests(unittest.TestCase):
    def test_explicit_set_allows_internal_blockers_and_rejects_external_blockers(self):
        receipt = ResolutionReceipt.from_mapping(
            {
                "issues": [9, 11],
                "owner": "tannerpolley",
                "implementation_base": "a" * 40,
                "branch": "codex/issue-10",
                "worktree": "issue-10",
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
                "worktree": "issue-10",
                "pull_request": 12,
            }
        )

        def comment(body):
            return {
                "author": "tannerpolley",
                "body": body,
                "created_at": "2026-07-23T00:00:00Z",
                "url": "https://github.example/comment/1",
            }

        matching = [
            snapshot(9, assignees=["tannerpolley"], comments=[comment(receipt.comment())]),
            snapshot(11, assignees=["tannerpolley"], comments=[comment(receipt.comment())]),
        ]
        self.assertTrue(plan_resolution(matching, receipt, require_recorded=True).eligible)

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
            ), redirect_stdout(output):
                github.return_value.snapshot.side_effect = lambda repository, number: snapshot(number)
                code = command_project_truss(
                    context,
                    {
                        "Action": "Resolve",
                        "Repository": "tannerpolley/project-truss",
                        "Issue": issue,
                        "ResolutionJson": json.dumps(payload),
                    },
                )
            return code, json.loads(output.getvalue())

        shared = {
            "owner": "tannerpolley",
            "implementation_base": "a" * 40,
            "branch": "codex/issue-10",
            "worktree": "issue-10",
        }
        singleton_code, singleton = resolve(shared)
        self.assertEqual((0, [9], True), (singleton_code, singleton["issues"], singleton["eligible"]))

        multi_code, multi = resolve({**shared, "issues": [9, 11]}, issue=10)
        self.assertEqual((0, [9, 11], True), (multi_code, multi["issues"], multi["eligible"]))

    def test_resolve_action_rejects_a_stale_implementation_base(self):
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
            "worktree": "issue-10",
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
                },
            )

    def test_resolution_closeout_requires_one_shared_verified_pull_request(self):
        receipt = ResolutionReceipt.from_mapping(
            {
                "issues": [9, 11],
                "owner": "tannerpolley",
                "implementation_base": "a" * 40,
                "branch": "codex/issue-10",
                "worktree": "issue-10",
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
        health = FinalHealth(True, True, True, "b" * 40)
        self.assertEqual((), close_resolution_findings(members, receipt, health))

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

    def test_closeout_action_verifies_the_shared_resolution_set(self):
        receipt = ResolutionReceipt.from_mapping(
            {
                "issues": [9, 11],
                "owner": "tannerpolley",
                "implementation_base": "a" * 40,
                "branch": "codex/issue-10",
                "worktree": "issue-10",
                "pull_request": 12,
            }
        )
        comment = {
            "author": "tannerpolley",
            "body": receipt.comment(),
            "created_at": "2026-07-23T00:00:00Z",
            "url": "https://github.example/comment/1",
        }
        members = {
            number: snapshot(
                number,
                assignees=["tannerpolley"],
                closing_prs=[passing_pr()],
                comments=[comment],
                issue_state="CLOSED",
                body=LEAF_BODY.replace("[ ]", "[x]"),
            )
            for number in receipt.issues
        }
        context = Context(
            ROOT / "scripts/project-truss.sh",
            ROOT,
            "scripts/project-truss.sh",
            "project-truss.sh",
            [],
            invocation_cwd=ROOT,
        )
        output = StringIO()
        with patch("scripts.lib.commands.project.GitHubClient") as github, patch(
            "scripts.lib.commands.project._validate_implementation_base"
        ), redirect_stdout(output):
            github.return_value.snapshot.side_effect = (
                lambda repository, number: members[number]
            )
            code = command_project_truss(
                context,
                {
                    "Action": "Closeout",
                    "Repository": "tannerpolley/project-truss",
                    "Issue": 10,
                    "ResolutionJson": json.dumps(receipt.to_dict()),
                    "HealthJson": json.dumps(
                        {
                            "verification_passed": True,
                            "integration_healthy": True,
                            "source_clean": True,
                            "head_sha": "b" * 40,
                        }
                    ),
                },
            )
        payload = json.loads(output.getvalue())
        self.assertEqual((0, True, []), (code, payload["ok"], payload["findings"]))
        self.assertEqual([9, 11], payload["issues"])


if __name__ == "__main__":
    unittest.main()
