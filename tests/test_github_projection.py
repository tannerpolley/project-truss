import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

class GitHubProjectionTests(unittest.TestCase):
    def test_project_action_uses_native_gh_idempotently_and_rejects_truncation(self):
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
        self.assertNotEqual(0, truncated.returncode)
        self.assertIn("github_capability_missing", truncated.stdout)
        self.assertNotEqual(0, invalid.returncode)


if __name__ == "__main__":
    unittest.main()
