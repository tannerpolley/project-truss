from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.lib.command_support import Context, ScriptError
from scripts.lib.commands.distribution import command_sync_live
from scripts.lib.package_provenance import (
    load_runtime_package,
    runtime_contract_hash,
    runtime_manifest,
    validate_runtime_reads,
    verify_runtime_provenance,
)


ROOT = Path(__file__).resolve().parents[1]
SKILLS = {"start", "shape", "deliver", "close", "advanced-user-input"}
PROMPT = "Use $project-truss:start only for explicit or hard-trigger governed work; ordinary coding stays direct."


class RuntimePackageTests(unittest.TestCase):
    def write_manifest(self, root: Path) -> None:
        plugin = root / ".codex-plugin"
        plugin.mkdir(exist_ok=True)
        (plugin / "runtime-package.yml").write_text(
            "version: 1\ninclude:\n  - .codex-plugin/**\n  - scripts/**\n  - skills/**\n  - docs/project-truss/**\n"
        )

    def test_source_manifest_is_the_compact_project_truss_surface(self):
        plugin = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual("project-truss", plugin["name"])
        self.assertEqual("1.0.0", plugin["version"])
        self.assertEqual("Project Truss", plugin["interface"]["displayName"])
        self.assertEqual([PROMPT], plugin["interface"]["defaultPrompt"])
        self.assertEqual(SKILLS, {path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md")})

        package = load_runtime_package(ROOT)
        paths = {entry.path for entry in runtime_manifest(ROOT)}
        required = {
            "docs/project-truss/contract.yml",
            "docs/project-truss/METHODS.md",
            "docs/project-truss/README.md",
            "scripts/lib/truss_policy.py",
            "scripts/lib/truss_github.py",
            "scripts/lib/project_truss_cli.py",
        }
        self.assertLessEqual(required, paths)
        self.assertFalse(any(path.startswith("docs/superpowers/") for path in paths))
        self.assertEqual([], validate_runtime_reads(ROOT, package))

    def test_hash_tracks_included_content_and_executable_mode_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "repo"
            shutil.copytree(ROOT, target)
            first = runtime_contract_hash(target)
            (target / "docs" / "completed-history.md").parent.mkdir(exist_ok=True)
            (target / "docs" / "completed-history.md").write_text("excluded\n")
            self.assertEqual(first, runtime_contract_hash(target))
            script = target / "scripts" / "project-truss.sh"
            script.write_text(script.read_text() + "\n# changed\n")
            changed = runtime_contract_hash(target)
            self.assertNotEqual(first, changed)
            script.chmod(0o775)
            self.assertEqual(changed, runtime_contract_hash(target))
            script.chmod(0o644)
            self.assertNotEqual(changed, runtime_contract_hash(target))

    def test_hash_is_location_independent_and_provenance_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "one"
            root.mkdir()
            self.write_manifest(root)
            (root / ".codex-plugin/plugin.json").write_text("{}")
            (root / "scripts").mkdir()
            (root / "scripts/run.sh").write_text("echo one\n")
            sibling = Path(tmp) / "two"
            shutil.copytree(root, sibling)
            self.assertEqual(runtime_contract_hash(root), runtime_contract_hash(sibling))

            project = root / "project"
            project.mkdir()
            ledger = {
                "manifest": [entry.to_dict() for entry in runtime_manifest(root)],
                "contract_hash": runtime_contract_hash(root),
                "project_root": str(project),
            }
            verify_runtime_provenance(ledger, root, project)
            ledger["contract_hash"] = "0" * 64
            with self.assertRaises(ValueError):
                verify_runtime_provenance(ledger, root, project)

    def test_missing_runtime_read_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "repo"
            shutil.copytree(ROOT, target)
            manifest = target / ".codex-plugin/runtime-package.yml"
            manifest.write_text(manifest.read_text().replace("  - docs/project-truss/contract.yml\n", ""))
            findings = validate_runtime_reads(target, load_runtime_package(target))
            self.assertTrue(any("contract.yml" in finding for finding in findings))

    def test_sync_replaces_the_live_source_without_touching_installed_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live = root / "live"
            predecessor = root / "predecessor"
            cache = root / "cache" / "installed.txt"
            marketplace = root / "marketplace.json"
            predecessor.mkdir()
            cache.parent.mkdir()
            cache.write_text("retain\n", encoding="utf-8")
            marketplace.write_text(json.dumps({"plugins": [{"name": "superpowers-project"}]}), encoding="utf-8")
            context = Context(ROOT / "scripts/sync-live.sh", ROOT, "scripts/sync-live.sh", "sync-live.sh", [], plugin_root=ROOT, invocation_cwd=ROOT)
            result = command_sync_live(context, {"LivePluginRoot": str(live), "PredecessorLiveRoot": str(predecessor), "MarketplacePath": str(marketplace)})
            self.assertEqual(0, result)
            self.assertEqual(runtime_contract_hash(ROOT), runtime_contract_hash(live))
            self.assertEqual(["project-truss"], [item["name"] for item in json.loads(marketplace.read_text())["plugins"]])
            self.assertFalse(predecessor.exists())
            self.assertEqual("retain\n", cache.read_text(encoding="utf-8"))

            with self.assertRaisesRegex(ScriptError, "deployment path"):
                command_sync_live(context, {"LivePluginRoot": str(ROOT), "PredecessorLiveRoot": str(predecessor), "MarketplacePath": str(marketplace)})

            rollback_live = root / "rollback-live"
            rollback_live.mkdir()
            marker = rollback_live / "installed.txt"
            marker.write_text("current\n", encoding="utf-8")
            original_replace = Path.replace

            def fail_promotion(path, target):
                if path.name.startswith(".rollback-live.staged-"):
                    raise OSError("simulated promotion failure")
                return original_replace(path, target)

            with patch.object(Path, "replace", fail_promotion), self.assertRaisesRegex(OSError, "promotion failure"):
                command_sync_live(context, {"LivePluginRoot": str(rollback_live), "PredecessorLiveRoot": str(predecessor), "MarketplacePath": str(marketplace)})
            self.assertEqual("current\n", marker.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
