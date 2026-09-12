"""Task plugins define public requirements, checks and artifact inspection."""
import base64
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
import shutil
from threading import Thread

from .contracts import require_text


def validate_files(files: dict, max_bytes: int = 500_000) -> dict[str, str]:
    if not isinstance(files, dict) or not files or len(files) > 32:
        raise ValueError("Submit between 1 and 32 text files")
    size = 0
    for name, content in files.items():
        if not isinstance(name, str) or "\\" in name:
            raise ValueError("File names must be relative POSIX paths")
        path = PurePosixPath(name)
        if (path.is_absolute() or not path.parts or any(p in {"..", "."} for p in path.parts)
                or str(path) != name or any(p.startswith(".") for p in path.parts)
                or any(ord(c) < 32 for c in name) or ":" in name):
            raise ValueError(f"Unsafe artifact path: {name!r}")
        if not isinstance(content, str):
            raise ValueError("Artifact contents must be text")
        size += len(content.encode())
        if size > max_bytes:
            raise ValueError("Artifact exceeds size limit")
    names = set(files)
    for name in names:
        if any(str(parent) in names for parent in PurePosixPath(name).parents):
            raise ValueError("A file cannot also be another file's parent directory")
    return dict(files)


class FileTask:
    def __init__(self, config: dict):
        self.config = config
        self.entrypoint = config.get("entrypoint", "output.txt")
        validate_files({self.entrypoint: ""})
        require_text(config.get("brief"), "task brief")

    def public(self) -> dict:
        return {"id": self.config["id"], "brief": self.config["brief"],
                "format": "text", "entrypoint": self.entrypoint,
                "requirements": self.config.get("checks", {}),
                "materials": self.config.get("materials", {})}

    def check(self, files: dict[str, str]) -> dict:
        failures = []
        checks = self.config.get("checks", {})
        for name in set([self.entrypoint, *checks.get("required_files", [])]):
            if not files.get(name, "").strip():
                failures.append(f"Missing or empty required file: {name}")
        text = files.get(self.entrypoint, "")
        for term in checks.get("contains", []):
            if term.casefold() not in text.casefold():
                failures.append(f"Required content missing: {term}")
        if len(text.split()) < checks.get("min_words", 1):
            failures.append(f"Entry file must contain at least {checks.get('min_words', 1)} words")
        if "max_words" in checks and len(text.split()) > checks["max_words"]:
            failures.append(f"Entry file exceeds {checks['max_words']} words")
        return {"passed": not failures, "failures": failures}

    def inspect(self, directory: Path) -> list[str]:
        return []


class EssayTask(FileTask):
    def __init__(self, config: dict):
        super().__init__({"entrypoint": "essay.md", **config})


class WebTask(FileTask):
    def __init__(self, config: dict):
        super().__init__({"entrypoint": "index.html", **config})
        if not self.entrypoint.endswith(".html"):
            raise ValueError("A webpage entrypoint must end in .html")

    def public(self) -> dict:
        return {**super().public(), "format": "html", "inspection": "rendered screenshot"
                if self.config.get("render", True) else "source only",
                "delivery": "Use self-contained HTML/CSS/JS and local files; external requests are blocked."}

    def check(self, files: dict[str, str]) -> dict:
        result = super().check(files)
        text = files.get(self.entrypoint, "").lower()
        if "<html" not in text or "<title" not in text:
            result["failures"].append("HTML requires an html element and a title")
        result["passed"] = not result["failures"]
        return result

    def inspect(self, directory: Path) -> list[str]:
        if not self.config.get("render", True):
            return []
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError("Rendered tasks need: uv sync --extra render") from None

        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(directory)))
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f"http://127.0.0.1:{server.server_port}/"
        try:
            with sync_playwright() as playwright:
                executable = self.config.get("browser") or shutil.which("chromium")
                browser = playwright.chromium.launch(**({"executable_path": executable} if executable else {}))
                try:
                    page = browser.new_page(viewport={"width": 1280, "height": 800},
                                            accept_downloads=False, service_workers="block")
                    page.route("**/*", lambda route: route.continue_()
                               if route.request.url.startswith(origin) and route.request.method == "GET"
                               else route.abort())
                    page.goto(origin + self.entrypoint, wait_until="load", timeout=15000)
                    page.screenshot(path=str(directory.parent / "preview.png"), full_page=False)
                finally:
                    browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        return ["data:image/png;base64," + base64.b64encode(
            (directory.parent / "preview.png").read_bytes()).decode()]
