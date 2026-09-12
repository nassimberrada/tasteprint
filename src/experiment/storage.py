"""Append-only event journal and write-once artifact versions."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import tempfile
import time

from .contracts import Request


class BudgetExceeded(RuntimeError):
    pass


class Journal:
    def __init__(self, root: Path, config: dict):
        root.mkdir(parents=True, exist_ok=True)
        self.directory = Path(tempfile.mkdtemp(prefix="run-", dir=root)).resolve()
        self.start = time.monotonic()
        self.calls = 0
        self.budgets = config["budgets"]
        self.write("config.private.json", config)
        source = b"".join(p.name.encode() + p.read_bytes() for p in sorted(Path(__file__).parent.glob("*.py")))
        self.write("manifest.json", {"created_at": datetime.now(timezone.utc).isoformat(),
                   "python": platform.python_version(), "source_sha256": hashlib.sha256(source).hexdigest(),
                   "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
                   "protocol": "artifact-feedback-v1", "mode": config.get("mode", "api"),
                   "synthetic_fixture": any(r.get("type") == "demo" for r in config["runtimes"].values())})

    def write(self, name: str, value) -> None:
        path = self.directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x") as handle:
            handle.write(json.dumps(value, indent=2) + "\n")

    def event(self, kind: str, **data):
        with (self.directory / "events.private.jsonl").open("a") as handle:
            handle.write(json.dumps({"kind": kind, "elapsed_seconds": time.monotonic() - self.start, **data}) + "\n")

    def check_time(self):
        if time.monotonic() - self.start >= self.budgets["max_seconds"]:
            raise BudgetExceeded("Run wall-time budget exhausted")

    def runtime(self, name: str, backend):
        journal = self

        class Metered:
            def invoke(self, request: Request):
                journal.check_time()
                if journal.calls >= journal.budgets["max_calls"]:
                    raise BudgetExceeded("Run model-call budget exhausted")
                journal.calls += 1
                call = journal.calls
                # Images are persisted as artifact previews, not repeated in the journal.
                journal.event("model_request", call=call, runtime=name,
                              request={**asdict(request), "images": len(request.images)})
                try:
                    response = backend.invoke(request)
                    journal.event("model_response", call=call, runtime=name,
                                  data=response.data, usage=response.usage)
                    journal.check_time()
                    return response
                except Exception as error:
                    journal.event("model_error", call=call, error_type=type(error).__name__)
                    raise

        return Metered()
