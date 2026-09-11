"""Chronological evaluation with feedback withheld until after prediction."""

import random

from .methods import Profile

MODES = ("uninformed", "flat", "conditional")


def validate(events: list) -> list:
    if not events:
        raise ValueError("Input must contain at least one event")
    for index, event in enumerate(events, 1):
        if not isinstance(event, dict):
            raise ValueError(f"Event {index}: expected an object")
        for key in ("user_id", "context"):
            if not isinstance(event.get(key), str) or not event[key].strip():
                raise ValueError(f"Event {index}: {key} must be a nonempty string")
        if event.get("choice") not in ("concise", "detailed"):
            raise ValueError(f"Event {index}: invalid choice")
        if "phase" in event and (not isinstance(event["phase"], str) or not event["phase"]):
            raise ValueError(f"Event {index}: phase must be a nonempty string")
    return events


def generate(seed: int) -> list:
    rng = random.Random(seed)
    events = []
    for step in range(120):
        context = "research" if step % 2 == 0 else "status"
        phase = ("stable" if step < 60 else "exception" if step < 66
                 else "return" if step < 90 else "change")
        for user in range(4):
            detailed = (context == "research") == (user % 2 == 0)
            if context == "research" and phase in {"exception", "change"}:
                detailed = not detailed
            if rng.random() < 0.1:
                detailed = not detailed
            events.append({"user_id": f"person-{user + 1}", "context": context,
                           "choice": "detailed" if detailed else "concise", "phase": phase})
    return events


def evaluate(events: list, retention: float = 0.95) -> list:
    validate(events)
    learners = {}
    rows = []
    for index, event in enumerate(events):
        for mode in MODES:
            key = (event["user_id"], mode)
            if key not in learners:
                learners[key] = Profile(mode, retention)
            learner = learners[key]
            before = learner.snapshot()
            probability = learner.predict(event["context"])
            observed = int(event["choice"] == "detailed")
            accuracy = (0.5 if probability == 0.5
                        else float((probability > 0.5) == bool(observed)))
            learner.observe(event["context"], event["choice"])
            rows.append({"index": index, **event, "phase": event.get("phase", "observed"),
                         "method": mode, "probability_detailed": probability,
                         "brier": (probability - observed) ** 2, "accuracy": accuracy,
                         "state_before": before, "state_after": learner.snapshot()})
    return rows


def report(rows: list) -> str:
    lines = ["# Sequential preference prediction", "",
             "Lower Brier is better. Accuracy awards half credit for ties.", "",
             "| Phase | Method | Choices | Brier | Accuracy |",
             "|---|---|---:|---:|---:|"]
    phases = list(dict.fromkeys(row["phase"] for row in rows))
    for phase in [None, *phases]:
        for mode in MODES:
            group = [row for row in rows if row["method"] == mode
                     and (phase is None or row["phase"] == phase)]
            count = len(group)
            brier = sum(row["brier"] for row in group) / count
            accuracy = sum(row["accuracy"] for row in group) / count
            label = "Overall" if phase is None else phase.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {label} | {mode} | {count} | {brier:.4f} | {accuracy:.1%} |")
    lines.extend(["", "## Interpretation limits", "",
                  "This is one descriptive run, without confidence intervals. Numerical",
                  "baselines do not establish LLM personalization or human preference learning.",
                  "Synthetic results test a constructed mechanism; supplied data must be",
                  "assessed for provenance, scope, and temporal leakage separately.", ""])
    return "\n".join(lines)
