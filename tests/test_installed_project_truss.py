from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.lib.agent_usability import TrialReceiptError, validate_trial_set
from scripts.lib.package_provenance import runtime_contract_hash
from scripts.run_agent_usability_trials_support import _initialize_trial_repository, build_worker_prompt


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = Path(os.environ.get("PROJECT_TRUSS_INSTALLED_ROOT", ROOT)).resolve()
SCENARIOS = {"direct", "governed-single", "governed-multi", "missing-method-capability", "premature-closeout"}
SKILLS = {"start", "shape", "resolve", "close", "advanced-user-input"}


class InstalledProjectTrussTests(unittest.TestCase):
    def test_installed_surface_has_one_front_door_and_five_scenarios(self):
        manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(("project-truss", "2.0.0"), (manifest["name"], manifest["version"]))
        self.assertEqual(["Use $project-truss:start only for explicit or hard-trigger governed work; ordinary coding stays direct."], manifest["interface"]["defaultPrompt"])
        self.assertEqual(SKILLS, {path.parent.name for path in (PLUGIN_ROOT / "skills").glob("*/SKILL.md")})
        trial_root = ROOT / "tests" / "project-truss-trials"
        self.assertEqual(SCENARIOS, {path.name for path in trial_root.iterdir() if path.is_dir()})
        for scenario in SCENARIOS:
            self.assertTrue((trial_root / scenario / "prompt.md").is_file())
            self.assertTrue((trial_root / scenario / "oracle.json").is_file())

    def test_trial_repository_initialization_preserves_fixture(self):
        scenario_root = ROOT / "tests" / "project-truss-trials" / "governed-single"
        prompt = build_worker_prompt((scenario_root / "prompt.md").read_text(encoding="utf-8"), PLUGIN_ROOT, "result.json")
        self.assertIn("mapping Status `blockers_or_decisions` to result `blockers`. `snapshot.json` is an immutable input fixture, not a generated artifact: preserve it unchanged.", prompt)
        self.assertIn("Copied fixture files other than `result.json` are immutable inputs; preserve them unchanged.", prompt)
        self.assertIn("mapping Status `blockers_or_decisions` to result `blockers`.", (ROOT / "tests" / "project-truss-trials" / "governed-multi" / "prompt.md").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            shutil.copytree(scenario_root / "fixture", project)
            snapshot = (project / "snapshot.json").read_bytes()
            _initialize_trial_repository(project)
            self.assertEqual(snapshot, (project / "snapshot.json").read_bytes())
            tracked = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "HEAD"], cwd=project, text=True)
            self.assertIn("snapshot.json", tracked.splitlines())
            with mock.patch("scripts.run_agent_usability_trials_support.subprocess.run", return_value=subprocess.CompletedProcess([], 1, stderr="denied")):
                with self.assertRaisesRegex(RuntimeError, "could not initialize trial Git repository: denied"):
                    _initialize_trial_repository(project)

    def test_canonical_trial_set_covers_direct_resolution_capability_and_closeout(self):
        receipts = []
        with tempfile.TemporaryDirectory() as directory:
            trial_root = Path(directory)
            for index, scenario in enumerate(sorted(SCENARIOS), 1):
                run_root = trial_root / scenario
                project = run_root / "project"
                scenario_root = ROOT / "tests" / "project-truss-trials" / scenario
                shutil.copytree(scenario_root / "fixture", project)
                oracle_path = ROOT / "tests" / "project-truss-trials" / scenario / "oracle.json"
                oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
                expected = "blocked" if scenario in {"missing-method-capability", "premature-closeout"} else "pass"
                source_urls = []
                if scenario == "direct":
                    (project / "result.txt").write_text("complete\n", encoding="utf-8")
                elif scenario == "missing-method-capability":
                    result_payload = {
                        "lane": "governed",
                        "blockers": ["method_capability_missing"],
                        "source_urls": [],
                    }
                    (project / "result.json").write_text(
                        json.dumps(result_payload) + "\n",
                        encoding="utf-8",
                    )
                else:
                    source_urls = json.loads((project / "snapshot.json").read_text(encoding="utf-8"))["source_urls"]
                    result_payload = {"source_urls": source_urls}
                    if scenario.startswith("governed-"):
                        result_payload.update({
                            "lane": "governed", "layers": oracle["layers"], "source": "fixture",
                            "ready_frontier": [], "blockers": ["external_state_unavailable"], "next_action": "Stop on copied evidence.",
                        })
                        if scenario == "governed-multi":
                            result_payload["dependency_edges"] = [{"blocked": 302, "blocked_by": 301}]
                    else:
                        result_payload["findings"] = oracle["required_findings"]
                    (project / "result.json").write_text(json.dumps(result_payload) + "\n", encoding="utf-8")
                evidence = [
                    {"path": path.relative_to(project).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                    for path in sorted(project.rglob("*")) if path.is_file()
                ]
                receipts.append({
                    "schema_version": 1,
                    "trial_id": f"{scenario}-1",
                    "scenario": scenario,
                    "repetition": 1,
                    "worker": {"id": f"00000000-0000-4000-8000-{index:012d}"},
                    "verifier": {"id": f"00000000-0000-4000-8000-{index + 10:012d}"},
                    "package_hash": runtime_contract_hash(PLUGIN_ROOT),
                    "observed_skill_root": str(PLUGIN_ROOT),
                    "oracle_path": str(oracle_path),
                    "oracle_sha256": hashlib.sha256(oracle_path.read_bytes()).hexdigest(),
                    "trial_root": str(run_root),
                    "project_root": str(project),
                    "expected_outcome": expected,
                    "observed_outcome": expected,
                    "friction": 1,
                    "user_input_calls": 0,
                    "truss_artifacts": [],
                    "external_mutations": 0,
                    "tool_calls": [] if scenario == "direct" else ["command_execution"],
                    "source_urls": source_urls,
                    "blocker": {
                        "premature-closeout": "state_contradiction",
                        "missing-method-capability": "method_capability_missing",
                    }.get(scenario),
                    "repository_evidence": evidence,
                    "worker_claim": {"summary": scenario},
                    "verifier_decision": expected,
                })
            summary = validate_trial_set(receipts, PLUGIN_ROOT)
            self.assertEqual(SCENARIOS, set(summary["scenarios"]))
            duplicate = copy.deepcopy(receipts)
            duplicate.append({**copy.deepcopy(receipts[0]), "trial_id": "duplicate"})
            with self.assertRaisesRegex(TrialReceiptError, "duplicate"):
                validate_trial_set(duplicate, PLUGIN_ROOT)


if __name__ == "__main__":
    unittest.main()
