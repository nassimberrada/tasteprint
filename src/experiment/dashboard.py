"""Dependency-free local dashboard. Only worker-visible journal fields are served."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

PAGE = (Path(__file__).with_name("dashboard.html")).read_text()

_FIELDS = {
    "task_start": ("user_id", "task", "split", "memory"),
    "submission": ("version", "artifact", "check"),
    "review": ("version", "user_review"),
    "question": ("question", "answer"),
    "task_end": ("status", "seconds", "submissions", "questions", "first_pass"),
    "episode_error": ("error_type",),
    "memory_update": ("before", "after", "evidence_id"),
    "run_end": ("status",),
}


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def _contained(base: Path, relative: str) -> Path | None:
    """Resolve journal paths without following references outside their root."""
    if not isinstance(relative, str):
        return None
    path = (base / relative).resolve()
    return path if path.is_relative_to(base.resolve()) else None


def _events(run: Path) -> list[dict]:
    try:
        lines = (run / "events.private.jsonl").read_text().splitlines()
    except (OSError, UnicodeError):
        return []
    events = []
    for line in lines:
        # A writer can be halfway through its final line during live polling.
        try:
            raw = json.loads(line)
        except ValueError:
            continue
        if not isinstance(raw, dict) or raw.get("kind") not in _FIELDS:
            continue
        fields = ("kind", "episode", "elapsed_seconds") + _FIELDS[raw["kind"]]
        event = {key: raw[key] for key in fields if key in raw}
        if "user_review" in event:
            review = event["user_review"]
            event["user_review"] = {key: review[key] for key in ("approved", "feedback") if isinstance(review, dict) and key in review}
        if event["kind"] == "submission":
            directory = _contained(run, event.get("artifact", ""))
            files = []
            if directory:
                artifact = _read_json(directory / "artifact.json", {})
                names = artifact.get("files", []) if isinstance(artifact, dict) else []
                file_root = directory / "files"
                if not isinstance(names, list):
                    names = []
                for name in names[:100]:
                    path = _contained(file_root, name)
                    if path is None or not path.is_file() or not path.is_relative_to(run.resolve()):
                        continue
                    try:
                        with path.open(errors="replace") as handle:
                            content = handle.read(48001)
                        files.append({"name": name, "text": content[:48000], "truncated": len(content) > 48000})
                    except OSError:
                        continue
            event["artifact_files"] = files
            event["artifact_text"] = "\n".join(f"--- {item['name']} ---\n{item['text']}" for item in files)
        events.append(event)
    return events


def serve(root: Path, host: str = "127.0.0.1", port: int = 8765):
    root = root.resolve()

    class Handler(BaseHTTPRequestHandler):
        def send(self, body, content_type="application/json; charset=utf-8", status=200):
            raw = body if isinstance(body, bytes) else body.encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            path = unquote(urlparse(self.path).path)
            # Random run IDs are not chronological; creation time selects latest.
            runs = sorted((p for p in root.glob("run-*") if p.is_dir() and not p.is_symlink()),
                          key=lambda p: (_read_json(p / "manifest.json", {}).get("created_at", ""), p.name))
            names = [p.name for p in runs]
            if path == "/":
                return self.send(PAGE, "text/html; charset=utf-8")
            if path == "/api/runs":
                return self.send(json.dumps(names))
            if path.startswith("/api/run/"):
                name = path[len("/api/run/"):]
                if name not in names:
                    return self.send(json.dumps({"error": "unknown run"}), status=404)
                events = _events(root / name)
                return self.send(json.dumps({"events": events, "complete": any(e["kind"] == "run_end" for e in events)}))
            self.send(json.dumps({"error": "not found"}), status=404)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Dashboard: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
