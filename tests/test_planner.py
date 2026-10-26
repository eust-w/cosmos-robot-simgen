import unittest

from cosmos_robot_simgen.planner import build_cosmos_prompt, compile_prompt_to_task, slugify


class PlannerTests(unittest.TestCase):
    def test_slugify_keeps_safe_name(self):
        self.assertEqual(slugify("Warehouse Pick Place!"), "warehouse_pick_place")

    def test_compile_prompt_generates_valid_pick_place_task(self):
        task = compile_prompt_to_task("A robot picks a blue cube and places it into a yellow bin.", "demo")

        task.validate()
        self.assertEqual(task.name, "demo")
        self.assertEqual(task.robot.name, "motrix_arm")
        self.assertGreaterEqual(len(task.objects), 4)
        self.assertGreaterEqual(len(task.waypoints), 6)
        self.assertIn("Cosmos3-Nano", task.metadata["cosmos_model"])

    def test_cosmos_prompt_mentions_task_elements(self):
        task = compile_prompt_to_task("Pick a bottle into a red tray.", "bottle_task")
        prompt = build_cosmos_prompt(task)

        self.assertIn("robot arm", prompt)
        self.assertIn("blue bottle", prompt)
        self.assertIn("Original user task", prompt)


if __name__ == "__main__":
    unittest.main()
