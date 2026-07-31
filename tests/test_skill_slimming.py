import unittest
from pathlib import Path

import yaml
from scripts.lib.skill_slimming import validate_skill_slimming
ROOT = Path(__file__).resolve().parents[1]
SKILLS = {"setup", "start", "shape", "resolve", "close", "advanced-user-input"}


class SkillSlimmingTests(unittest.TestCase):
    def test_exact_six_skill_surface_is_compact_and_matt_first(self):
        skill_files = sorted((ROOT / "skills").glob("*/SKILL.md"))
        self.assertEqual(SKILLS, {path.parent.name for path in skill_files})
        self.assertLessEqual(
            sum(len(path.read_text(encoding="utf-8").splitlines()) for path in skill_files),
            300,
        )
        self.assertEqual(
            SKILLS,
            {
                path.parents[1].name
                for path in (ROOT / "skills").glob("*/agents/openai.yaml")
            },
        )

        active = "\n".join(path.read_text(encoding="utf-8") for path in skill_files)
        self.assertNotIn("Super" + "powers", active)
        self.assertNotIn("$project-truss:deliver", active)
        self.assertIn("Matt", active)

        findings, metrics = validate_skill_slimming(ROOT)
        self.assertEqual([], findings)
        self.assertEqual(6, metrics["skill_count"])

    def test_metadata_reconstructs_the_matt_first_workflow(self):
        workflow = {
            "setup": ("once per repository", "available Matt disciplines", "return to Start"),
            "start": ("Matt-first", "grilling", "verified closeout"),
            "shape": ("confirmed Matt", "native GitHub", "return to Start"),
            "resolve": ("Ready", "Matt TDD", "pull request", "return to Start"),
            "close": ("Matt review", "merge", "local retirement", "return to Start"),
            "advanced-user-input": ("native Truss", "bounded question", "record", "return to Start"),
        }
        reconstructed = []
        for name, phrases in workflow.items():
            skill = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            interface = yaml.safe_load((ROOT / "skills" / name / "agents/openai.yaml").read_text(encoding="utf-8"))["interface"]
            surface = "\n".join((skill, *(str(interface[field]) for field in ("short_description", "default_prompt")))).casefold()
            self.assertTrue(all(phrase.casefold() in surface for phrase in phrases), name)
            self.assertIn("docs/project-truss/contract.yml", skill, name)
            reconstructed.append(name)
        self.assertEqual(list(workflow), reconstructed)
        for premature_stop in ("issue publication", "PR creation", "review", "merge", "pre-cleanup"):
            self.assertIn(premature_stop, (ROOT / "skills/start/SKILL.md").read_text(encoding="utf-8"))
    def test_projects_and_labels_are_projection_not_lifecycle_state(self):
        shape = (ROOT / "skills/shape/SKILL.md").read_text(encoding="utf-8")
        for command in ("gh project view", "gh project item-list", "gh project item-add"):
            self.assertIn(command, shape)
        self.assertIn("preserve", shape.casefold())
        self.assertIn("agent-shaped", shape)
        self.assertIn("advisory only", shape)
        self.assertIn("never run `gh auth refresh", shape.casefold())

        resolve = (ROOT / "skills/resolve/SKILL.md").read_text(encoding="utf-8")
        close = (ROOT / "skills/close/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("pull request", resolve)
        self.assertIn("Project projection", resolve)
        self.assertIn("Project projection", close)


if __name__ == "__main__":
    unittest.main()
