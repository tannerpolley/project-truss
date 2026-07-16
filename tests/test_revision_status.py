import json
import subprocess
import unittest
from pathlib import Path

from scripts.lib.revision_status import evaluate_revision_status

ROOT = Path(__file__).resolve().parents[1]


class RevisionStatusTests(unittest.TestCase):
    def base(self):
        return {
            "source_dirty": False,
            "validation_current": True,
            "source_committed": True,
            "deployment_current": True,
            "installation_current": True,
            "cleanup_current": True,
            "fresh_session_acknowledged": True,
        }

    def test_six_states_name_one_exact_next_gate(self):
        cases = [
            ({"validation_current": False}, ("validation-required", "run-validation")),
            ({"source_dirty": True, "source_committed": False}, ("commit-required", "commit-source")),
            ({"deployment_current": False}, ("deployment-stale", "sync-live")),
            ({"installation_current": False}, ("installation-stale", "refresh-plugin")),
            ({"cleanup_current": False}, ("cleanup-required", "run-cleanup")),
            ({"fresh_session_acknowledged": False}, ("fresh-session-required", "start-fresh-session")),
        ]
        for changes, expected in cases:
            with self.subTest(expected=expected):
                evidence = self.base()
                evidence.update(changes)
                status = evaluate_revision_status(evidence)
                self.assertEqual(expected, (status["state"], status["next_gate"]))
                self.assertEqual(changes.get("fresh_session_acknowledged") is False, status["fresh_session_required"])

    def test_complete_state_has_no_next_gate(self):
        status = evaluate_revision_status(self.base())
        self.assertEqual("complete", status["state"])
        self.assertIsNone(status["next_gate"])

    def test_public_status_command_is_read_only(self):
        evidence = self.base()
        evidence["deployment_current"] = False
        before = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, text=True, capture_output=True, check=True).stdout
        process = subprocess.run(
            ["bash", str(ROOT / "scripts" / "get-agent-plugin-version.sh"), "-RepoRoot", str(ROOT), "-RevisionStatus", "-RevisionEvidenceJson", json.dumps(evidence)],
            cwd="/tmp",
            text=True,
            capture_output=True,
        )
        after = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, text=True, capture_output=True, check=True).stdout
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)
        self.assertEqual("sync-live", json.loads(process.stdout)["next_gate"])
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
