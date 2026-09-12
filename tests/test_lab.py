import copy
import json
from pathlib import Path
import tempfile
import unittest

from experiment.config import load, resolve
from experiment.lab import Session
from experiment.plugins import create
from experiment.storage import BudgetExceeded
from experiment.tasks import validate_files

ROOT = Path(__file__).resolve().parents[1]


class LabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = load(ROOT / "configs/demo.json")

    def session(self, config=None):
        result = Session(config or self.config, Path(self.temp.name))
        self.addCleanup(result.close)
        return result

    def test_memory_transfers_to_test_tasks_when_demo_policy_updates(self):
        session = self.session()
        session.run()
        rows = session.results
        self.assertTrue(all(row["status"] == "approved" for row in rows))
        self.assertEqual(rows[4]["submissions"], 2)  # user-b's first correction
        self.assertTrue(rows[6]["first_pass"])
        events = [json.loads(line) for line in (session.journal.directory / "events.private.jsonl").read_text().splitlines()]
        updates = [event for event in events if event["kind"] == "memory_update"]
        self.assertTrue(updates)
        self.assertTrue(any(event["episode"] in {2, 3, 6, 7} for event in updates))

    def test_private_persona_and_assessment_never_enter_worker_or_memory(self):
        config = copy.deepcopy(self.config)
        config["users"][0]["private_marker"] = "SECRET_PROFILE_MARKER"
        session = self.session(config)
        session.run()
        events = [json.loads(line) for line in (session.journal.directory / "events.private.jsonl").read_text().splitlines()]
        for event in events:
            if event["kind"] == "model_request" and event["request"]["purpose"] in {"worker", "learn"}:
                serialized = json.dumps(event)
                self.assertNotIn("SECRET_PROFILE_MARKER", serialized)
                self.assertNotIn('"assessment"', serialized)
            if event["kind"] == "model_request" and event["request"]["purpose"] == "assess":
                self.assertNotIn("history", event["request"]["payload"])

    def test_user_profiles_are_independent(self):
        session = self.session()
        session.run()
        self.assertNotIn("playful", json.dumps(session.memories[0].context()).lower())
        self.assertIn("playful", json.dumps(session.memories[1].context()).lower())

    def test_no_memory_baseline_does_not_transfer(self):
        self.config["profiling"]["type"] = "none"
        session = self.session()
        session.run()
        self.assertEqual(session.results[6]["submissions"], 2)
        self.assertFalse(session.results[6]["first_pass"])

    def test_questions_disqualify_zero_feedback_first_pass(self):
        session = self.session()
        session.next_task()
        session.ask_user("What tone should I use?")
        artifact = session.worker.act(session.get_task())
        session.submit_artifact(artifact["files"])
        self.assertTrue(session.results[0]["first_submission_approved"])
        self.assertFalse(session.results[0]["first_pass"])

    def test_objective_failure_prevents_approval_and_exhausts_submissions(self):
        self.config["budgets"]["max_submissions"] = 1
        session = self.session()
        session.next_task()
        result = session.submit_artifact({"essay.md": "restrained"})
        self.assertFalse(result["approved"])
        self.assertEqual(result["status"], "submission_limit")
        self.assertIsNone(session.results[0]["last_assessment"])
        with self.assertRaises(ValueError):
            session.submit_artifact({"essay.md": "anything"})

    def test_budget_failures_keep_all_planned_episodes(self):
        self.config["budgets"]["max_calls"] = 1
        session = self.session()
        session.run()
        self.assertEqual(len(session.results), 8)
        self.assertTrue(all(row["status"] == "budget_exhausted" for row in session.results))
        self.assertEqual(session.journal.calls, 1)

    def test_immutable_versions_and_memory_snapshots(self):
        self.config["users"] = [self.config["users"][1]]
        session = self.session()
        first = session.next_task()
        submission = session.worker.act(first)
        session.submit_artifact(submission["files"])
        path = session.journal.directory / "episodes/0000/v001/files/essay.md"
        original = path.read_text()
        session.submit_artifact(session.worker.act(session.get_task())["files"])
        self.assertEqual(path.read_text(), original)
        self.assertEqual(first["memory"], {})
        self.assertTrue((session.journal.directory / "episodes/0000/v002/files/essay.md").exists())

    def test_path_traversal_and_collisions_rejected(self):
        for files in ({"../secret": "x"}, {"/tmp/x": "x"}, {".env": "x"},
                      {"a/../b": "x"}, {"a\\b": "x"}, {"a": "x", "a/b": "y"}):
            with self.assertRaises(ValueError):
                validate_files(files)

    def test_plugin_factory_loads_without_registry_edits(self):
        task = create("task", {"type": "experiment.tasks:FileTask", "id": "new",
                               "brief": "Explain something", "entrypoint": "output.txt",
                               "checks": {"contains": ["example"]}})
        self.assertFalse(task.check({"output.txt": "a claim"})["passed"])
        self.assertTrue(task.check({"output.txt": "an example"})["passed"])

    def test_heldout_must_follow_training_and_ids_are_unique(self):
        config = copy.deepcopy(self.config)
        config["tasks"].reverse()
        with self.assertRaises(ValueError):
            resolve(config)
        config = copy.deepcopy(self.config)
        config["users"][1]["id"] = config["users"][0]["id"]
        with self.assertRaises(ValueError):
            resolve(config)

    def test_scheduled_preference_change_is_private(self):
        self.config["users"][0]["changes"] = [{"from_task": 0, "preferences": {"default": "playful"}}]
        session = self.session()
        public = session.next_task()
        self.assertNotIn("playful", json.dumps(public))
        feedback = session.submit_artifact(session.worker.act(public)["files"])
        self.assertIn("playful", feedback["feedback"])

    def test_mcp_actions_match_api_results(self):
        api = self.session()
        api.run()
        config = copy.deepcopy(self.config)
        config["mode"] = "mcp"
        harness = self.session(config)
        from experiment.actors import LLMWorker
        from experiment.runtimes import DemoRuntime
        worker = LLMWorker({}, DemoRuntime({}))
        while not harness.next_task().get("done"):
            while harness.current["status"] == "active":
                harness.submit_artifact(worker.act(harness.get_task())["files"])
        fields = ("status", "submissions", "questions", "first_pass", "last_assessment")
        self.assertEqual([[r[k] for k in fields] for r in api.results],
                         [[r[k] for k in fields] for r in harness.results])


if __name__ == "__main__":
    unittest.main()
