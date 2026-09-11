import unittest

from experiment.runner import evaluate, generate, validate


class ProtocolTests(unittest.TestCase):
    def event(self, choice="detailed", user="a"):
        return {"user_id": user, "context": "research", "choice": choice}

    def test_current_label_cannot_affect_current_prediction(self):
        left = evaluate([self.event(), self.event("concise")])
        right = evaluate([self.event(), self.event("detailed")])
        self.assertEqual([r["probability_detailed"] for r in left],
                         [r["probability_detailed"] for r in right])
        self.assertNotEqual(left[-1]["state_after"], right[-1]["state_after"])

    def test_user_state_is_isolated_and_snapshots_are_independent(self):
        rows = evaluate([self.event(), self.event(user="b"), self.event()])
        self.assertTrue(all(row["probability_detailed"] == 0.5 for row in rows[3:6]))
        self.assertEqual(rows[2]["state_before"]["global"], [0.0, 0.0])
        self.assertEqual(rows[2]["state_after"]["global"], [0.0, 1.0])

    def test_phase_labels_do_not_reach_learning(self):
        events = generate(7)
        changed = [{**event, "phase": "hidden"} for event in events]
        self.assertEqual([r["probability_detailed"] for r in evaluate(events)],
                         [r["probability_detailed"] for r in evaluate(changed)])

    def test_seed_reproducibility(self):
        self.assertEqual(evaluate(generate(7)), evaluate(generate(7)))
        self.assertNotEqual(generate(7), generate(8))

    def test_bad_data_rejected(self):
        for events in ([], [None], [self.event("unknown")], [{"user_id": "a"}]):
            with self.assertRaises(ValueError):
                validate(events)


if __name__ == "__main__":
    unittest.main()
