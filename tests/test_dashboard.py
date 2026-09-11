"""Regression checks for the dashboard's public projection and live journal reads."""
import json
from pathlib import Path
import tempfile
import unittest

from experiment.dashboard import _events


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name) / "run-example"
        self.run.mkdir()

    def journal(self, rows, tail=""):
        (self.run / "events.private.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows) + tail)

    def test_private_judge_fields_are_removed_and_partial_lines_are_tolerated(self):
        self.journal([
            {"kind": "model_request", "request": "SECRET"},
            {"kind": "review", "episode": 0, "assessment": "SECRET", "user_review":
             {"approved": False, "feedback": "Please shorten it.", "private": "SECRET"}},
            {"kind": "task_end", "episode": 0, "status": "approved", "last_assessment": "SECRET",
             "initial_preference_score": "SECRET"},
            {"kind": "run_end", "status": "done"},
        ], '{"kind": "submission"')
        events = _events(self.run)
        self.assertEqual(len(events), 3)
        self.assertNotIn("SECRET", json.dumps(events))
        self.assertEqual(events[0]["user_review"]["feedback"], "Please shorten it.")

    def test_file_previews_are_bounded_and_external_files_are_not_read(self):
        directory = self.run / "episodes/0/v1"
        (directory / "files").mkdir(parents=True)
        (directory / "files/essay.md").write_text("x" * 50000)
        secret = Path(self.temp.name) / "secret.txt"
        secret.write_text("SECRET_OUTSIDE_RUN")
        (directory / "files/link.txt").symlink_to(secret)
        (directory / "artifact.json").write_text(json.dumps({"files": ["essay.md", "link.txt", str(secret)]}))
        self.journal([{"kind": "submission", "artifact": "episodes/0/v1", "version": 1}])
        event = _events(self.run)[0]
        self.assertEqual(len(event["artifact_files"]), 1)
        self.assertEqual(len(event["artifact_files"][0]["text"]), 48000)
        self.assertTrue(event["artifact_files"][0]["truncated"])
        self.assertNotIn("SECRET_OUTSIDE_RUN", json.dumps(event))

    def test_missing_artifact_does_not_hide_submission(self):
        self.journal([{"kind": "submission", "artifact": "episodes/not-yet-written", "version": 1}])
        self.assertEqual(_events(self.run)[0]["artifact_files"], [])
