from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from scripts.lib.workspace_isolation import WorkspaceIsolationError, resolve_workspace_isolation, validate_workspace_receipt


ROOT = Path(__file__).resolve().parents[1]
REQUEST = {"requirement": "required", "repository_identity": "repo:project-truss", "issue_number": 130}


class WorkspaceIsolationTests(unittest.TestCase):
    def receipt(self, **overrides):
        value = {
            "schema_version": 1,
            "provider": "codex_managed_worktree",
            "workspace_id": "workspace-1",
            "repository_root": "/repo",
            "git_common_dir": "/repo/.git",
            "issue_number": 130,
            "task_id": "task-1",
            "thread_id": "thread-1",
            "observed_head": "a" * 40,
            "head_mode": "branch",
            "branch": "codex/issue-130",
            "owner": "codex_app",
            "disposition": "active",
        }
        return {**value, **overrides}

    def expected(self, **overrides):
        source = self.receipt()
        fields = ("provider", "workspace_id", "repository_root", "git_common_dir", "issue_number", "task_id", "thread_id", "owner")
        return {**{field: source[field] for field in fields}, **overrides}

    def validate(self, receipt=None, expected=None, **options):
        validate_workspace_receipt(
            receipt or self.receipt(),
            expected or self.expected(),
            current_head="a" * 40,
            current_branch="codex/issue-130",
            publication=True,
            **options,
        )

    def test_provider_resolution_routes(self):
        cases = (
            ({"codex_project_tasks": True, "native_task_status": "created", "current_workspace": {"provider": "codex_managed_worktree", "repository_identity": "repo:project-truss", "issue_number": 130, "workspace_id": "workspace-1"}}, {"provider": "codex_managed_worktree", "operation": "adopt"}),
            ({"codex_project_tasks": True, "source_task_id": "task-1", "native_task_status": "not_started"}, {"provider": "codex_managed_worktree", "operation": "fork_task"}),
            ({"codex_project_tasks": False, "local_git_worktrees": True, "native_task_status": "not_started"}, {"provider": "local_git_worktree", "operation": "invoke_vanilla_worktree_skill"}),
            ({"codex_project_tasks": False, "local_git_worktrees": False, "native_task_status": "not_started"}, {"provider": "current_checkout", "operation": "adopt"}),
        )
        for capabilities, expected in cases:
            request = {**REQUEST, "requirement": "preferred"} if expected["provider"] == "current_checkout" else REQUEST
            with self.subTest(expected=expected):
                decision = resolve_workspace_isolation(request, capabilities)
                self.assertEqual(expected, {key: decision[key] for key in expected})

    def test_provider_resolution_fails_closed(self):
        cases = (
            ({**REQUEST, "observed_head": "0" * 40}, {"codex_project_tasks": True, "native_task_status": "not_started"}),
            (REQUEST, {"codex_project_tasks": False, "local_git_worktrees": True, "native_task_status": "created"}),
            (REQUEST, {"codex_project_tasks": False, "local_git_worktrees": False, "native_task_status": "not_started"}),
            ({**REQUEST, "issue_number": 0}, {"codex_project_tasks": True, "native_task_status": "not_started"}),
        )
        for request, capabilities in cases:
            with self.subTest(request=request), self.assertRaises(WorkspaceIsolationError):
                resolve_workspace_isolation(request, capabilities)

    def test_workspace_observation_rejects_stale_or_unsafe_identity(self):
        self.validate()
        detached = self.receipt(head_mode="detached", branch=None)
        validate_workspace_receipt(detached, self.expected(), current_head="a" * 40, current_branch="", publication=False)
        with self.assertRaisesRegex(WorkspaceIsolationError, "branch-bound"):
            validate_workspace_receipt(detached, self.expected(), current_head="a" * 40, current_branch="", publication=True)
        mutations = (
            {"provider": "shared_subagent"}, {"owner": "plugin"}, {"schema_version": True},
            {"issue_number": 131}, {"observed_head": "b" * 40}, {"workspace_path": "/caller"},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(WorkspaceIsolationError):
                self.validate({**self.receipt(), **mutation})

    def test_public_launcher_returns_an_untrusted_action_decision(self):
        process = subprocess.run(
            ["bash", str(ROOT / "scripts/workspace-isolation.sh"), "-RepoRoot", str(ROOT), "-RequestJson", json.dumps(REQUEST), "-CapabilitiesJson", json.dumps({"codex_project_tasks": True, "source_task_id": "task-1", "native_task_status": "not_started"})],
            cwd="/tmp",
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)
        payload = json.loads(process.stdout)
        self.assertEqual((True, True, "workspace-isolation-decision", "fork_task"), (payload["ok"], payload["untrusted_request"], payload["phase"], payload["decision"]["operation"]))


if __name__ == "__main__":
    unittest.main()
