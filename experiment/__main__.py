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
        command.add_argument("--config", type=Path, default=Path(__file__).parent.parent / "configs/demo.json")
        command.add_argument("--output", type=Path, default=Path("reports/runs"))
        if name == "compare":
            command.add_argument("--techniques", nargs="+", default=["none", "profile", "rules", "skills"])
    commands.add_parser("plugins", help="List built-in factories")
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
    try:
        config = load(args.config)
        if args.command == "serve":
            from .mcp_server import build_server
            config["mode"] = "mcp"
            session = Session(config, args.output)
            print(f"Private experiment records: {session.journal.directory}", file=sys.stderr)
            try:
                build_server(session).run(transport="stdio")
            finally:
                session.close("interrupted")
        else:
            selections = args.techniques if args.command == "compare" else [config["technique"]["type"]]
            paths = []
            for technique in selections:
                variant = copy.deepcopy(config)
                variant["mode"] = "api"
                variant["technique"]["type"] = technique
                session = Session(variant, args.output)
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
