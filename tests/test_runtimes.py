import io
import json
import os
from unittest.mock import patch
import unittest

from experiment.contracts import Request
from experiment.runtimes import OpenRouter, decode


class RuntimeTests(unittest.TestCase):
    @patch.dict(os.environ, {"TEST_PROVIDER_KEY": "test-only"})
    def test_openrouter_payload_and_usage(self):
        captured = []

        def endpoint(request, timeout):
            captured.append(json.loads(request.data))
            return io.BytesIO(json.dumps({"choices": [{"message": {"content": '{"approved":true}'},
                                                       "finish_reason": "stop"}],
                                         "usage": {"total_tokens": 123}}).encode())

        with patch("urllib.request.urlopen", endpoint):
            runtime = OpenRouter({"model": "test/model", "api_key_env": "TEST_PROVIDER_KEY", "vision": True})
            response = runtime.invoke(Request("review", "Review", {"artifact": "text"}, ["data:image/png;base64,AA=="]))
        self.assertTrue(response.data["approved"])
        self.assertEqual(response.usage["total_tokens"], 123)
        self.assertEqual(captured[0]["response_format"], {"type": "json_object"})
        self.assertEqual(captured[0]["messages"][1]["content"][1]["type"], "image_url")

    def test_malformed_outputs_are_not_silently_repaired(self):
        with self.assertRaises(ValueError):
            decode("not json")
        self.assertEqual(decode('```json\n{"x":1}\n```'), {"x": 1})


if __name__ == "__main__":
    unittest.main()
