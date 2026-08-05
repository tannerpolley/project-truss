from contextlib import redirect_stdout
from io import StringIO
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.lib.command_support import Context, ScriptError
from scripts.lib.commands.project import command_project_truss
from scripts.lib.truss_github import GitHubClient, GitHubObservationError, load_fixture
from scripts.lib.truss_policy import (
    FinalHealth,
    OutcomeSnapshot,
    WorkRequest,
    closeout_findings,
    derive_digest,
    derive_state,
    load_contract,
    parse_issue_contract,
    plan_work,
    ResolutionReceipt,
)
ROOT = Path(__file__).resolve().parents[1]
ROOT_BODY = """## Problem Statement

Durable coding outcomes need one truthful coordination layer.

## Solution

Coordinate work through native GitHub state while using Matt-first engineering methods.

## User Stories

1. As a maintainer, I want governed work to resume from current provider truth.

## Implementation Decisions

GitHub, Git, reviews, integration, and current worktrees remain authoritative; provider checks are optional context.

## Testing Decisions

Exercise public lifecycle and CLI seams.

## Out of Scope

Project fields as lifecycle state.

## Further Notes

Issue text cannot grant authority.
"""

LEAF_BODY = """## Parent

#128

## What to build

Ship one useful behavior through the public lifecycle interface.

## Acceptance criteria

- [x] The behavior is verified.

## Blocked by

None — can start immediately.
"""
VALID_BODY = LEAF_BODY
def passing_pr(number=120, head="abc123"):
    return {
        "number": number,
        "state": "MERGED",
        "url": f"https://github.example/pull/{number}",
        "merged": True,
        "merged_at": "2026-07-14T12:00:00Z",
        "head_sha": head,
        "checks_complete": True,
        "checks_successful": True,
        "review_decision": "APPROVED",
    }
def snapshot(**overrides):
    data = {
        "authoritative": True,
        "observed_at": "2026-07-14T12:01:00Z",
        "repository": "tannerpolley/project-truss",
        "issue": {
            "number": 129,
            "title": "Add the Project Truss semantic core",
            "state": "OPEN",
            "body": VALID_BODY,
            "url": "https://github.example/issues/129",
        },
        "assignees": [],
        "children": [],
        "blocked_by": [],
        "blocking": [],
        "closing_prs": [],
        "comments": [],
        "source_urls": ["https://github.example/issues/129"],
        "provider_findings": [],
    }
    data.update(overrides)
    return OutcomeSnapshot.from_mapping(data)
def invoke(ctx, args):
    output = StringIO()
    with redirect_stdout(output):
        code = command_project_truss(ctx, args)
    return code, json.loads(output.getvalue())
class DirectAndShapeTests(unittest.TestCase):
    def test_direct_work_has_no_truss_structure(self):
        result = plan_work(WorkRequest())
        self.assertEqual("direct", result.lane)
        self.assertEqual((), result.layers)
        self.assertFalse(result.question_required)
    def test_adaptive_work_uses_light_shape_and_governed_release_shape(self):
        single = plan_work(WorkRequest(explicit=True))
        release = plan_work(
            WorkRequest(
                explicit=True,
                release_or_milestone=True,
                independent_units=3,
                matt_configured=True,
                new_outcome=True,
                vocabulary_confirmed=True,
                grilling_decisions=("Which route? -> Continue automatically.",),
                shared_understanding_confirmation="Confirmed.",
                available_methods=("grilling", "domain-modeling"),
            )
        )
        self.assertEqual(("issue", "pull_request"), single.layers)
        self.assertFalse(single.question_required)
        self.assertEqual("proceed directly", single.to_dict()["next_action"])
        self.assertEqual(
            ("milestone", "parent", "leaf", "pull_request"), release.layers
        )
        self.assertFalse(release.question_required)
        self.assertEqual("shape", release.next_skill)
    def test_plan_infers_grilling_quality_and_profile_methods(self):
        with self.assertRaises(ValueError): WorkRequest.from_mapping({"repository_profile": []})
        self.assertIsNone(plan_work(WorkRequest(explicit=True)).next_skill)
        request = WorkRequest(
            mode="governed", explicit=True, matt_configured=True, new_outcome=True, code_change=True, change_risk="structural",
            stable_behavior_change=True, repository_profile="scientific-computing",
            grilling_decisions=("Question -> answer",),
            shared_understanding_confirmation="Confirmed",
            vocabulary_confirmed=True,
            available_methods=("grilling", "domain-modeling", "tdd", "code-review",
                               "cutthroat-code-cleanup", "minimize-code-surface"),
        )
        plan = plan_work(request)
        self.assertFalse(plan.question_required)
        self.assertNotIn("grill-with-docs", plan.method_routes)
        self.assertEqual("missing", plan.method_routes["scientific-coding-and-testing"])
        for method in ("grilling", "domain-modeling", "tdd", "code-review",
                       "cutthroat-code-cleanup", "minimize-code-surface"):
            self.assertEqual("invocable", plan.method_routes[method])
        self.assertEqual(("method_capability_missing",), plan.blockers)
        self.assertIsNone(plan.next_skill)
        self.assertEqual("stop: method_capability_missing", plan.to_dict()["next_action"])
        ungrilled = plan_work(WorkRequest(mode="governed", explicit=True, matt_configured=True, new_outcome=True,
            vocabulary_confirmed=True,
            available_methods=("grilling", "domain-modeling")))
        self.assertEqual((True, "start", ("decision_required",)),
                         (ungrilled.question_required, ungrilled.next_skill, ungrilled.blockers))
        resumed = plan_work(WorkRequest(explicit=True, matt_configured=True))
        self.assertEqual((None, "proceed directly"),
                         (resumed.next_skill, resumed.to_dict()["next_action"]))
        self.assertRaisesRegex(ValueError, "invalid failed_gate", WorkRequest.from_mapping, {"failed_gate": "ci"})
        recovery = plan_work(WorkRequest(explicit=True, matt_configured=True, failed_gate="verification",
                                         available_methods=("diagnosing-bugs",)))
        self.assertEqual("invocable", recovery.method_routes["diagnosing-bugs"])

    def test_start_requires_context_review_then_shared_vocabulary(self):
        base = WorkRequest(
            mode="governed", explicit=True, start_entry=True, context_available=True,
            context_files=("CONTEXT.md",), matt_configured=True, new_outcome=True,
            available_methods=("grilling", "domain-modeling"),
        )
        review = plan_work(base)
        self.assertEqual(("context_required",), review.blockers)
        self.assertEqual("review_required", review.to_dict()["context"]["status"])

        vocabulary = plan_work(WorkRequest(**{**base.__dict__, "context_reviewed": True}))
        self.assertEqual(("vocabulary_required",), vocabulary.blockers)
        self.assertEqual("vocabulary_required", vocabulary.context_status)

        decisions = plan_work(WorkRequest(**{
            **base.__dict__, "context_reviewed": True, "vocabulary_confirmed": True,
            "context_terms": ("shared vocabulary",),
        }))
        self.assertEqual(("decision_required",), decisions.blockers)
        complete = plan_work(WorkRequest(**{
            **base.__dict__, "context_reviewed": True, "vocabulary_confirmed": True,
            "context_terms": ("shared vocabulary",), "scope_complete": True,
            "grilling_decisions": ("What is the boundary? -> The repository contract.",),
            "shared_understanding_confirmation": "Confirmed.",
        }))
        self.assertEqual((), complete.blockers)
        self.assertEqual("shape", complete.next_skill)

    def test_new_matt_1_2_methods_route_from_their_real_triggers(self):
        wizard = plan_work(WorkRequest(explicit=True, matt_configured=True, manual_procedure=True,
                                       available_methods=("wizard",)))
        self.assertEqual("invocable", wizard.method_routes["wizard"])
        docs = plan_work(WorkRequest(explicit=True, matt_configured=True, agent_document_change=True,
                                     available_methods=("writing-for-agents",)))
        self.assertEqual("invocable", docs.method_routes["writing-for-agents"])
        design = plan_work(WorkRequest(explicit=True, matt_configured=True, design_change=True,
                                       available_methods=("codebase-design",)))
        self.assertEqual("invocable", design.method_routes["codebase-design"])
    def test_contract_and_issue_body_fail_closed_as_one_behavior_family(self):
        contract = load_contract(ROOT / "docs/project-truss/contract.yml")
        self.assertEqual(2, contract["version"])
        self.assertEqual(["setup", "start", "shape", "resolve", "close", "advanced-user-input"], contract["public_skills"])
        self.assertEqual(
            ["setup", "start", "shape", "resolve", "close", "advanced-user-input"],
            contract["skills"],
        )
        root = parse_issue_contract(ROOT_BODY)
        leaf = parse_issue_contract(LEAF_BODY)
        self.assertEqual(("root", True), (root.kind, root.ok))
        self.assertEqual(("leaf", True), (leaf.kind, leaf.ok))
        incomplete = parse_issue_contract(LEAF_BODY.replace("## Blocked by", "## Dependencies"))
        self.assertTrue(incomplete.ok)
        self.assertNotIn("Blocked by", incomplete.missing)
        duplicate = parse_issue_contract(LEAF_BODY + "\n## Acceptance criteria\n\n- [x] Duplicate.\n")
        self.assertFalse(duplicate.ok)
        self.assertIn("Acceptance criteria", duplicate.missing)
        self.assertFalse(parse_issue_contract(ROOT_BODY + "\n" + LEAF_BODY).ok)
        for marks in ("#", "##", "###", "######"):
            self.assertTrue(parse_issue_contract(LEAF_BODY + f"\n{marks} Outcome\n\nRetired hybrid.\n").ok)
        invalid_parent = parse_issue_contract(LEAF_BODY.replace("#128", "No parent"))
        self.assertFalse(invalid_parent.ok)
        self.assertIn("Parent", invalid_parent.missing)
        retired = parse_issue_contract(
            """## Outcome

Retired.

## Context or behavioral delta

Retired.

## Scope and non-goals

Retired.

## Acceptance criteria

- [x] Retired.

## Verification basis

Retired.

## Constraints, risks, and authority

Retired.
"""
        )
        self.assertFalse(retired.ok)

        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "contract.yml"
            invalid.write_text(
                (ROOT / "docs/project-truss/contract.yml").read_text(encoding="utf-8")
                + "unknown: true\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unknown contract key"):
                load_contract(invalid)


class LifecycleAndDigestTests(unittest.TestCase):
    def test_all_five_states_are_derived_without_a_ledger(self):
        cases = {
            "Ready": snapshot(),
            "Claimed": snapshot(assignees=["tannerpolley"]),
            "In review": snapshot(assignees=["tannerpolley"], closing_prs=[{**passing_pr(), "state": "OPEN", "merged": False, "merged_at": None}]),
            "Blocked": snapshot(blocked_by=[{"number": 128, "title": "blocker", "state": "OPEN", "url": "https://github.example/issues/128"}]),
            "Done": snapshot(
                issue={"number": 129, "title": "core", "state": "CLOSED", "body": VALID_BODY, "url": "https://github.example/issues/129"},
                assignees=["tannerpolley"],
                closing_prs=[passing_pr()],
            ),
        }
        for expected, current in cases.items():
            with self.subTest(expected=expected):
                self.assertEqual(expected, derive_state(current))

    def test_digest_has_five_reentry_parts_and_source_links(self):
        digest = derive_digest(snapshot()).to_dict()
        self.assertEqual(
            "Ship one useful behavior through the public lifecycle interface.",
            digest["outcome"],
        )
        self.assertEqual([{"number": 129, "title": "Add the Project Truss semantic core", "url": "https://github.example/issues/129"}], digest["ready_frontier"])
        self.assertEqual({}, digest["active"])
        self.assertEqual([], digest["blockers_or_decisions"])
        self.assertEqual("Claim ready issue #129 before implementation.", digest["next_safe_action"])
        self.assertEqual("live", digest["source"])
        self.assertEqual(["https://github.example/issues/129"], digest["source_urls"])

        parent = snapshot(
            issue={"number": 128, "title": "parent", "state": "OPEN", "body": VALID_BODY, "url": "https://github.example/issues/128"},
            children=[
                {"number": 129, "title": "ready", "state": "OPEN", "url": "https://github.example/issues/129", "lifecycle_state": "Ready"},
                {"number": 130, "title": "blocked", "state": "OPEN", "url": "https://github.example/issues/130", "lifecycle_state": "Blocked"},
            ],
        )
        parent_digest = derive_digest(parent)
        self.assertEqual([129], [item["number"] for item in parent_digest.ready_frontier])
        self.assertEqual(["child #130 is Blocked"], list(parent_digest.blockers_or_decisions))
        self.assertEqual("Claim ready child #129 before implementation.", parent_digest.next_safe_action)
class TruthfulCloseoutTests(unittest.TestCase):
    def test_status_requires_an_implementation_base_after_claim(self):
        current = snapshot(assignees=["one"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ctx = Context(ROOT / "scripts/project-truss.sh", ROOT, "scripts/project-truss.sh", "project-truss.sh", [], invocation_cwd=root)
            with patch("scripts.lib.commands.project.GitHubClient") as github:
                github.return_value.snapshot.return_value = current
                with self.assertRaisesRegex(ScriptError, "ImplementationBase is required after claim"):
                    command_project_truss(ctx, {"Action": "Status", "Repository": "owner/repo", "Issue": 129})

    def test_status_has_no_provider_specific_working_artifact_state(self):
        current = snapshot()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ctx = Context(ROOT / "scripts/project-truss.sh", ROOT, "scripts/project-truss.sh", "project-truss.sh", [], invocation_cwd=root)

            with patch("scripts.lib.commands.project.GitHubClient") as github:
                github.return_value.snapshot.return_value = current
                (root / "docs/legacy-workflow/specs").mkdir(parents=True)
                (root / "docs/legacy-workflow/plans/nested").mkdir(parents=True)
                (root / "docs/legacy-workflow/specs/feature.md").write_text("working spec", encoding="utf-8")
                (root / "docs/legacy-workflow/plans/nested/steps.md").write_text("working plan", encoding="utf-8")
                code, payload = invoke(ctx, {"Action": "Status", "Repository": "owner/repo", "Issue": 129})

        self.assertEqual((0, [129], "start"), (code, [item["number"] for item in payload["ready_frontier"]], payload["next_skill"]))
        self.assertNotIn("unretired_artifacts", payload)
        self.assertNotIn("implementation_artifact_history", payload)

    def test_status_keeps_provider_and_child_blockers_ordered(self):
        current = snapshot(
            authoritative=False,
            children=[{
                "number": 130,
                "title": "blocked child",
                "state": "OPEN",
                "url": "https://github.example/issues/130",
                "lifecycle_state": "Blocked",
            }],
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ctx = Context(ROOT / "scripts/project-truss.sh", ROOT, "scripts/project-truss.sh", "project-truss.sh", [], invocation_cwd=root)
            with patch("scripts.lib.commands.project.GitHubClient") as github:
                github.return_value.snapshot.return_value = current
                code, payload = invoke(ctx, {"Action": "Status", "Repository": "owner/repo", "Issue": 129})

        self.assertEqual(0, code)
        self.assertEqual(
            ["external_state_unavailable", "child #130 is Blocked"],
            payload["blockers_or_decisions"],
        )
        self.assertEqual(
            "Resolve blockers on child #130 before continuing.",
            payload["next_safe_action"],
        )

    def test_status_rejects_an_implementation_base_outside_current_history(self):
        current = snapshot(assignees=["one"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*args):
                return subprocess.run(["git", *args], cwd=root, text=True, check=True, capture_output=True).stdout.strip()

            git("init", "-q")
            git("config", "user.name", "Project Truss Test")
            git("config", "user.email", "project-truss@example.com")
            (root / "README.md").write_text("base\n", encoding="utf-8")
            git("add", "README.md")
            git("commit", "-qm", "base")
            ancestor = git("rev-parse", "HEAD")
            (root / "README.md").write_text("future\n", encoding="utf-8")
            git("add", "README.md")
            git("commit", "-qm", "future")
            future = git("rev-parse", "HEAD")
            git("checkout", "-q", ancestor)

            ctx = Context(ROOT / "scripts/project-truss.sh", ROOT, "scripts/project-truss.sh", "project-truss.sh", [], invocation_cwd=root)
            with patch("scripts.lib.commands.project.GitHubClient") as github:
                github.return_value.snapshot.return_value = current
                with self.assertRaisesRegex(ScriptError, "not an ancestor"):
                    command_project_truss(ctx, {
                        "Action": "Status",
                        "Repository": "owner/repo",
                        "Issue": 129,
                        "ImplementationBase": future,
                    })

    def test_closeout_has_no_provider_specific_artifact_evidence(self):
        current = snapshot(
            issue={"number": 128, "title": "root", "state": "CLOSED", "body": ROOT_BODY, "url": "https://github.example/issues/128"},
            children=[{"number": 129, "title": "child", "state": "CLOSED", "url": "https://github.example/issues/129", "lifecycle_state": "Done"}],
        )
        health = json.dumps({"verification_passed": True, "review_passed": True, "integration_healthy": True, "source_clean": True, "head_sha": "abc123"})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ctx = Context(ROOT / "scripts/project-truss.sh", ROOT, "scripts/project-truss.sh", "project-truss.sh", [], invocation_cwd=root)

            with patch("scripts.lib.commands.project.GitHubClient") as github:
                github.return_value.snapshot.return_value = current
                code, payload = invoke(ctx, {
                    "Action": "Closeout",
                    "Repository": "owner/repo",
                    "Issue": 128,
                    "HealthJson": health,
                })

        self.assertEqual((0, []), (code, payload["findings"]))
        self.assertNotIn("unretired_artifacts", payload)
        self.assertNotIn("implementation_artifact_history", payload)

    def test_code_leaf_closeout_requires_a_resolution_receipt(self):
        current = snapshot(
            issue={"number": 129, "title": "core", "state": "CLOSED", "body": VALID_BODY, "url": "https://github.example/issues/129"},
            assignees=["one"],
            closing_prs=[passing_pr()],
        )
        health = json.dumps({"verification_passed": True, "integration_healthy": True, "source_clean": True, "head_sha": "abc123"})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ctx = Context(ROOT / "scripts/project-truss.sh", ROOT, "scripts/project-truss.sh", "project-truss.sh", [], invocation_cwd=root)
            with patch("scripts.lib.commands.project.GitHubClient") as github:
                github.return_value.snapshot.return_value = current
                with self.assertRaisesRegex(ScriptError, "ResolutionJson is required for code-leaf Closeout"):
                    command_project_truss(ctx, {
                        "Action": "Closeout",
                        "Repository": "owner/repo",
                        "Issue": 129,
                        "HealthJson": health,
                    })

    def test_code_leaf_closeout_requires_exactly_one_current_claim(self):
        current = snapshot(
            issue={"number": 129, "title": "core", "state": "CLOSED", "body": VALID_BODY, "url": "https://github.example/issues/129"},
            closing_prs=[passing_pr()],
        )
        self.assertEqual(
            ("claim_conflict",),
            closeout_findings(current, FinalHealth(True, True, True, "abc123", review_passed=True)),
        )

    def test_verified_parent_rollup_does_not_require_a_parent_code_pr(self):
        parent = snapshot(
            issue={"number": 128, "title": "parent", "state": "CLOSED", "body": VALID_BODY, "url": "https://github.example/issues/128"},
            children=[{"number": 129, "title": "child", "state": "CLOSED", "url": "https://github.example/issues/129", "lifecycle_state": "Done"}],
        )
        health = FinalHealth(True, True, True, "integrated-head")
        self.assertEqual("Done", derive_state(parent))
        self.assertEqual((), closeout_findings(parent, health))

    def test_closed_but_unverified_descendant_blocks_parent_rollup(self):
        parent = snapshot(
            issue={"number": 128, "title": "parent", "state": "CLOSED", "body": VALID_BODY, "url": "https://github.example/issues/128"},
            children=[{"number": 129, "title": "child", "state": "CLOSED", "url": "https://github.example/issues/129", "lifecycle_state": "Blocked"}],
        )
        self.assertEqual("Blocked", derive_state(parent))
        self.assertEqual(
            ("integration_unhealthy", "state_contradiction"),
            closeout_findings(parent, FinalHealth(True, True, True, "integrated-head")),
        )

    def test_fixture_and_open_dependency_block_closeout_in_contract_order(self):
        current = snapshot(
            authoritative=False,
            issue={"number": 129, "title": "core", "state": "CLOSED", "body": VALID_BODY, "url": "https://github.example/issues/129"},
            assignees=["tannerpolley"],
            blocked_by=[{"number": 128, "title": "blocker", "state": "OPEN", "url": "https://github.example/issues/128"}],
            closing_prs=[passing_pr()],
        )
        health = FinalHealth(True, True, True, "abc123", review_passed=True)
        self.assertEqual(
            ("dependency_blocked", "external_state_unavailable"),
            closeout_findings(current, health),
        )

    def test_closeout_rejects_claim_pr_check_descendant_and_health_contradictions(self):
        current = snapshot(
            issue={"number": 129, "title": "core", "state": "CLOSED", "body": VALID_BODY.replace("[x]", "[ ]"), "url": "https://github.example/issues/129"},
            assignees=["one", "two"],
            children=[{"number": 130, "title": "child", "state": "OPEN", "url": "https://github.example/issues/130"}],
            closing_prs=[{**passing_pr(), "checks_successful": False}],
        )
        findings = closeout_findings(current, FinalHealth(False, False, False, "different"))
        self.assertEqual(
            ("claim_conflict", "verification_failed", "integration_unhealthy", "state_contradiction"),
            findings,
        )
        reviewed = snapshot(
            issue={"number": 129, "title": "core", "state": "CLOSED", "body": VALID_BODY, "url": "https://github.example/issues/129"},
            assignees=["one"],
            closing_prs=[{**passing_pr(), "review_decision": "CHANGES_REQUESTED"}],
        )
        approved = snapshot(
            issue={"number": 129, "title": "core", "state": "CLOSED", "body": VALID_BODY, "url": "https://github.example/issues/129"},
            assignees=["one"], closing_prs=[{**passing_pr(), "checks_complete": False, "checks_successful": False}],
        )
        self.assertEqual(((), "Done"), (closeout_findings(approved, FinalHealth(True, True, True, "abc123", review_passed=True)), derive_state(approved)))
        self.assertEqual(("verification_failed",), closeout_findings(reviewed, FinalHealth(True, True, True, "abc123", review_passed=True)))
        self.assertEqual(("state_contradiction",), closeout_findings(snapshot(
            issue={"number": 129, "title": "core", "state": "CLOSED", "body": VALID_BODY, "url": "https://github.example/issues/129"},
            assignees=["one"], closing_prs=[passing_pr()],
        ), FinalHealth(True, True, False, "abc123", review_passed=True)))
class GitHubObservationTests(unittest.TestCase):
    def test_live_provider_reads_relationships_pr_checks_and_source_urls(self):
        issue_payload = {
            "data": {
                "repository": {
                    "issue": {
                        "id": "I_116",
                        "number": 116,
                        "title": "Simplify",
                        "state": "CLOSED",
                        "body": VALID_BODY,
                        "url": "https://github.example/issues/116",
                        "updatedAt": "2026-07-13T00:00:00Z",
                        "assignees": {"nodes": [], "pageInfo": {"hasNextPage": False}},
                        "milestone": {"number": 3, "title": "M2", "state": "OPEN", "url": "https://github.example/milestone/3"},
                        "parent": None,
                        "subIssues": {"nodes": [], "pageInfo": {"hasNextPage": False}},
                        "blockedBy": {"nodes": [{"id": "I_115", "number": 115, "title": "isolation", "state": "CLOSED", "url": "https://github.example/issues/115"}], "pageInfo": {"hasNextPage": False}},
                        "blocking": {"nodes": [], "pageInfo": {"hasNextPage": False}},
                        "closedByPullRequestsReferences": {"nodes": [{"number": 120, "state": "MERGED", "merged": True, "mergedAt": "2026-07-13T01:00:00Z", "url": "https://github.example/pull/120", "headRefOid": "abc123"}], "pageInfo": {"hasNextPage": False}},
                        "comments": {"nodes": [], "pageInfo": {"hasNextPage": False}},
                    }
                }
            }
        }
        pr_payload = {
            "number": 120,
            "state": "MERGED",
            "mergedAt": "2026-07-13T01:00:00Z",
            "mergeCommit": {"oid": "merge123"},
            "statusCheckRollup": [{"__typename": "CheckRun", "name": "Validate", "status": "COMPLETED", "conclusion": "SUCCESS"}],
            "reviewDecision": "APPROVED",
            "url": "https://github.example/pull/120",
            "headRefOid": "abc123",
        }
        commands = []

        def runner(command, timeout):
            commands.append(command)
            payload = issue_payload if "graphql" in command else pr_payload
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

        current = GitHubClient(runner=runner, clock=lambda: "2026-07-14T12:00:00Z").snapshot(
            "tannerpolley/project-truss", 116
        )
        self.assertTrue(current.authoritative)
        self.assertEqual([115], [item.number for item in current.blocked_by])
        self.assertEqual([120], [item.number for item in current.closing_prs])
        self.assertTrue(current.closing_prs[0].checks_successful)
        self.assertIn("https://github.example/pull/120", current.source_urls)
        self.assertEqual(2, len(commands))

        pr_payload.pop("statusCheckRollup")
        absent = GitHubClient(runner=runner).snapshot("tannerpolley/project-truss", 116)
        self.assertEqual((False, False), (absent.closing_prs[0].checks_complete, absent.closing_prs[0].checks_successful))

        issue_payload["data"]["repository"]["issue"]["comments"]["pageInfo"].update(
            {"hasNextPage": True, "endCursor": "cursor"}
        )
        with self.assertRaisesRegex(GitHubObservationError, "safe pagination limit"):
            GitHubClient(runner=runner).snapshot("owner/repo", 116)
        issue_payload["data"]["repository"]["issue"]["comments"]["pageInfo"]["hasNextPage"] = False
        issue_payload["data"]["repository"]["issue"]["assignees"]["nodes"] = [{}]
        with self.assertRaisesRegex(GitHubObservationError, "assignee identity"):
            GitHubClient(runner=runner).snapshot("tannerpolley/project-truss", 116)

    def test_provider_errors_map_to_closed_blocker_vocabulary(self):
        def unavailable(command, timeout):
            return SimpleNamespace(returncode=1, stdout="", stderr="not logged in")

        with self.assertRaisesRegex(GitHubObservationError, "not logged in") as caught:
            GitHubClient(runner=unavailable).snapshot("owner/repo", 1)
        self.assertEqual("external_state_unavailable", caught.exception.code)

    def test_fixture_is_forced_non_authoritative(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            path.write_text(json.dumps(snapshot().to_dict()), encoding="utf-8")
            fixture = load_fixture(path)
            self.assertFalse(fixture.authoritative)
            self.assertEqual("Blocked", derive_state(fixture))
            digest = derive_digest(fixture)
            self.assertEqual((), digest.ready_frontier)
            self.assertIn("external_state_unavailable", digest.blockers_or_decisions)

            parent = snapshot(children=[{
                "number": 130,
                "title": "copied ready child",
                "state": "OPEN",
                "url": "https://github.example/issues/130",
                "lifecycle_state": "Ready",
            }])
            path.write_text(json.dumps(parent.to_dict()), encoding="utf-8")
            self.assertEqual((), derive_digest(load_fixture(path)).ready_frontier)


class LauncherTests(unittest.TestCase):
    def test_plan_cli_routes_shape_capability_stops_and_failed_gate_recovery(self):
        def launch(request):
            process = subprocess.run(["bash", str(ROOT / "scripts/project-truss.sh"), "-Action", "Plan",
                "-RequestJson", json.dumps(request)], cwd="/tmp", text=True, capture_output=True)
            self.assertEqual(0, process.returncode, process.stdout + process.stderr)
            return json.loads(process.stdout)
        shaped = launch({"explicit": True, "independent_units": 2})
        self.assertEqual(("Plan", "governed", ["parent", "leaf", "pull_request"]),
                         (shaped["action"], shaped["lane"], shaped["layers"]))
        blocked = launch({"explicit": True, "matt_configured": True, "new_outcome": True,
            "grilling_decisions": ["Question -> answer"], "shared_understanding_confirmation": "Confirmed"})
        self.assertEqual((None, "proceed directly"),
                         (blocked["next_skill"], blocked["next_action"]))
        recovery = launch({"explicit": True, "matt_configured": True, "failed_gate": "review",
                           "available_methods": ["diagnosing-bugs"]})
        self.assertEqual("invocable", recovery["method_routes"]["diagnosing-bugs"])

    def test_plan_routes_existing_pr_from_live_receipt_evidence(self):
        ctx = Context(ROOT / "scripts/project-truss.sh", ROOT, "", "", [], invocation_cwd=ROOT)
        payload = {"number": 7, "headRefName": "codex/issue-129", "closingIssuesReferences": [{"number": 129}]}
        client = GitHubClient(runner=lambda *_: SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""))
        receipt = ResolutionReceipt((129,), "one", "a" * 40, "codex/issue-129", "/tmp/worktree", 7)
        claimed = lambda value, author="one": snapshot(comments=[{"body": value.comment(), "author": author}])
        stale = ResolutionReceipt((129,), "one", "a" * 40, "codex/issue-129", "/tmp/worktree", 8)
        cases = ((snapshot(), "direct"), (claimed(receipt), "governed"),
                 (claimed(stale), "direct"), (claimed(receipt, "other"), "direct"))
        for current, expected in cases:
            with patch.object(client, "snapshot", return_value=current), \
                    patch("scripts.lib.commands.project.GitHubClient", return_value=client):
                _, result = invoke(ctx, {"Action": "Plan", "Repository": "owner/repo", "PullRequest": 7})
            self.assertEqual((expected, "live"), (result["lane"], result["source"]))


if __name__ == "__main__":
    unittest.main()
