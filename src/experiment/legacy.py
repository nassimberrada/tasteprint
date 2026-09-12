"""Original numerical experiment, retained as a small protocol fixture."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import tempfile

from .runner import evaluate, generate, report, validate


def main():
    parser = argparse.ArgumentParser(description="Predict choices, reveal feedback, update profiles.")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--data", type=Path, help="Chronological JSONL; otherwise generate synthetic choices")
    parser.add_argument("--retention", type=float, default=0.95)
    parser.add_argument("--output", type=Path, default=Path("reports/runs"))
    args = parser.parse_args()
    if not 0 < args.retention <= 1:
        parser.error("--retention must be in (0, 1]")
    try:
        events = (validate([json.loads(line) for line in args.data.read_text().splitlines() if line.strip()])
                  if args.data else generate(args.seed))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    rows = evaluate(events, args.retention)
    summary = report(rows)
    source = b"".join(path.name.encode() + path.read_bytes()
                      for path in sorted(Path(__file__).parent.glob("*.py")))
    manifest = {"created_at": datetime.now(timezone.utc).isoformat(),
                "source": str(args.data) if args.data else "synthetic-v1",
                "seed": args.seed if args.data is None else None,
                "retention": args.retention, "events": len(events),
                "python": platform.python_version(),
                "input_sha256": hashlib.sha256(json.dumps(events, sort_keys=True).encode()).hexdigest(),
                "source_sha256": hashlib.sha256(source).hexdigest()}
    args.output.mkdir(parents=True, exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix="run-", dir=args.output))
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (destination / "predictions.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    (destination / "report.md").write_text(summary)
    print(summary)
    print(f"Artifacts: {destination.resolve()}")


if __name__ == "__main__":
    main()
