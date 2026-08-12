from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts.lib.command_support import Context
from scripts.lib.commands.project import command_project_truss
from scripts.lib.scientific_evidence import issue_body_sha256, validate_benchmark_case, validate_evidence_packet
from scripts.lib.truss_policy import FinalHealth, OutcomeSnapshot, closeout_findings, derive_state, parse_issue_contract


ROOT = Path(__file__).resolve().parents[1]
SCIENTIFIC_BODY = """## Claim to Establish

The dilute limit approaches the analytical ideal relation; failure to converge falsifies the claim.

## Inputs and Sources

Analytical derivation, SI units, model revision v1, and a documented density sequence.

## Experiment or Implementation

Evaluate decreasing densities and compare with the independent analytical limit.

## Acceptance and Falsification Criteria

- [x] Classify the claim from reproducible evidence, including a supported negative result.

## Required Evidence

Source, formulation, comparison tolerance, certificates, raw artifacts, hashes, and all Science review dimensions.

## Blocked by

None — can start immediately.
"""
SCIENTIFIC_ROOT = """## Scientific Question

Does the model recover the analytical limit?

## Falsifiable Claims

- The output converges to the analytical value; persistent deviation falsifies the claim.

## Evidence and Sources

Primary derivation and versioned inputs.

## Mathematical or Numerical Formulation

Evaluate the declared limiting sequence.

## Benchmark and Validation Plan

Compare with an independent analytical oracle.

## Acceptance and Falsification Criteria

- [ ] Classify the claim from reproducible evidence.

## Out of Scope

Unrelated model families.

## Further Notes

Negative results are valid outcomes.
"""


def benchmark():
    return {
        "schema_version": 1,
        "claim_id": "C-1",
        "title": "Dilute analytical limit",
        "claim": {"type": "limiting_case", "statement": "Z tends to one."},
        "source": {"class": "analytic", "locator": {"document": "CONTEXT.md"}},
        "oracle": {
            "class": "analytic",
            "independence_rationale": "Derived without the implementation.",
            "claimed_independent": True,
        },
        "inputs": {"density": [1e-3, 1e-4]},
        "comparisons": [{
            "quantity": "Z", "metric": "absolute_error", "atol": 1e-8, "rtol": 1e-8,
            "tolerance_basis": "Truncation estimate plus floating-point roundoff.",
        }],
        "certificates": ["monotone convergence"],
        "failure_meaning": "The residual term fails to vanish.",
        "provenance": {"repository_revision": "a" * 40, "command": "python check.py", "environment": "lock:123"},
    }


def packet(digest: str):
    return {
        "schema_version": 1,
        "github_issue": 1,
        "issue_body_sha256": issue_body_sha256(SCIENTIFIC_BODY),
        "claim_id": "C-1",
        "classification": "FALSIFIED",
        "source_locators": ["CONTEXT.md#dilute-limit"],
        "assumptions": ["SI units"],
        "repository_revision": "a" * 40,
        "model_revision": "model-v1",
        "input_revision": "inputs-v2",
        "command": "python check.py",
        "environment": "lock:123",
        "raw_results": ["results.json"],
        "comparisons": [{
            "quantity": "Z", "metric": "absolute_error", "atol": 1e-8, "rtol": 1e-8,
            "tolerance_basis": "Truncation estimate plus floating-point roundoff.",
        }],
        "certificates": ["residual did not converge"],
        "limitations": ["Only the declared domain was tested."],
        "dimensions": {
            "source": {"state": "verified", "evidence": ["CONTEXT.md#dilute-limit"]},
            "formulation": {"state": "verified", "evidence": ["derivation.md"]},
            "numerical_verification": {"state": "verified", "evidence": ["results.json"]},
            "empirical_validation": {"state": "outside_scope", "evidence": []},
            "reproducibility": {"state": "reproducible", "evidence": ["lock:123"]},
            "implementation_promotion": {"state": "experimental_only", "evidence": ["issue#1"]},
        },
        "scientific_review": {
            "reviewer": "owner",
            "verdict": "passed",
            "basis": ["source", "formulation", "numerical_verification", "empirical_validation", "reproducibility", "implementation_promotion"],
        },
        "artifact_hashes": {"results.json": digest},
    }


class ScientificEvidenceTests(unittest.TestCase):
    def test_benchmark_distinguishes_independent_science_from_change_detection(self):
        valid = validate_benchmark_case(benchmark())
        self.assertTrue(valid.ok)
        self.assertEqual("independent", valid.evidence["oracle_strength"])
        snapshot = benchmark()
        snapshot["oracle"] = {
            "class": "change_detection_only", "independence_rationale": "Same implementation output.",
            "claimed_independent": True,
        }
        invalid = validate_benchmark_case(snapshot)
        self.assertIn("change_detection_claimed_independent", invalid.findings)
        snapshot["oracle"]["claimed_independent"] = False
        self.assertEqual("change_detection", validate_benchmark_case(snapshot).evidence["oracle_strength"])

    def test_benchmark_rejects_nonfinite_or_unjustified_tolerance_and_missing_provenance(self):
        case = benchmark()
        case["comparisons"][0]["atol"] = float("nan")
        case["comparisons"][0]["tolerance_basis"] = ""
        case["provenance"]["environment"] = ""
        findings = validate_benchmark_case(case).findings
        self.assertIn("comparison_0_definition_invalid", findings)
        self.assertIn("comparison_0_tolerance_invalid", findings)
        self.assertIn("provenance_incomplete", findings)

    def test_falsified_packet_is_complete_only_with_reproducible_hashed_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "results.json"
            artifact.write_text('{"Z": 1.2}\n', encoding="utf-8")
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            valid = validate_evidence_packet(packet(digest), root)
            self.assertTrue(valid.ok)
            self.assertTrue(valid.evidence["negative_result_is_complete"])
            invalid = validate_evidence_packet(packet("0" * 64), root)
            self.assertIn("evidence_artifact_mismatch", invalid.findings)
            inconsistent = packet(digest)
            inconsistent["dimensions"]["numerical_verification"]["state"] = "failed"
            self.assertIn("classification_dimension_conflict", validate_evidence_packet(inconsistent, root).findings)
            unhashed = packet(digest)
            unhashed["raw_results"].append("trace.json")
            self.assertIn("raw_result_hash_missing", validate_evidence_packet(unhashed, root).findings)
            source_limited = packet(digest)
            source_limited.update({
                "classification": "SOURCE_INSUFFICIENT", "raw_results": [],
                "comparisons": [], "certificates": [], "artifact_hashes": {},
                "model_revision": "", "input_revision": "",
            })
            source_limited["dimensions"]["source"] = {"state": "insufficient", "evidence": ["search-log.md"]}
            source_limited["dimensions"]["formulation"] = {"state": "not_applicable", "evidence": []}
            source_limited["dimensions"]["numerical_verification"] = {"state": "not_applicable", "evidence": []}
            self.assertTrue(validate_evidence_packet(source_limited, root).ok)

    def test_scientific_contract_and_closeout_require_evidence_and_science_review(self):
        contract = parse_issue_contract(SCIENTIFIC_BODY)
        self.assertEqual(("scientific-computing", "standalone", True), (contract.profile, contract.kind, contract.ok))
        leaf = parse_issue_contract("## Parent\n\n#9\n\n" + SCIENTIFIC_BODY)
        root = parse_issue_contract(SCIENTIFIC_ROOT)
        self.assertEqual(("scientific-computing", "leaf", True), (leaf.profile, leaf.kind, leaf.ok))
        self.assertEqual(("scientific-computing", "root", True, False), (root.profile, root.kind, root.ok, root.acceptance_complete))
        current = OutcomeSnapshot.from_mapping({
            "authoritative": True, "observed_at": "2026-08-12T00:00:00Z", "repository": "owner/repo",
            "issue": {"number": 1, "title": "Limit", "state": "CLOSED", "body": SCIENTIFIC_BODY, "url": "https://example/issues/1"},
            "assignees": ["owner"], "children": [], "blocked_by": [], "blocking": [], "comments": [],
            "closing_prs": [{"number": 2, "state": "MERGED", "url": "https://example/pull/2", "merged": True,
                             "merged_at": "2026-08-12T00:00:00Z", "head_sha": "a" * 40, "checks_complete": False,
                             "checks_successful": False, "review_decision": "APPROVED"}],
            "source_urls": [], "provider_findings": [],
        })
        health = FinalHealth(True, True, True, "a" * 40, review_passed=True)
        self.assertEqual(("scientific_evidence_missing",), closeout_findings(current, health))
        unproven = OutcomeSnapshot.from_mapping({**current.to_dict(), "closing_prs": []})
        self.assertEqual("Blocked", derive_state(unproven))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "results.json"
            artifact.write_text("negative\n", encoding="utf-8")
            evidence = validate_evidence_packet(
                packet(hashlib.sha256(artifact.read_bytes()).hexdigest()), root,
                packet_path="evidence.json",
            )
            reviewed = OutcomeSnapshot.from_mapping({
                **current.to_dict(),
                "comments": [{"author": "owner", "body": evidence.receipt(), "created_at": "2026-08-12T00:00:00Z", "url": "https://example/comment/1"}],
            })
            passed = FinalHealth(True, True, True, "a" * 40, review_passed=True)
            self.assertEqual((), closeout_findings(reviewed, passed, evidence))
            failed_review_data = packet(hashlib.sha256(artifact.read_bytes()).hexdigest())
            failed_review_data["scientific_review"]["verdict"] = "failed"
            failed_review = validate_evidence_packet(failed_review_data, root, packet_path="failed-review.json")
            failed_snapshot = OutcomeSnapshot.from_mapping({
                **current.to_dict(),
                "comments": [{"author": "owner", "body": failed_review.receipt(), "created_at": "2026-08-12T00:00:00Z", "url": "https://example/comment/2"}],
            })
            self.assertEqual((("scientific_evidence_missing", "scientific_review_failed"), "Blocked"), (closeout_findings(failed_snapshot, passed, failed_review), derive_state(failed_snapshot)))
            research_only = OutcomeSnapshot.from_mapping({**reviewed.to_dict(), "closing_prs": []})
            science_only = FinalHealth(True, True, True, "")
            self.assertEqual((), closeout_findings(research_only, science_only, evidence))
            stale_data = research_only.to_dict(); stale_data["issue"]["body"] += "\nchanged"; stale = OutcomeSnapshot.from_mapping(stale_data)
            self.assertEqual(("Done", "Blocked"), (derive_state(research_only), derive_state(stale)))

    def test_research_only_closeout_needs_no_implementation_receipt_or_pull_request(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); root = base / "project"; remote = base / "remote.git"; root.mkdir()
            subprocess.run(["git", "init", "--bare", "-q", remote], check=True); subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
            (root / "README.md").write_text("science\n", encoding="utf-8"); subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
            subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "base"], cwd=root, check=True)
            subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=root, check=True); subprocess.run(["git", "push", "-qu", "origin", "main"], cwd=root, check=True); subprocess.run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=remote, check=True)
            revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            artifact = root / "results.json"; artifact.write_text("negative\n", encoding="utf-8")
            evidence_data = packet(hashlib.sha256(artifact.read_bytes()).hexdigest())
            evidence_data["repository_revision"] = revision
            evidence_path = root / "evidence.json"; evidence_path.write_text(json.dumps({"issues": {"1": evidence_data}}), encoding="utf-8")
            subprocess.run(["git", "add", "evidence.json", "results.json"], cwd=root, check=True)
            subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "record evidence"], cwd=root, check=True)
            subprocess.run(["git", "push", "-q", "origin", "main"], cwd=root, check=True)
            context = Context(ROOT / "scripts/project-truss.sh", ROOT, "", "", [], invocation_cwd=root); validated_output = StringIO()
            with redirect_stdout(validated_output):
                self.assertEqual(0, command_project_truss(context, {"Action": "ValidateScientificEvidence", "ScientificEvidencePath": "evidence.json"}))
            validated = json.loads(validated_output.getvalue())
            current = OutcomeSnapshot.from_mapping({
                "authoritative": True, "observed_at": "2026-08-12T00:00:00Z", "repository": "owner/repo",
                "issue": {"number": 1, "title": "Limit", "state": "CLOSED", "body": SCIENTIFIC_BODY, "url": "https://example/issues/1"},
                "assignees": ["owner"], "children": [], "blocked_by": [], "blocking": [], "closing_prs": [],
                "comments": [{"author": "owner", "body": validated["receipts"]["1"], "created_at": "2026-08-12T00:00:00Z", "url": "https://example/comment/1"}],
                "source_urls": [], "provider_findings": [],
            })
            health = json.dumps({"verification_passed": True, "integration_healthy": True, "source_clean": True, "head_sha": ""})
            output = StringIO()
            with mock.patch("scripts.lib.commands.project.GitHubClient") as github, redirect_stdout(output):
                github.return_value.snapshot.return_value = current
                code = command_project_truss(context, {
                    "Action": "Closeout", "Repository": "owner/repo", "Issue": 1,
                    "ScientificEvidencePath": "evidence.json", "HealthJson": health,
                })
            payload = json.loads(output.getvalue())
            self.assertEqual((0, True, []), (code, payload["ok"], payload["findings"]))
            self.assertEqual("return to Start and re-read scientific closeout", payload["continuation"]["next_action"])
            output = StringIO()
            with mock.patch("scripts.lib.commands.project.GitHubClient") as github, redirect_stdout(output):
                github.return_value.snapshot.return_value = current
                status_code = command_project_truss(context, {
                    "Action": "Status", "Repository": "owner/repo", "Issue": 1,
                })
            status = json.loads(output.getvalue())
            self.assertEqual((0, "No action; the current outcome is done."), (status_code, status["next_safe_action"]))


if __name__ == "__main__":
    unittest.main()
