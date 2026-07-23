"""Project Truss distribution, version, release, and trial handlers."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

try:
    from ..agent_usability import validate_trial_receipt, validate_trial_set
    from ..command_support import Context, ScriptError, arg_value, emit, has_switch, normalize_rel, project_path_for, project_root_for, read_text, run, write_text
    from ..package_provenance import runtime_contract_hash, runtime_manifest
except ImportError:
    from agent_usability import validate_trial_receipt, validate_trial_set
    from command_support import Context, ScriptError, arg_value, emit, has_switch, normalize_rel, project_path_for, project_root_for, read_text, run, write_text
    from package_provenance import runtime_contract_hash, runtime_manifest


PLUGIN_NAME = "project-truss"


def validate_dependency_pins(path: Path) -> list[str]:
    findings = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        value = line.strip()
        if value and not value.startswith("#") and ("==" not in value or any(operator in value for operator in (">=", "<=", "~=", "!="))):
            findings.append(f"line {number} is not exactly pinned: {value}")
    return findings


def base_release_tag(version: str) -> str:
    base = version.split("+", 1)[0]
    if re.fullmatch(r"\d+\.\d+\.\d+", base) is None:
        raise ValueError("release version must have a numeric major.minor.patch base")
    return f"v{base}"


def plugin_manifest(root: Path) -> dict[str, Any] | None:
    path = root / ".codex-plugin" / "plugin.json"
    return json.loads(read_text(path)) if path.is_file() else None


def _surface(name: str, root: Path | None, source_hash: str) -> dict[str, Any]:
    exists = root is not None and root.is_dir()
    manifest = plugin_manifest(root) if exists and root is not None else None
    contract = ""
    error = ""
    if exists and root is not None:
        try:
            contract = runtime_contract_hash(root)
        except (OSError, ValueError) as exc:
            error = str(exc)
    return {
        "name": name,
        "path": str(root.resolve()) if root is not None else "",
        "exists": bool(exists),
        "manifest_name": manifest.get("name", "") if manifest else "",
        "manifest_version": manifest.get("version", "") if manifest else "",
        "contract_hash": contract,
        "matches_source": bool(exists and contract == source_hash),
        "error": error,
    }


def command_get_agent_plugin_version(ctx: Context, args: dict[str, Any]) -> int:
    from revision_status import evaluate_revision_status

    root = project_root_for(ctx, args)
    live_root = Path(str(arg_value(args, "LivePluginRoot", default=str(Path.home() / ".codex" / "plugins" / PLUGIN_NAME)))).expanduser()
    manifest = plugin_manifest(root)
    if manifest is None:
        raise ScriptError("source plugin manifest is missing")
    source_hash = runtime_contract_hash(root)
    head = run(["git", "rev-parse", "HEAD"], root)
    status = run(["git", "status", "--short"], root)
    source = {
        "name": "source",
        "path": str(root),
        "manifest_name": manifest.get("name", ""),
        "manifest_version": manifest.get("version", ""),
        "git_commit": head.stdout.strip() if head.returncode == 0 else "",
        "dirty": bool(status.stdout.strip()),
        "contract_hash": source_hash,
    }
    live = _surface("live", live_root, source_hash)
    observed_root = None
    observed_plugin = arg_value(args, "ObservedPluginRoot")
    observed_skill = arg_value(args, "ObservedSkillRoot")
    if observed_plugin:
        observed_root = Path(str(observed_plugin)).expanduser().resolve()
    elif observed_skill:
        cursor = Path(str(observed_skill)).expanduser().resolve()
        cursor = cursor.parent if cursor.is_file() else cursor
        while cursor != cursor.parent:
            if (cursor / ".codex-plugin" / "plugin.json").is_file():
                observed_root = cursor
                break
            cursor = cursor.parent
        if observed_root is None:
            raise ScriptError(f"could not resolve plugin root from observed skill root: {observed_skill}")
    observed = _surface("observed", observed_root, source_hash) if observed_root else None
    if has_switch(args, "RevisionStatus"):
        supplied = arg_value(args, "RevisionEvidenceJson")
        path_value = arg_value(args, "RevisionEvidencePath")
        if supplied and path_value:
            raise ScriptError("provide RevisionEvidenceJson or RevisionEvidencePath, not both")
        evidence = json.loads(str(supplied)) if supplied else json.loads(read_text(project_path_for(root, str(path_value), "RevisionEvidencePath"))) if path_value else {
            "source_dirty": source["dirty"],
            "validation_current": False,
            "source_committed": not source["dirty"] and bool(source["git_commit"]),
            "deployment_current": live["matches_source"],
            "installation_current": False,
            "cleanup_current": False,
            "fresh_session_acknowledged": has_switch(args, "FreshSessionAcknowledged"),
        }
        return emit({"ok": True, "phase": "plugin-revision-status", **evaluate_revision_status(evidence)})
    failures = []
    if not live["matches_source"]:
        failures.append("live plugin differs from source")
    if observed and not observed["matches_source"]:
        failures.append("observed plugin differs from source")
    if live["manifest_version"] != manifest.get("version"):
        failures.append("live plugin manifest version differs from source")
    ok = not failures if has_switch(args, "RequireCurrent") else True
    reason = "source, live, and observed plugin surfaces are current" if not failures else "; ".join(failures)
    if has_switch(args, "Banner"):
        print("\n".join([
            "Project Truss plugin",
            f"manifest_version: {source['manifest_version']}",
            f"git_commit: {source['git_commit']}",
            f"source_dirty: {source['dirty']}",
            f"contract_hash: {source['contract_hash']}",
            f"source/live: {'current' if live['matches_source'] else 'stale'}",
            f"observed: {'not supplied' if observed is None else ('current' if observed['matches_source'] else 'stale')}",
            f"reason: {reason}",
        ]))
        return 0 if ok else 1
    return emit({"ok": ok, "phase": "agent-plugin-version", "reason": reason, "source": source, "live": live, "observed": observed}, 0 if ok else 1)


def _deployment_root(value: str, source: Path, label: str) -> Path:
    target = Path(value).expanduser().resolve()
    if target in {Path(target.anchor), Path.home().resolve(), source} or target in source.parents or source in target.parents:
        raise ScriptError(f"{label} deployment path overlaps a protected source or home boundary: {target}")
    return target


def _copy_runtime_package(source: Path, target: Path) -> None:
    staged = target.with_name(f".{target.name}.staged-{os.getpid()}")
    backup = target.with_name(f".{target.name}.backup-{os.getpid()}")
    if staged.exists():
        shutil.rmtree(staged)
    if backup.exists():
        shutil.rmtree(backup)
    staged.mkdir(parents=True)
    promoted = False
    preserved = False
    try:
        for entry in runtime_manifest(source):
            destination = staged / entry.path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / entry.path, destination)
        if target.exists():
            if not target.is_dir():
                raise ScriptError(f"live plugin target is not a directory: {target}")
            target.replace(backup)
            preserved = True
        try:
            staged.replace(target)
            promoted = True
        except Exception as promotion_error:
            if preserved:
                try:
                    backup.replace(target)
                except Exception as rollback_error:
                    raise ScriptError(f"live promotion failed and rollback also failed: {rollback_error}") from promotion_error
            raise
    finally:
        if staged.exists():
            shutil.rmtree(staged)
        if promoted and backup.exists():
            shutil.rmtree(backup)


def command_sync_live(ctx: Context, args: dict[str, Any]) -> int:
    root = ctx.repo_root.resolve()
    home = Path.home()
    live_root = _deployment_root(str(arg_value(args, "LivePluginRoot", default=os.environ.get("PROJECT_TRUSS_LIVE_PLUGIN_ROOT", str(home / ".codex" / "plugins" / PLUGIN_NAME)))), root, "live plugin")
    marketplace = Path(str(arg_value(args, "MarketplacePath", default=str(home / ".agents" / "plugins" / "marketplace.json")))).expanduser()
    if has_switch(args, "Validate", "validate"):
        result = subprocess.run(["bash", str(root / "scripts" / "validate.sh")], cwd=root, text=True)
        if result.returncode != 0:
            raise ScriptError("validation failed before sync")
    _copy_runtime_package(root, live_root)
    source_manifest = [entry.to_dict() for entry in runtime_manifest(root)]
    live_manifest = [entry.to_dict() for entry in runtime_manifest(live_root)]
    if source_manifest != live_manifest:
        raise ScriptError("live install differs from the runtime package manifest")
    marketplace.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(read_text(marketplace)) if marketplace.is_file() else {"name": "personal", "interface": {"displayName": "Personal"}, "plugins": []}
    data["plugins"] = [
        plugin for plugin in data.get("plugins", [])
        if plugin.get("name") != PLUGIN_NAME
    ]
    data["plugins"].append({"name": PLUGIN_NAME, "source": {"source": "local", "path": f"./.codex/plugins/{PLUGIN_NAME}"}, "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}, "category": "Productivity"})
    write_text(marketplace, json.dumps(data, indent=2) + "\n")
    return emit({
        "ok": True,
        "source": str(root),
        "live_plugin_root": str(live_root),
        "marketplace": {"marketplace_path": str(marketplace), "plugin_name": PLUGIN_NAME, "source_path": f"./.codex/plugins/{PLUGIN_NAME}"},
        "deployed_plugin_skills": sorted(path.name for path in (root / "skills").iterdir() if path.is_dir()),
        "runtime_package": {"files": len(source_manifest), "bytes": sum(item["length"] for item in source_manifest)},
    })


def command_install(ctx: Context, args: dict[str, Any]) -> int:
    manifest = plugin_manifest(ctx.repo_root)
    if not manifest or manifest.get("name") != PLUGIN_NAME:
        raise ScriptError(f"plugin manifest name must be {PLUGIN_NAME}")
    sync_args = dict(args)
    if not has_switch(args, "SkipValidation"):
        sync_args["Validate"] = True
    return command_sync_live(ctx, sync_args)


def command_prepare_release(ctx: Context, args: dict[str, Any]) -> int:
    root = project_root_for(ctx, args)
    manifest = plugin_manifest(root) or {}
    version = str(arg_value(args, "Version", default=manifest.get("version", ""))).lstrip("v")
    base = version.split("+", 1)[0]
    changelog = read_text(root / "CHANGELOG.md")
    head = run(["git", "rev-parse", "HEAD"], root)
    status = run(["git", "status", "--short"], root)
    check_only = has_switch(args, "CheckOnly")
    checks = [
        {"name": "manifest name", "ok": manifest.get("name") == PLUGIN_NAME},
        {"name": "manifest version", "ok": manifest.get("version") == version and bool(version)},
        {"name": "release tag", "ok": bool(base_release_tag(version))},
        {"name": "changelog entry", "ok": bool(re.search(rf"(?m)^##\s+v?{re.escape(base)}(?:\s|$)", changelog))},
        {"name": "runtime package", "ok": bool(runtime_manifest(root))},
        {"name": "validation dependencies pinned", "ok": not validate_dependency_pins(root / "requirements-validation.txt")},
        {"name": "git head", "ok": head.returncode == 0},
    ]
    if not check_only:
        checks.append({"name": "worktree clean", "ok": not status.stdout.strip()})
    ok = all(check["ok"] for check in checks)
    result = {"ok": ok, "phase": "prepare-release", "check_only": check_only, "manifest_name": manifest.get("name", ""), "manifest_version": manifest.get("version", ""), "release_tag": base_release_tag(version), "package_hash": runtime_contract_hash(root), "commit": head.stdout.strip(), "dirty": bool(status.stdout.strip()), "checks": checks}
    output = arg_value(args, "OutputPath")
    if output:
        write_text(project_path_for(root, str(output), "OutputPath"), json.dumps(result, indent=2) + "\n")
    return emit(result, 0 if ok else 1)


def command_validate_agent_usability_receipt(ctx: Context, args: dict[str, Any]) -> int:
    root = project_root_for(ctx, args)
    receipt_path = arg_value(args, "ReceiptPath")
    receipt_dir = arg_value(args, "ReceiptDir")
    if bool(receipt_path) == bool(receipt_dir):
        raise ScriptError("provide exactly one of ReceiptPath or ReceiptDir")
    source_root = ctx.plugin_root or ctx.repo_root
    if receipt_path:
        path = project_path_for(root, str(receipt_path), "ReceiptPath")
        receipt = json.loads(read_text(path))
        observed_root = Path(str(receipt.get("observed_skill_root", ""))).resolve()
        if runtime_contract_hash(observed_root) != runtime_contract_hash(source_root):
            raise ScriptError("installed Project Truss package does not match source")
        validate_trial_receipt(receipt, observed_root)
        return emit({"ok": True, "phase": "agent-usability-receipt", "receipt": normalize_rel(path, root)})
    directory = project_path_for(root, str(receipt_dir), "ReceiptDir")
    receipt_paths = sorted(directory.glob("**/receipt.json"))
    receipts = [json.loads(read_text(path)) for path in receipt_paths]
    index_path = directory / "receipt-index.json"
    if not index_path.is_file():
        raise ScriptError("agent trial receipt index is missing")
    index = json.loads(read_text(index_path))
    observed_root = Path(str(index.get("observed_skill_root", ""))).resolve()
    if runtime_contract_hash(observed_root) != runtime_contract_hash(source_root):
        raise ScriptError("installed Project Truss package does not match source")
    metrics = validate_trial_set(receipts, observed_root)
    if index.get("package_hash") != runtime_contract_hash(observed_root):
        raise ScriptError("agent trial receipt index package hash is stale")
    expected = [normalize_rel(path, source_root) for path in receipt_paths]
    if index.get("receipts") != expected:
        raise ScriptError("agent trial receipt index must contain sorted plugin-relative paths")
    return emit({"ok": True, "phase": "agent-usability-receipt", "receipt_count": len(receipts), "metrics": metrics})


def command_run_agent_usability_trials(ctx: Context, args: dict[str, Any]) -> int:
    raise ScriptError("run-agent-usability-trials.sh must be invoked directly with --execute and an explicit output directory")


HANDLERS = {
    "command_get_agent_plugin_version": command_get_agent_plugin_version,
    "command_install": command_install,
    "command_prepare_release": command_prepare_release,
    "command_run_agent_usability_trials": command_run_agent_usability_trials,
    "command_sync_live": command_sync_live,
    "command_validate_agent_usability_receipt": command_validate_agent_usability_receipt,
}
