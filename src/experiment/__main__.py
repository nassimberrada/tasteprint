"""CLI for local runs, comparisons and the worker-facing MCP server."""
import argparse
import copy
import json
from pathlib import Path
import sys

from .config import load
from .lab import Session


def main():
    parser = argparse.ArgumentParser(description="Study how agents learn individual preferences.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "compare", "serve"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path, default=Path(__file__).parents[2] / "configs/demo.json")
        command.add_argument("--output", type=Path, default=Path("reports/runs"))
        command.add_argument("--runtimes", type=Path, default=Path("runtimes/demo.json"),
                             help="JSON runtime bundle; use runtimes/codex.json for Codex")
        if name == "compare":
            command.add_argument("--profiling", "--techniques", dest="profiling", nargs="+",
                                 default=["none", "summary", "rules", "skills"],
                                 help="Profiling strategies to compare")
    commands.add_parser("plugins", help="List built-in factories")
    dashboard = commands.add_parser("dashboard", help="Serve a live run dashboard and replay UI")
    dashboard.add_argument("--runs", type=Path, default=Path("reports/runs"))
    dashboard.add_argument("--host", default="127.0.0.1")
    dashboard.add_argument("--port", type=int, default=8765)
    commands.add_parser("legacy", help="Old numerical choice experiment; use python -m experiment.legacy")
    args = parser.parse_args()
    if args.command == "legacy":
        from .legacy import main as legacy
        sys.argv = [sys.argv[0]]
        legacy()
        return
    if args.command == "plugins":
        from .plugins import BUILTINS
        print(json.dumps(BUILTINS, indent=2))
        return
    if args.command == "dashboard":
        from .dashboard import serve
        serve(args.runs, args.host, args.port)
        return
    try:
        config = load(args.config)
        runtime_specs = load(args.runtimes)
        if args.command == "serve":
            from .mcp_server import build_server
            config["mode"] = "mcp"
            session = Session(config, args.output, runtime_specs)
            print(f"Private experiment records: {session.journal.directory}", file=sys.stderr)
            try:
                build_server(session).run(transport="stdio")
            finally:
                session.close("interrupted")
        else:
            selections = args.profiling if args.command == "compare" else [config["profiling"]["type"]]
            paths = []
            for technique in selections:
                variant = copy.deepcopy(config)
                variant["mode"] = "api"
                variant["profiling"]["type"] = technique
                # Keep the legacy alias synchronized for older config consumers.
                variant["memory"]["type"] = technique
                variant["technique"]["type"] = technique
                session = Session(variant, args.output, runtime_specs)
                destination = session.run()
                print(f"{technique}: {destination}")
                print((destination / "report.md").read_text())
                paths.append(destination)
            if any(row["status"] in {"error", "budget_exhausted"} for path in paths
                   for row in json.loads((path / "results.json").read_text())):
                return 1
    except (ValueError, RuntimeError, OSError, KeyError, ImportError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
