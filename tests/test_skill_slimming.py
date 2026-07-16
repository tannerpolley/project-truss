import unittest
from pathlib import Path

from scripts.lib.skill_slimming import validate_skill_slimming


ROOT = Path(__file__).resolve().parents[1]
SKILLS = {"start", "shape", "deliver", "close", "advanced-user-input"}
STALE = (
    "$superpowers-project:",
    "Manual Mode",
    "Auto Mode",
    "Looping Mode",
    "run ledger",
    "issue mirror",
)


class SkillSlimmingTests(unittest.TestCase):
    def test_exact_five_skill_surface_is_compact_and_current(self):
        skill_files = sorted((ROOT / "skills").glob("*/SKILL.md"))
        self.assertEqual(SKILLS, {path.parent.name for path in skill_files})
        self.assertLessEqual(sum(len(path.read_text(encoding="utf-8").splitlines()) for path in skill_files), 300)
        self.assertEqual(SKILLS, {path.parents[1].name for path in (ROOT / "skills").glob("*/agents/openai.yaml")})

        active = "\n".join(path.read_text(encoding="utf-8") for path in skill_files)
        active += (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        for phrase in STALE:
            self.assertNotIn(phrase, active)

        findings, metrics = validate_skill_slimming(ROOT)
        self.assertEqual([], findings)
        self.assertEqual(5, metrics["skill_count"])
        self.assertLessEqual(metrics["skill_lines"], 300)

    def test_each_lifecycle_owner_has_one_clear_responsibility(self):
        expected = {
            "start": ("direct", "governed", "one outcome"),
            "shape": ("milestone", "sub-issue", "dependency"),
            "deliver": ("Ready", "assignee", "hidden worktree", "Superpowers"),
            "close": ("pull request", "checks", "acceptance", "integration"),
        }
        for name, phrases in expected.items():
            text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            for phrase in phrases:
                self.assertIn(phrase, text, f"{name}: {phrase}")
            self.assertIn("docs/project-truss/contract.yml", text, name)


if __name__ == "__main__":
    unittest.main()
