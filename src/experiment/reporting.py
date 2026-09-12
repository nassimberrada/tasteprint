"""Reports include failed and unattempted episodes in the denominator."""
from collections import Counter
import json


def render_report(results: list, calls: int) -> str:
    lines = ["# Artifact-and-feedback experiment", "", f"Metered model calls: {calls}", "",
             "| Split | Planned | Approved | First submission approved | First pass, no questions |",
             "|---|---:|---:|---:|---:|"]
    for split in ("train", "test"):
        group = [row for row in results if row["split"] == split]
        if group:
            count = len(group)
            lines.append(f"| {split} | {count} | " + " | ".join(
                f"{sum(test(row) for row in group) / count:.1%}" for test in (
                    lambda r: r["status"] == "approved", lambda r: r["first_submission_approved"],
                    lambda r: r["first_pass"])) + " |")
    lines.extend(["", "## Terminal states", ""])
    lines.extend(f"- {status}: {count}" for status, count in sorted(Counter(r["status"] for r in results).items()))
    factors = {}
    for row in results:
        for name, score in row.get("final_factor_scores", {}).items():
            factors.setdefault(name, []).append(score)
    if factors:
        lines.extend(["", "## Factor-level evaluation", "",
                      "| Factor | Assessments | Mean final score | Mean score change |",
                      "|---|---:|---:|---:|"])
        for name in sorted(factors):
            deltas = [row["factor_score_delta"][name] for row in results
                      if name in row.get("factor_score_delta", {})]
            values = factors[name]
            lines.append(f"| {name} | {len(values)} | {sum(values) / len(values):.3f} | "
                         f"{(sum(deltas) / len(deltas)) if deltas else 0:.3f} |")
    lines.extend(["", "## Per task", "",
                  "| User | Task | Status | Submissions | Questions | Final preference score | Score delta | Feedback rounds | Memory updates | Time to approval (s) |",
                  "|---|---|---|---:|---:|---:|---:|---:|---:|---:|"])
    for row in results:
        score = row["last_assessment"]["score"] if row["last_assessment"] is not None else "unmeasured"
        clean = lambda value: str(value).replace("|", "\\|").replace("\n", " ")
        lines.append("| " + " | ".join(clean(x) for x in (row["user_id"], row["task_id"], row["status"],
                                                          row["submissions"], row["questions"], score,
                                                          row.get("preference_score_delta") if row.get("preference_score_delta") is not None else "—",
                                                          row.get("feedback_rounds", 0),
                                                          row.get("memory_updates", 0),
                                                          row.get("time_to_approval_seconds") or "—")) + " |")
    lines.extend(["", "First pass requires approval on submission one with zero clarification questions.",
                  "Test-time profiling and preference policies are recorded in the run configuration.",
                  "Independent assessments are hidden from the worker. Missing assessments are not zero scores.",
                  "Failures and unattempted tasks remain in the planned-task denominator.",
                  "This run alone establishes neither statistical significance nor transfer to human users.",
                  "Demo runtime results are plumbing checks, not LLM research evidence.", ""])
    return "\n".join(lines)


def render_trace(events: list) -> str:
    """Render a compact, human-readable trace without private persona/judge data."""
    lines = ["# Run trace", "", "This trace summarizes task briefs, submissions, checks, reviewer feedback, and terminal states.", ""]
    starts = {e["episode"]: e for e in events if e.get("kind") == "task_start"}
    grouped = {}
    for event in events:
        if "episode" in event:
            grouped.setdefault(event["episode"], []).append(event)
    for episode in sorted(grouped):
        start = starts.get(episode, {})
        task = start.get("task", {})
        lines += [f"## Episode {episode}: {start.get('user_id', 'unknown')} / {task.get('id', 'unknown')}", "",
                  f"Task: {task.get('brief', '')}", ""]
        for event in grouped[episode]:
            kind = event.get("kind")
            if kind == "submission":
                check = event.get("check", {})
                lines.append(f"- Version {event.get('version')}: submitted `{event.get('artifact')}`; checks {'passed' if check.get('passed') else 'failed' }.")
            elif kind == "review":
                review = event.get("user_review", {})
                decision = "approved" if review.get("approved") else "requested revision"
                feedback = str(review.get("feedback", "")).replace("\n", " ")
                lines.append(f"- Reviewer: **{decision}** — {feedback}")
            elif kind == "episode_error":
                lines.append(f"- Error: {event.get('error_type', 'unknown')}")
            elif kind == "task_end":
                lines.append(f"- Terminal state: **{event.get('status')}** after {event.get('submissions', 0)} submission(s), {event.get('questions', 0)} question(s), {event.get('seconds', 0):.1f}s.")
        lines.append("")
    return "\n".join(lines)
