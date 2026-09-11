"""Optional end-to-end stdio handshake and tool exchange against a real SDK client."""
import importlib.util
from datetime import timedelta
import os
import json
from pathlib import Path
import sys
import tempfile
import unittest


@unittest.skipUnless(importlib.util.find_spec("mcp") and os.environ.get("RUN_MCP_E2E"),
                     "Set RUN_MCP_E2E=1 to run the subprocess MCP test")
class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_stdio_transport(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as output:
            parameters = StdioServerParameters(command=sys.executable,
                args=["-m", "experiment", "serve", "--config", str(root / "configs/demo.json"), "--output", output],
                cwd=str(root))
            async with stdio_client(parameters) as streams:
                async with ClientSession(*streams, read_timeout_seconds=timedelta(seconds=15)) as client:
                    await client.initialize()
                    names = {tool.name for tool in (await client.list_tools()).tools}
                    self.assertIn("submit_artifact", names)
                    task = await client.call_tool("next_task", {})
                    self.assertFalse(task.isError)
                    serialized = " ".join(block.text for block in task.content if block.type == "text")
                    self.assertNotIn("feedback_style", serialized)
                    self.assertIn("brief", serialized)
                    response = await client.call_tool("submit_artifact", {"files": {"essay.md":
                        "A restrained explanation of feedback. " + "An example helps explain the limitation. " * 25}})
                    self.assertFalse(response.isError)
                    text = " ".join(block.text for block in response.content if block.type == "text")
                    self.assertIn('"approved": true', text)
                    self.assertNotIn("assessment", text)
                    await client.call_tool("stop_run", {})
            results = json.loads(next(Path(output).glob("run-*/results.json")).read_text())
            self.assertEqual(len(results), 8)
            self.assertEqual(results[0]["status"], "approved")


if __name__ == "__main__":
    unittest.main()
