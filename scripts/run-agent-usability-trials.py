#!/usr/bin/env python3
"""Run the five Project Truss scenarios against the installed plugin."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from agent_usability import TrialReceiptError, validate_trial_receipt, validate_trial_set
from package_provenance import runtime_contract_hash
from run_agent_usability_trials_support import VERIFIER_SCHEMA, WORKER_SCHEMA, _initialize_trial_repository, build_worker_prompt, summarize_observed_events


def installed_plugin_root() -> Path:
    result = subprocess.run(["codex", "plugin", "list", "--json"], text=True, capture_output=True, stdin=subprocess.DEVNULL)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "could not inspect installed plugins")
    installed = json.loads(result.stdout).get("installed", [])
    matches = [item for item in installed if item.get("pluginId") == "project-truss@personal" and item.get("installed") and item.get("enabled")]
    if len(matches) != 1:
        raise RuntimeError("project-truss@personal must be the one enabled Project Truss installation")
    root = Path(str((matches[0].get("source") or {}).get("path", ""))).resolve()
    manifest = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    if (manifest.get("name"), manifest.get("version")) != ("project-truss", "2.0.0"):
        raise RuntimeError("installed Project Truss identity is not 2.0.0")
    return root


def invoke_agent(project: Path, prompt: str, schema: Path, output: Path, events_path: Path, sandbox: str) -> tuple[dict, str, list[dict]]:
    result = subprocess.run(
        ["codex", "exec", "--ephemeral", "--json", "--color", "never", "--sandbox", sandbox, "--skip-git-repo-check", "-C", str(project), "--output-schema", str(schema), "--output-last-message", str(output), prompt],
        cwd=project, text=True, capture_output=True, stdin=subprocess.DEVNULL)
    events_path.write_text(result.stdout, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Codex agent failed")
    try:
        events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        session = next(str(event["thread_id"]) for event in events if event.get("type") == "thread.started")
        response = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, KeyError, StopIteration) as exc:
        raise RuntimeError("Codex agent did not emit a valid event stream and structured result") from exc
    return response, session, events


def _evidence(project: Path) -> list[dict[str, str]]:
    return [
        {"path": path.relative_to(project).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in sorted(project.rglob("*"))
        if path.is_file() and ".git" not in path.parts
    ]


def run_trial(plugin_root: Path, output_dir: Path, scenario_dir: Path, worker_schema: Path, verifier_schema: Path) -> Path:
    oracle_path = scenario_dir / "oracle.json"
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    scenario = str(oracle.get("scenario") or "")
    expected = str(oracle.get("expected_outcome") or "")
    if scenario != scenario_dir.name or expected not in {"pass", "blocked"} or not (scenario_dir / "prompt.md").is_file():
        raise ValueError(f"invalid canonical scenario: {scenario_dir}")
    receipt_root = output_dir / "runs" / f"{scenario}-1"
    fixture = scenario_dir / "fixture"
    with tempfile.TemporaryDirectory(prefix=f"project-truss-{scenario}-") as directory:
        execution_root = Path(directory)
        project = execution_root / "project"
        shutil.copytree(fixture, project)
        _initialize_trial_repository(project)
        output_path = str((oracle.get("expected_file") or {}).get("path") or "result.json")
        prompt = build_worker_prompt((scenario_dir / "prompt.md").read_text(encoding="utf-8"), plugin_root, output_path)
        worker_output = execution_root / "worker-output.json"
        worker_events = execution_root / "worker-events.jsonl"
        worker, worker_id, worker_stream = invoke_agent(project, prompt, worker_schema, worker_output, worker_events, "workspace-write")
        worker_metrics = summarize_observed_events(worker_stream)
        fixture_paths = {path.relative_to(fixture).as_posix() for path in fixture.rglob("*") if path.is_file()}
        actual_paths = {path.relative_to(project).as_posix() for path in project.rglob("*") if path.is_file() and ".git" not in path.parts}
        artifacts = sorted(actual_paths - fixture_paths - {output_path})
        verifier_prompt = (
            f"Independently verify `{project}` against untouched oracle `{oracle_path}` and installed package `{plugin_root}`. "
            f"Inspect the worker event log `{worker_events}`. Observed metrics: {json.dumps(worker_metrics, sort_keys=True)}. "
            "Reject source-checkout reads, unexpected artifacts, questions, external writes, or a result unsupported by current files. "
            f"Return `{expected}` only when the oracle is proven; otherwise return `reject`. Do not trust the worker narrative."
        )
        verifier_output = execution_root / "verifier-output.json"
        verifier_events = execution_root / "verifier-events.jsonl"
        verifier, verifier_id, verifier_stream = invoke_agent(project, verifier_prompt, verifier_schema, verifier_output, verifier_events, "read-only")
        verifier_metrics = summarize_observed_events(verifier_stream)
        shutil.copytree(execution_root, receipt_root)
    project = receipt_root / "project"
    receipt = {
        "schema_version": 1,
        "trial_id": f"{scenario}-1",
        "scenario": scenario,
        "repetition": 1,
        "worker": {"id": worker_id},
        "verifier": {"id": verifier_id},
        "package_hash": runtime_contract_hash(plugin_root),
        "observed_skill_root": worker["observed_skill_root"],
        "oracle_path": str(oracle_path.resolve()),
        "oracle_sha256": hashlib.sha256(oracle_path.read_bytes()).hexdigest(),
        "trial_root": str(receipt_root),
        "project_root": str(project),
        "expected_outcome": expected,
        "observed_outcome": worker["observed_outcome"],
        "friction": worker["friction"],
        "user_input_calls": int(worker_metrics["user_input_calls"]) + int(verifier_metrics["user_input_calls"]),
        "truss_artifacts": artifacts,
        "external_mutations": int(worker_metrics["external_mutations"]) + int(verifier_metrics["external_mutations"]),
        "tool_calls": [f"worker:{name}" for name in worker_metrics["tool_calls"]] + [f"verifier:{name}" for name in verifier_metrics["tool_calls"]],
        "source_urls": worker["source_urls"],
        "blocker": worker["blocker"],
        "repository_evidence": _evidence(project),
        "worker_claim": worker["claim"],
        "verifier_decision": verifier["decision"],
    }
    validate_trial_receipt(receipt, plugin_root)
    receipt_path = receipt_root / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--parallelism", type=int, default=2)
    args = parser.parse_args()
    if not args.execute:
        parser.error("--execute is required because this command starts fresh Codex agents")
    if shutil.which("codex") is None or not 1 <= args.parallelism <= 4:
        parser.error("codex is required and parallelism must be 1-4")
    source_root = Path(__file__).resolve().parents[1]
    output_dir = Path(args.output_dir).resolve()
    try:
        relative_output = output_dir.relative_to(source_root)
    except ValueError:
        parser.error("--output-dir must be inside the Project Truss source root")
    if not relative_output.parts or relative_output.parts[0] != ".project-truss":
        parser.error("--output-dir must be under .project-truss")
    try:
        plugin_root = installed_plugin_root()
        if plugin_root == source_root:
            raise RuntimeError("installed-product trials cannot use the source checkout")
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True)
        worker_schema = output_dir / "worker-output.schema.json"
        verifier_schema = output_dir / "verifier-output.schema.json"
        worker_schema.write_text(json.dumps(WORKER_SCHEMA, indent=2) + "\n", encoding="utf-8")
        verifier_schema.write_text(json.dumps(VERIFIER_SCHEMA, indent=2) + "\n", encoding="utf-8")
        scenarios = sorted((source_root / "tests" / "project-truss-trials").iterdir())
        with ThreadPoolExecutor(max_workers=args.parallelism) as executor:
            receipt_paths = list(executor.map(lambda path: run_trial(plugin_root, output_dir, path, worker_schema, verifier_schema), scenarios))
        receipts = [json.loads(path.read_text(encoding="utf-8")) for path in receipt_paths]
        metrics = validate_trial_set(receipts, plugin_root)
    except (OSError, ValueError, RuntimeError, TrialReceiptError, json.JSONDecodeError) as exc:
        parser.exit(1, f"agent usability trials failed: {exc}\n")
    relative = sorted(path.relative_to(source_root).as_posix() for path in receipt_paths)
    index = {"package_hash": runtime_contract_hash(plugin_root), "observed_skill_root": str(plugin_root), "receipts": relative}
    (output_dir / "receipt-index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "phase": "installed-product-trials", "receipts": relative, "metrics": metrics}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
