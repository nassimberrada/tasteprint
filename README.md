# Agent preference-learning experiments

This repository studies a practical question: can an AI worker learn what a particular user likes while completing real tasks, so that it needs fewer revisions on the next task?

Each experiment combines a worker agent, a user agent with a private persona and taste profile, a swappable learning technique, and a runtime that supplies an LLM through OpenRouter, a trusted command wrapper, or an MCP harness. The runner gives the worker a task, collects a submission, asks the user agent for feedback, and repeats until approval or a budget is reached. On later tasks for the same user, only configured learned memory is carried forward.

Test-time behavior is controlled by two independent axes: `test_time_profiling_policy` (`frozen` or `updating`) controls whether learned memory may change during test tasks; `test_time_user_preferences` (`stable` or `drifting`) controls whether scheduled persona changes are applied. Both default to `frozen` and `stable` so held-out transfer is reproducible.

The important metric is **first-pass approval on held-out tasks**: approval on the first submission with no clarification questions. Approval alone is insufficient because a simulator can be overly cooperative; objective checks, independent assessment, cost, and failed tasks are recorded separately.

## Run the local fixture

```bash
uv sync
uv run python -m experiment run
uv run python -m experiment compare --techniques none profile rules skills
uv run python -m unittest discover -s tests -v
```

The deterministic demo exercises the complete state machine without network access. It is plumbing validation, not evidence that an AI understands human taste. Runs create a private, append-only directory under `reports/runs/` containing `manifest.json`, `events.private.jsonl`, immutable artifact versions, `results.json`, `memory.private.json`, `report.md`, and a readable `trace.md` summarizing submissions, checks, feedback, revisions, and terminal states.

## Use an actual model through OpenRouter

OpenRouter uses an OpenAI-compatible chat schema and returns normalized responses. Configure one model for the worker, reviewer, judge, and memory learner, or point each role at a different runtime:

```bash
export OPENROUTER_API_KEY='...'
export EXPERIMENT_MODEL='openai/gpt-5.2'
uv run python -m experiment run --config configs/openrouter.json
```

The model must return the small JSON objects specified in the prompts. Model errors, malformed JSON, token limits, call counts, and wall time stop or record a run rather than being silently treated as approval.

## Use an MCP harness

The same runner can be driven by Codex, Claude, Antigravity, or another MCP client:

```bash
uv sync --extra mcp
uv run python -m experiment serve --config configs/demo.json
```

The server exposes `next_task`, `get_task`, `ask_user`, `submit_artifact`, `get_status`, and `stop_run`. The harness never receives the private persona, independent judge score, or server filesystem path. See `tests/test_mcp.py` for a real SDK client example; run it with `RUN_MCP_E2E=1` when a local MCP subprocess test is desired.

## Swap components

Configurations are JSON and support relative `include` files. Built-ins are runtimes `demo`, `openrouter`, `command`, `codex`; worker and user `llm`; techniques `none`, `profile`, `rules`, `skills`; and tasks `essay`, `webpage`, `files`. Any plugin can instead be written as `module:Factory`, for example `examples.custom_task:Task`.

The public contracts are in `experiment/contracts.py`. Task plugins return a public brief, validate submitted relative text files, run objective checks, and optionally return image data for a visual reviewer. Runtime plugins implement `invoke(Request) -> Response`. Learning techniques see worker-visible evidence and expose `context()`; they never receive the private user profile.

## Repository guide

- `experiment/lab.py` — shared task / feedback / revision state machine.
- `experiment/actors.py` — worker and user-agent behavior.
- `experiment/runtimes.py` — OpenRouter, command-wrapper, and deterministic transports.
- `experiment/techniques.py` — swappable memory strategies.
- `experiment/tasks.py` — task contracts, safe artifact storage, checks, and optional browser inspection.
- `experiment/mcp_server.py` — MCP tools for external harnesses.
- `experiment/config.py`, `plugins.py`, `storage.py`, `reporting.py` — configuration, factories, journals, budgets, and reports.
- `configs/` — demo, OpenRouter, and command-wrapper suites.
- `RESEARCH.md` — hypotheses, validity safeguards, and planned studies.
- `DESIGN.html` — visual architecture and a plain-language walkthrough.

The old numerical choice experiment remains at `experiment/legacy.py` as a small protocol fixture. It is separate from the artifact-feedback engine. For implementation context, open `DESIGN.html` and `RESEARCH.md` before changing the runner.

LLM user simulators can be too agreeable, leak information, or behave unlike people. Use multiple simulator models, hold out tasks and personas, keep the judge independent, and validate promising findings with consented human participants. A successful simulated run is a testable result, not proof of real-user alignment.
