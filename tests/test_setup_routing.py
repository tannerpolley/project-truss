from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts.lib.command_support import Context
from scripts.lib.commands.project import command_project_truss
from scripts.lib.truss_setup import SetupError, SetupRequest, apply_setup, validate_setup_target
from scripts.lib.truss_policy import OutcomeSnapshot, WorkRequest, all_method_routes, derive_digest, parse_issue_contract, plan_work

ROOT = Path(__file__).resolve().parents[1]
METHODS = ["grilling", "tdd", "diagnosing-bugs", "research", "domain-modeling", "prototype",
           "resolving-merge-conflicts", "code-review", "cutthroat-code-cleanup",
           "minimize-code-surface", "scientific-coding-and-testing"]

class SetupRoutingTests(unittest.TestCase):
    def test_setup_is_idempotent_and_preserves_unrelated_instructions(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            agents = project / "AGENTS.md"
            agents.write_text(
                "# Local policy\n\nKeep this.\n\n## Agent skills\n\n### Custom\n\nPreserve this skill.\n\n## Existing section\n\nPreserve this too.\n",
                encoding="utf-8",
            )
            agent_docs = project / "docs/agents"
            agent_docs.mkdir(parents=True)
            (agent_docs / "issue-tracker.md").write_text(
                "# Existing tracker\n\nPreserve tracker guidance.\n", encoding="utf-8"
            )
            request = json.dumps(
                {
                    "repository": "owner/repo",
                    "instruction_file": "AGENTS.md",
                    "domain_layout": "single-context",
                    "triage_enabled": True,
                    "available_methods": METHODS,
                }
            )
            context = Context(
                ROOT / "scripts/project-truss.sh",
                ROOT,
                "scripts/project-truss.sh",
                "project-truss.sh",
                [],
                invocation_cwd=project,
            )

            outputs, instruction_snapshots = [], []
            for index in range(2):
                output = StringIO()
                with mock.patch(
                    "scripts.lib.commands.project.validate_setup_target",
                    return_value={"repository": "owner/repo"},
                ), redirect_stdout(output):
                    self.assertEqual(
                        0,
                        command_project_truss(
                            context, {"Action": "Setup", "SetupJson": request}
                        ),
                    )
                outputs.append(json.loads(output.getvalue()))
                instruction_snapshots.append(agents.read_text(encoding="utf-8"))
                if index == 0:
                    tracker = project / "docs/agents/issue-tracker.md"
                    tracker.write_text(
                        tracker.read_text() + "\nRepository-specific note.\n",
                        encoding="utf-8",
                    )

            first_text = instruction_snapshots[0]
            self.assertEqual(instruction_snapshots[0], instruction_snapshots[1])
            self.assertIn("Keep this.", first_text)
            self.assertIn("Preserve this skill.", first_text)
            self.assertIn("Preserve this too.", first_text)
            self.assertEqual(1, first_text.count("## Agent skills"))
            self.assertTrue(outputs[0]["changed"])
            self.assertFalse(outputs[1]["changed"])
            self.assertEqual(["AGENTS.md"], outputs[0]["evidence"]["instruction_files"])
            self.assertEqual(METHODS, outputs[0]["evidence"]["reported_available_methods"])
            self.assertEqual(
                {"issue-tracker.md", "domain.md", "triage-labels.md"},
                {path.name for path in (project / "docs/agents").iterdir()},
            )
            tracker = (project / "docs/agents/issue-tracker.md").read_text()
            self.assertIn("Repository-specific note.", tracker)
            self.assertIn("Preserve tracker guidance.", tracker)
            self.assertEqual(1, tracker.count("## Project Truss tracker contract"))
            self.assertIn("owner/repo", tracker)
            self.assertIn("Wayfinder decision", tracker)
            self.assertIn("Project Truss execution", tracker)
            self.assertNotIn("Wayfinder labels derive", tracker)
            apply_setup(
                project,
                SetupRequest("owner/repo", "AGENTS.md", "single-context", False, tuple(METHODS)),
            )
            self.assertFalse((project / "docs/agents/triage-labels.md").exists())
            self.assertIn(
                "Repository-specific note.",
                (project / "docs/agents/issue-tracker.md").read_text(),
            )

    def test_setup_preflight_requires_matching_git_and_github_identity(self):
        root = Path("/repo")
        responses = [
            subprocess.CompletedProcess([], 0, "/repo\n", ""),
            subprocess.CompletedProcess([], 0, "owner/repo\n", ""),
        ]
        evidence = validate_setup_target(
            root, "owner/repo", runner=mock.Mock(side_effect=responses)
        )
        self.assertEqual("owner/repo", evidence["repository"])
        with self.assertRaisesRegex(SetupError, "github_capability_missing"):
            validate_setup_target(
                root,
                "owner/repo",
                runner=mock.Mock(
                    side_effect=[
                        responses[0],
                        subprocess.CompletedProcess([], 0, "other/repo\n", ""),
                    ]
                ),
            )

    def test_setup_rejects_symlink_escape_and_duplicate_agent_sections(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            outside = Path(directory) / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "docs").symlink_to(outside, target_is_directory=True)
            request = SetupRequest("owner/repo", "AGENTS.md", "single-context", False, ())
            with self.assertRaisesRegex(SetupError, "state_contradiction"):
                apply_setup(root, request)
            (root / "docs").unlink()
            (root / "AGENTS.md").write_text(
                "## Agent skills\n\nOne\n\n## Agent skills\n\nTwo\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(SetupError, "multiple"):
                apply_setup(root, request)
            (root / "AGENTS.md").write_text("", encoding="utf-8")
            (root / "pnpm-workspace.yaml").write_text("packages: []\n", encoding="utf-8")
            with self.assertRaisesRegex(SetupError, "multi-context"):
                apply_setup(root, request)

    def test_setup_rolls_back_partial_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            agents = root / "AGENTS.md"
            agents.write_text("Keep me.\n", encoding="utf-8")
            request = SetupRequest("owner/repo", "AGENTS.md", "single-context", False, ())
            real_replace, calls = __import__("os").replace, 0

            def fail_second(source, target):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated write failure")
                return real_replace(source, target)

            with mock.patch("scripts.lib.truss_setup.os.replace", side_effect=fail_second):
                with self.assertRaisesRegex(SetupError, "setup write failed"):
                    apply_setup(root, request)
            self.assertEqual("Keep me.\n", agents.read_text(encoding="utf-8"))
            self.assertFalse((root / "docs/agents/issue-tracker.md").exists())

    def test_setup_rejects_invalid_external_values(self):
        base = {"repository": "owner/repo", "instruction_file": "AGENTS.md",
                "domain_layout": "single-context", "triage_enabled": True, "available_methods": []}
        with self.assertRaises(ValueError):
            SetupRequest.from_mapping({**base, "repository": 1})
        with self.assertRaisesRegex(ValueError, "duplicates"):
            SetupRequest.from_mapping({**base, "available_methods": ["tdd", "tdd"]})

    def test_plan_routes_callable_matt_methods_and_native_truss_stages(self):
        setup = plan_work(WorkRequest(explicit=True))
        self.assertEqual(("setup", ()), (setup.next_skill, setup.blockers))
        self.assertNotIn("setup-matt-pocock-skills", setup.method_routes)

        wayfinder = plan_work(
            WorkRequest(
                explicit=True,
                exceeds_safe_context=True,
                material_decision_missing=True,
                matt_configured=True,
                new_outcome=True,
                grilling_decisions=("Question -> answer",),
                shared_understanding_confirmation="Confirmed",
                available_methods=("grilling", "domain-modeling"),
            )
        )
        self.assertEqual("start", wayfinder.next_skill)
        self.assertNotIn("wayfinder", wayfinder.method_routes)
        self.assertNotIn("grill-with-docs", wayfinder.method_routes)
        self.assertEqual("invocable", wayfinder.method_routes["grilling"])
        self.assertEqual("not_triggered", wayfinder.method_routes["tdd"])

        missing = plan_work(
            WorkRequest(
                explicit=True,
                matt_configured=True,
                required_methods=("tdd",),
                available_methods=(),
            )
        )
        self.assertEqual(("method_capability_missing",), missing.blockers)
        self.assertEqual("missing", missing.method_routes["tdd"])
        self.assertEqual("not_triggered", all_method_routes(("grilling",))["tdd"])

    def test_wayfinder_questions_are_not_truss_execution_contracts(self):
        wayfinder = "## Question\n\nWhich persistence model should the destination use?"
        leaf = """## Parent

#24

## What to build

Ship the selected persistence model.

## Acceptance criteria

- [ ] Persistence behavior is verified.

## Blocked by

None.
"""
        self.assertFalse(parse_issue_contract(wayfinder).ok)
        self.assertFalse(parse_issue_contract(leaf + "\n" + wayfinder).ok)
        snapshot = OutcomeSnapshot.from_mapping(
            {
                "authoritative": True,
                "observed_at": "2026-01-01T00:00:00Z",
                "repository": "owner/repo",
                "issue": {
                    "number": 1, "title": "Decision", "state": "OPEN",
                    "body": wayfinder, "url": "https://github.com/owner/repo/issues/1",
                },
                "assignees": [], "children": [], "blocked_by": [], "blocking": [],
                "closing_prs": [], "comments": [], "source_urls": [],
                "provider_findings": [], "parent": None, "milestone": None,
            }
        )
        self.assertIn("contract_incomplete", derive_digest(snapshot).blockers_or_decisions)
        nested = OutcomeSnapshot.from_mapping(
            {
                **snapshot.to_dict(),
                "issue": {
                    "number": 2, "title": "Executable", "state": "OPEN",
                    "body": leaf, "url": "https://github.com/owner/repo/issues/2",
                },
                "children": [{
                    "number": 1, "title": "Decision", "state": "OPEN",
                    "body": wayfinder, "url": "https://github.com/owner/repo/issues/1",
                    "lifecycle_state": "Blocked",
                }],
            }
        )
        self.assertEqual((), nested.children)


if __name__ == "__main__":
    unittest.main()
