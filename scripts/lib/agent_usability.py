"""Validate the four fresh-session Project Truss installed-product receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
import uuid

try:
    from .package_provenance import runtime_contract_hash
except ImportError:
    from package_provenance import runtime_contract_hash


class TrialReceiptError(ValueError):
    pass


SCENARIOS = {"direct", "governed-single", "governed-multi", "premature-closeout"}
REQUIRED = {
    "schema_version", "trial_id", "scenario", "repetition", "worker", "verifier", "package_hash",
    "observed_skill_root", "oracle_path", "oracle_sha256", "trial_root", "project_root",
    "expected_outcome", "observed_outcome", "friction", "user_input_calls", "truss_artifacts",
    "external_mutations", "tool_calls", "source_urls", "blocker", "repository_evidence",
    "worker_claim", "verifier_decision",
}


def _resolve(value: object, base: Path) -> Path:
    path = Path(str(value))
    return (base / path).resolve() if not path.is_absolute() else path.resolve()


def _within(value: object, base: Path) -> Path:
    path = _resolve(value, base)
    try:
        path.relative_to(base.resolve())
    except ValueError as exc:
        raise TrialReceiptError("trial path escaped its declared root") from exc
    return path


def _files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }


def _oracle(receipt: dict[str, Any], plugin_root: Path) -> tuple[dict[str, Any], Path]:
    path = _resolve(receipt["oracle_path"], plugin_root)
    scenario = receipt["scenario"]
    if not path.is_file() or path.name != "oracle.json" or path.parent.name != scenario or path.parent.parent.name != "project-truss-trials":
        raise TrialReceiptError("oracle path is not the canonical scenario oracle")
    if hashlib.sha256(path.read_bytes()).hexdigest() != receipt["oracle_sha256"]:
        raise TrialReceiptError("oracle hash is stale")
    try:
        oracle = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrialReceiptError("scenario oracle is unreadable") from exc
    if oracle.get("scenario") != scenario or oracle.get("expected_outcome") != receipt["expected_outcome"]:
        raise TrialReceiptError("receipt does not match its scenario oracle")
    return oracle, path


def _validate_scenario(receipt: dict[str, Any], oracle: dict[str, Any], oracle_path: Path, project: Path) -> None:
    fixture_root = oracle_path.parent / "fixture"
    fixture = _files(fixture_root)
    actual = _files(project)
    output_path = str((oracle.get("expected_file") or {}).get("path") or "result.json")
    expected_paths = set(fixture) | {output_path}
    if set(actual) != expected_paths:
        raise TrialReceiptError("trial repository contains missing or unexpected artifacts")
    for relative, source in fixture.items():
        if relative != output_path and source.read_bytes() != actual[relative].read_bytes():
            raise TrialReceiptError("scenario fixture was mutated")
    artifacts = receipt["truss_artifacts"]
    if not isinstance(artifacts, list) or any(not isinstance(item, str) for item in artifacts):
        raise TrialReceiptError("Project Truss artifacts must be observed paths")
    if artifacts:
        raise TrialReceiptError("trial created Project Truss artifacts")
    if receipt["scenario"] == "direct":
        if receipt["source_urls"]:
            raise TrialReceiptError("direct work invented governed source links")
        if actual[output_path].read_text(encoding="utf-8") != oracle["expected_file"]["text"]:
            raise TrialReceiptError("direct edit did not reach the oracle result")
        return
    try:
        result = json.loads(actual[output_path].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrialReceiptError("scenario result is not valid JSON") from exc
    if result.get("source_urls") != receipt["source_urls"]:
        raise TrialReceiptError("receipt source URLs do not match repository evidence")
    snapshot = json.loads((fixture_root / "snapshot.json").read_text(encoding="utf-8"))
    if receipt["source_urls"] != snapshot.get("source_urls"):
        raise TrialReceiptError("scenario source URLs do not match the fixture")
    if len(receipt["source_urls"]) < int(oracle.get("minimum_source_urls", 0)):
        raise TrialReceiptError("scenario source URL threshold was not met")
    if receipt["scenario"].startswith("governed-"):
        required = {"lane", "layers", "source", "ready_frontier", "blockers", "next_action", "source_urls"}
        if not required.issubset(result) or result["lane"] != "governed" or result["layers"] != oracle["layers"]:
            raise TrialReceiptError("governed result does not match the planned layers")
        if result["source"] != "fixture" or result["ready_frontier"] != []:
            raise TrialReceiptError("non-authoritative fixture leaked an actionable frontier")
        if not isinstance(result["blockers"], list) or not set(oracle.get("required_blockers", [])).issubset(result["blockers"]):
            raise TrialReceiptError("governed result lost required blockers")
        if len(result.get("dependency_edges", [])) < int(oracle.get("minimum_dependency_edges", 0)) or result.get("dependency_edges", []) != snapshot.get("trial_dependency_edges", []):
            raise TrialReceiptError("governed result lost dependency evidence")
    elif not isinstance(result.get("findings"), list) or not set(oracle.get("required_findings", [])).issubset(result["findings"]):
        raise TrialReceiptError("premature closeout was not contradicted by evidence")


def validate_trial_receipt(receipt: dict[str, Any], plugin_root: Path) -> None:
    missing = sorted(REQUIRED - set(receipt))
    unknown = sorted(set(receipt) - REQUIRED)
    if missing or unknown:
        detail = ("missing=" + ",".join(missing)) if missing else ("unknown=" + ",".join(unknown))
        raise TrialReceiptError("invalid receipt fields: " + detail)
    scenario = receipt.get("scenario")
    if type(receipt.get("schema_version")) is not int or receipt["schema_version"] != 1 or scenario not in SCENARIOS or type(receipt.get("repetition")) is not int or receipt["repetition"] != 1:
        raise TrialReceiptError("invalid trial schema, scenario, or repetition")
    if receipt.get("trial_id") != f"{scenario}-1":
        raise TrialReceiptError("trial id does not bind the canonical scenario")
    if receipt.get("expected_outcome") not in {"pass", "blocked"} or receipt.get("observed_outcome") != receipt.get("expected_outcome"):
        raise TrialReceiptError("observed outcome does not match the scenario oracle")
    root = plugin_root.resolve()
    if _resolve(receipt["observed_skill_root"], root) != root or receipt.get("package_hash") != runtime_contract_hash(root):
        raise TrialReceiptError("trial did not observe the current installed package")
    agent_ids = []
    for role in ("worker", "verifier"):
        value = str((receipt.get(role) or {}).get("id", ""))
        try:
            uuid.UUID(value)
        except (ValueError, AttributeError) as exc:
            raise TrialReceiptError(f"{role} id must be an actual Codex session id") from exc
        agent_ids.append(value)
    if agent_ids[0] == agent_ids[1]:
        raise TrialReceiptError("worker and verifier must be independent agents")
    trial_root = _resolve(receipt["trial_root"], root)
    project = _within(receipt["project_root"], trial_root)
    if type(receipt.get("friction")) is not int or not 1 <= receipt["friction"] <= 5:
        raise TrialReceiptError("friction must be an integer from 1 through 5")
    if type(receipt.get("user_input_calls")) is not int or type(receipt.get("external_mutations")) is not int or receipt["user_input_calls"] != 0 or receipt["external_mutations"] != 0:
        raise TrialReceiptError("trial crossed a forbidden boundary")
    if not isinstance(receipt.get("tool_calls"), list) or any(not isinstance(item, str) for item in receipt["tool_calls"]):
        raise TrialReceiptError("tool calls must come from the Codex event stream")
    if not isinstance(receipt.get("source_urls"), list) or any(not str(item).startswith(("https://", "http://")) for item in receipt["source_urls"]):
        raise TrialReceiptError("source URLs are invalid")
    required_blocker = "state_contradiction" if scenario == "premature-closeout" else None
    if receipt.get("blocker") != required_blocker:
        raise TrialReceiptError("scenario blocker does not match the oracle")
    evidence = receipt.get("repository_evidence")
    if not isinstance(evidence, list) or not evidence:
        raise TrialReceiptError("repository evidence is required")
    evidence_paths = set()
    for item in evidence:
        relative = Path(str((item or {}).get("path", "")))
        if relative.is_absolute():
            raise TrialReceiptError("repository evidence paths must be relative")
        path = _within(project / relative, project)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != str((item or {}).get("sha256", "")):
            raise TrialReceiptError("repository evidence is missing or stale")
        evidence_paths.add(relative.as_posix())
    if evidence_paths != set(_files(project)) or len(evidence_paths) != len(evidence):
        raise TrialReceiptError("repository evidence inventory is incomplete or duplicated")
    claim = receipt.get("worker_claim")
    if not isinstance(claim, dict) or not isinstance(claim.get("summary"), str) or not claim["summary"].strip():
        raise TrialReceiptError("worker claim summary is required")
    if receipt.get("verifier_decision") != receipt.get("expected_outcome"):
        raise TrialReceiptError("independent verifier did not confirm the outcome")
    oracle, oracle_path = _oracle(receipt, root)
    _validate_scenario(receipt, oracle, oracle_path, project)


def validate_trial_set(receipts: list[dict[str, Any]], plugin_root: Path) -> dict[str, Any]:
    scenarios = [str(item.get("scenario")) for item in receipts]
    if len(set(scenarios)) != len(scenarios):
        raise TrialReceiptError("duplicate scenario receipt")
    if len(receipts) != len(SCENARIOS):
        raise TrialReceiptError("canonical trial set requires exactly four receipts")
    if set(scenarios) != SCENARIOS:
        raise TrialReceiptError("canonical trial set is incomplete")
    for receipt in receipts:
        validate_trial_receipt(receipt, plugin_root)
    identities = [str(receipt[role]["id"]) for receipt in receipts for role in ("worker", "verifier")]
    if len(set(identities)) != len(identities):
        raise TrialReceiptError("fresh agents must not be reused across scenarios")
    friction = sorted(item["friction"] for item in receipts)
    median = (friction[1] + friction[2]) / 2
    if median > 2:
        raise TrialReceiptError("median trial friction exceeds 2")
    return {"scenarios": sorted(SCENARIOS), "receipts": 4, "median_friction": median, "user_input_calls": 0, "external_mutations": 0}
