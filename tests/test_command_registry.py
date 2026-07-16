import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from shutil import copytree

from scripts.lib.command_catalog import CommandSpec, ScriptError, _COMMANDS, build_command_registry, load_command_catalog, resolve_command
from scripts.lib.command_support import Context, normalize_rel, project_path_for, project_root_for
from scripts.lib.commands import load_handlers


ROOT = Path(__file__).resolve().parents[1]


class CommandRegistryTests(unittest.TestCase):
    def test_project_truss_launcher_is_registered_as_mutation_free(self):
        self.assertEqual("command_project_truss", _COMMANDS["scripts/project-truss.sh"])
        self.assertEqual("none", load_command_catalog(ROOT)["scripts/project-truss.sh"].mutation)

    def test_workspace_policy_launcher_is_registered_as_mutation_free(self):
        self.assertEqual("command_workspace_isolation", _COMMANDS["scripts/workspace-isolation.sh"])
        self.assertEqual("none", load_command_catalog(ROOT)["scripts/workspace-isolation.sh"].mutation)

    def test_registry_drift_reports_extra_launcher(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copytree(ROOT / "scripts", root / "scripts")
            copytree(ROOT / "skills", root / "skills")
            extra = root / "scripts" / "extra-launcher.sh"
            extra.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            with self.assertRaisesRegex(ScriptError, "extra-launcher.sh"):
                build_command_registry(root)

    def test_every_shipped_launcher_has_one_entry(self):
        registry = build_command_registry(ROOT)
        catalog = load_command_catalog(ROOT)
        launchers = {
            path.relative_to(ROOT).as_posix()
            for base in (ROOT / "scripts", ROOT / "skills")
            for path in base.rglob("*.sh")
            if "/lib/" not in path.as_posix()
        }
        self.assertEqual(launchers, set(registry))
        for path, spec in catalog.items():
            with self.subTest(path=path):
                process = subprocess.run(
                    ["bash", str(ROOT / path), "-DispatchProbe"],
                    cwd="/tmp",
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(0, process.returncode, process.stdout + process.stderr)
                self.assertEqual(
                    {"ok": True, "path": path, "handler": spec.handler, "kind": spec.kind, "mutation": spec.mutation},
                    json.loads(process.stdout),
                )

    def test_dispatcher_is_not_classified_as_a_launcher(self):
        self.assertNotIn("scripts/lib/project_truss_cli.py", build_command_registry(ROOT))

    def test_unknown_path_fails_closed(self):
        with self.assertRaisesRegex(Exception, "unregistered script path"):
            resolve_command("scripts/test-unknown.sh", ROOT)

    def test_registry_has_no_retired_or_unimplemented_handlers(self):
        self.assertFalse(any(handler.endswith("_unimplemented") for handler in _COMMANDS.values()))
        retired = ("workflow", "gate", "evidence")
        self.assertFalse(any(any(word in handler for word in retired) for handler in _COMMANDS.values()))

    def test_every_registered_handler_is_callable(self):
        sys.path.insert(0, str(ROOT / "scripts" / "lib"))
        try:
            import project_truss_cli as cli
        finally:
            sys.path.pop(0)
        missing = sorted({handler for handler in _COMMANDS.values() if not callable(cli.resolve_handler(handler))})
        self.assertEqual([], missing)
        handlers = load_handlers()
        expected_modules = {
            "command_project_truss": "commands.project",
            "command_prepare_release": "commands.distribution",
            "command_validate_agent_usability_receipt": "commands.distribution",
        }
        for name, module in expected_modules.items():
            self.assertTrue(handlers[name].__module__.endswith(module))

    def test_typed_catalog_has_known_kinds_and_mutation_classes(self):
        catalog = load_command_catalog(ROOT)
        self.assertTrue(catalog)
        self.assertTrue(all(isinstance(spec, CommandSpec) for spec in catalog.values()))
        self.assertTrue(all(spec.kind in {"validator", "distribution", "project"} for spec in catalog.values()))
        self.assertTrue(all(spec.mutation in {"none", "project", "git", "deployment", "external"} for spec in catalog.values()))
        self.assertEqual(set(catalog), {spec.path for spec in catalog.values()})

    def test_public_validator_runs_from_arbitrary_cwd(self):
        script = ROOT / "scripts" / "validate-skill-metadata-contract.sh"
        process = subprocess.run(["bash", str(script), "-RepoRoot", str(ROOT)], cwd="/tmp", text=True, capture_output=True)
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)
        self.assertTrue(json.loads(process.stdout)["ok"])

    def test_project_paths_are_scoped_to_the_invocation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            ctx = Context(Path(__file__), root, "tests/x", "x", [], plugin_root=ROOT, invocation_cwd=root)
            self.assertEqual(root, project_root_for(ctx, {"RepoRoot": "."}))
            self.assertEqual(root, project_root_for(ctx, {"RepoRoot": str(root)}))
            self.assertEqual(".project-truss/receipt.json", normalize_rel(root / ".project-truss/receipt.json", root))
            self.assertEqual("../outside", normalize_rel(root.parent / "outside", root))
            with self.assertRaisesRegex(Exception, "outside project root"):
                project_path_for(root, "../outside", "Path")


if __name__ == "__main__":
    unittest.main()
