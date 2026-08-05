import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts.lib.command_support import Context
from scripts.lib.commands.project import command_project_truss
from scripts.lib.truss_github import GitHubClient
from scripts.lib.truss_policy import OutcomeSnapshot, ResolutionReceipt, WorkRequest, derive_state, parse_issue_contract, plan_work

BODY = """## What to build

Ship one self-contained behavior.

## Acceptance criteria

- [x] The behavior is verified.

## Blocked by

None.

## Notes

Extra context is allowed.
"""


def issue(assignees=(), comments=(), *, state="OPEN"):
    return OutcomeSnapshot.from_mapping({
        "authoritative": True, "observed_at": "2026-08-04T00:00:00Z", "repository": "owner/repo",
        "issue": {"number": 9, "title": "Standalone", "state": state, "body": BODY, "url": "https://github.example/issues/9"},
        "assignees": list(assignees), "children": [], "blocked_by": [], "blocking": [], "closing_prs": [],
        "comments": list(comments), "source_urls": [], "provider_findings": [],
    })


class FrictionReductionTests(unittest.TestCase):
    def test_standalone_aliases_terminal_state_and_continuation(self):
        self.assertEqual(("standalone", True), (parse_issue_contract(BODY).kind, parse_issue_contract(BODY).ok))
        for reason, expected in (("NOT_PLANNED", "Cancelled"), ("DEFERRED", "Deferred")):
            terminal = issue(state="CLOSED").to_dict()
            terminal["issue"]["state_reason"] = reason
            self.assertEqual(expected, derive_state(OutcomeSnapshot.from_mapping(terminal)))
        self.assertEqual("light", plan_work(WorkRequest(explicit=True)).to_dict()["continuation"]["lane"])

    def test_claim_writes_and_verifies_a_receipt(self):
        receipt = ResolutionReceipt.from_mapping({"issues": [9], "owner": "agent", "implementation_base": "a" * 40, "branch": "codex/issue-9", "worktree": "/tmp/issue-9"})
        comment = {"author": "agent", "body": receipt.comment(), "created_at": "now", "url": "comment"}
        client = GitHubClient(runner=Mock())
        with patch.object(client, "snapshot", side_effect=[issue(), issue(["agent"], [comment])]), patch.object(client, "_mutate") as mutate:
            result = client.claim_resolution("owner/repo", receipt)
        self.assertTrue(result["verified"])
        self.assertEqual(2, mutate.call_count)

    def test_start_alias_and_light_method_degradation_continue(self):
        root = Path(__file__).resolve().parents[1]
        output = StringIO()
        with redirect_stdout(output):
            code = command_project_truss(Context(root / "scripts/project-truss.sh", root, "", "", [], invocation_cwd=root), {"_positional": ["start"]})
        payload = json.loads(output.getvalue())
        self.assertEqual((0, "Plan", "light"), (code, payload["action"], payload["lane"]))
        self.assertEqual(["context_required"], payload["blockers"])
        self.assertEqual("review_required", payload["context"]["status"])
        self.assertIn("CONTEXT.md", payload["context"]["files"])
        plan = plan_work(WorkRequest(explicit=True, code_change=True))
        self.assertEqual((), plan.blockers)
        self.assertEqual("missing", plan.method_routes["code-review"])

    def test_start_reports_missing_context_instead_of_silently_continuing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = StringIO()
            with redirect_stdout(output):
                code = command_project_truss(
                    Context(Path(__file__).resolve().parents[1] / "scripts/project-truss.sh",
                            Path(__file__).resolve().parents[1], "", "", [], invocation_cwd=root),
                    {"Action": "Plan", "RequestJson": json.dumps({"explicit": True, "start_entry": True})},
                )
        payload = json.loads(output.getvalue())
        self.assertEqual(0, code)
        self.assertEqual(("context_required", "missing"), (payload["blockers"][0], payload["context"]["status"]))

    def test_cursor_pagination_appends_a_page(self):
        client = GitHubClient(runner=Mock())
        with patch.object(client, "_page", return_value={"nodes": [{"login": "second"}], "pageInfo": {"hasNextPage": False}}) as page:
            nodes = client._paginate("owner/repo", 9, "assignees", [{"login": "first"}], {"hasNextPage": True, "endCursor": "cursor"})
        self.assertEqual(["first", "second"], [node["login"] for node in nodes])
        page.assert_called_once_with("owner/repo", 9, "assignees", "cursor")


if __name__ == "__main__":
    unittest.main()
