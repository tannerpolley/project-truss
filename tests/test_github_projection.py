import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.lib.truss_github import GitHubClient, GitHubObservationError, ProjectProjection, project_item_membership

ROOT = Path(__file__).resolve().parents[1]

class GitHubProjectionTests(unittest.TestCase):
    def test_project_action_verifies_a_found_item_even_when_the_project_is_truncated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin, marker = root / "bin", root / "member"
            fake_bin.mkdir()
            gh = fake_bin / "gh"
            gh.write_text(
                "#!/usr/bin/env python3\nimport json, os, pathlib, sys\n"
                "args, marker = sys.argv[1:], pathlib.Path(os.environ['TRUSS_MARKER'])\n"
                "if args[:2] == ['project', 'view']:\n"
                " print(json.dumps({'url': 'https://github.example/projects/7'}))\n"
                "elif args[:2] == ['project', 'item-add']:\n marker.write_text('yes'); print('{}')\n"
                "else:\n"
                " items = [{'content': {'url': 'https://github.example/issues/9'}}] if marker.exists() else []\n"
                " total = len(items) + (1 if os.environ.get('TRUSS_TRUNCATED') else 0)\n"
                " print(json.dumps({'items': items, 'totalCount': total}))\n",
                encoding="utf-8",
            )
            gh.chmod(0o755)
            env = dict(os.environ, TRUSS_MARKER=str(marker))
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
            projection = {"owner": "tannerpolley", "project": 7,
                          "url": "https://github.example/issues/9", "ensure": True}
            command = ["bash", str(ROOT / "scripts/project-truss.sh"), "-Action", "Project",
                       "-ProjectionJson", json.dumps(projection)]
            added = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True)
            repeated = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True)
            env["TRUSS_TRUNCATED"] = "1"
            truncated = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True)
            invalid = subprocess.run(
                [*command[:-1], json.dumps({**projection, "owner": None})],
                cwd=root, env=env, text=True, capture_output=True)
        self.assertEqual((0, True, True, "start"), (
            added.returncode, json.loads(added.stdout)["ok"], json.loads(added.stdout)["member"],
            json.loads(added.stdout)["next_skill"]))
        self.assertEqual(0, repeated.returncode)
        self.assertEqual(0, truncated.returncode)
        self.assertTrue(json.loads(truncated.stdout)["member"])
        self.assertNotEqual(0, invalid.returncode)

    def test_project_action_still_blocks_when_a_truncated_page_hides_the_target(self):
        with self.assertRaisesRegex(GitHubObservationError, "github_scope_exceeded"):
            project_item_membership(
                {"items": [], "totalCount": 1},
                "https://github.example/issues/9",
            )

    def test_project_membership_is_advisory_unless_required(self):
        def unavailable(command, timeout):
            return subprocess.CompletedProcess(command, 1, "", "project scope unavailable")

        target = ProjectProjection("tannerpolley", 7, "https://github.example/issues/9", True)
        advisory = GitHubClient(runner=unavailable).project_membership(target)
        self.assertEqual((False, False), (advisory["member"], advisory["required"]))
        with self.assertRaisesRegex(GitHubObservationError, "external_state_unavailable"):
            GitHubClient(runner=unavailable).project_membership(
                ProjectProjection("tannerpolley", 7, target.url, True, required=True)
            )


if __name__ == "__main__":
    unittest.main()
