# Agent preference-learning experiments

This repository studies a practical question: can an AI worker learn what a particular user likes while completing real tasks, so that it needs fewer revisions on the next task?

Each experiment combines a worker agent, a user agent with a private persona and taste profile, an independent evaluator, a swappable profiling strategy, and a separately selected runtime bundle. The runner gives the worker a task, collects a submission, asks the user agent for feedback, and repeats until approval or a budget is reached. On later tasks for the same user, only the configured preference profile is carried forward.

Test-time behavior is controlled by two independent axes: `test_time_profiling_policy` (`frozen` or `updating`) controls whether learned memory may change during test tasks; `test_time_user_preferences` (`stable` or `drifting`) controls whether scheduled persona changes are applied. Both default to `frozen` and `stable` so held-out transfer is reproducible.

The important metric is **first-pass approval on held-out tasks**: approval on the first submission with no clarification questions. Approval alone is insufficient because a simulator can be overly cooperative; objective checks, independent assessment, cost, and failed tasks are recorded separately. Evaluators also return factor-level fit scores when preference factors are available, so reports show what transferred rather than only one aggregate score.

## Run the local fixture

```bash
uv sync
uv run python -m experiment run --config configs/demo.json --runtimes runtimes/demo.json
uv run python -m experiment compare --config configs/demo.json --runtimes runtimes/demo.json --profiling none summary rules skills
uv run python -m experiment run --config configs/smoke.json --runtimes runtimes/codex.json
uv run python -m unittest discover -s tests -v
uv run python -m experiment dashboard --runs reports/runs
```

The deterministic demo exercises the complete state machine without network access. It is plumbing validation, not evidence that an AI understands human taste. Runs create a private, append-only directory under `reports/runs/` containing `manifest.json`, `events.private.jsonl`, immutable artifact versions, `results.json`, `memory.private.json`, `report.md`, and a readable `trace.md` summarizing submissions, checks, feedback, revisions, and terminal states.

The dashboard polls active run journals, displays worker artifacts and persona-reviewer feedback, and can replay completed runs from their event timeline. It binds to localhost by default.

## Use an actual model through OpenRouter

OpenRouter uses an OpenAI-compatible chat schema and returns normalized responses. Create a runtime bundle mapping worker, reviewer, evaluator, and profiling roles to OpenRouter settings, or point each role at a different provider:

```bash
export OPENROUTER_API_KEY='...'
export EXPERIMENT_MODEL='openai/gpt-5.2'
```

The checked-in `smoke.json` is the fastest Codex plumbing run when paired with `runtimes/codex.json`. `sampled.json` is the fast stratified sample: four personas, one training task, and one held-out task. Pair `benchmark.json` with `runtimes/codex.json` for the full Codex benchmark. Create a similar runtime bundle for OpenRouter runs.

The larger cross-domain benchmark is described in [BENCHMARK.md](BENCHMARK.md).

The model must return the small JSON objects specified in the prompts. Model errors, malformed JSON, token limits, call counts, and wall time stop or record a run rather than being silently treated as approval.

## Use an MCP harness

The same runner can be driven by Codex, Claude, Antigravity, or another MCP client:

```bash
uv sync --extra mcp
uv run python -m experiment serve --config configs/demo.json --runtimes runtimes/demo.json
```

The server exposes `next_task`, `get_task`, `ask_user`, `submit_artifact`, `get_status`, and `stop_run`. The harness never receives the private persona, independent judge score, or server filesystem path. See `tests/test_mcp.py` for a real SDK client example; run it with `RUN_MCP_E2E=1` when a local MCP subprocess test is desired.

## Swap components

Experiment configs are runtime-agnostic JSON and support relative `include` files. Runtime bundles live under `runtimes/` and map logical roles (`worker`, `reviewer`, `evaluator`, `profiling`) to providers. Built-ins are runtimes `demo`, `openrouter`, `command`, `codex`; worker, user, and evaluator `llm`; profiling strategies `none`, `summary`, `rules`, `skills`; and tasks `essay`, `webpage`, `files`. Extensions can instead be written as trusted `module:Factory` plugins; see `CONTRIBUTING.md`.

The public contracts are in `src/experiment/contracts.py`. Task plugins return a public brief, validate submitted relative text files, run objective checks, and optionally return image data for a visual reviewer. Runtime plugins implement `invoke(Request) -> Response`. Profiling strategies see worker-visible evidence and expose `context()`; they never receive the private user profile.

## Repository guide

- `src/experiment/` — implementation package containing the state machine, agents, runtimes, tasks, profiling strategies, MCP server, dashboard, and reporting.
- `configs/` — composable base, demo, smoke, sampled, and full benchmark configurations.
- `RESEARCH.md` — hypotheses, validity safeguards, and planned studies.
- `DESIGN.html` — visual architecture and a plain-language walkthrough.

The old numerical choice experiment remains at `src/experiment/legacy.py` as a small protocol fixture. It is separate from the artifact-feedback engine. For implementation context, open `DESIGN.html` and `RESEARCH.md` before changing the runner.

LLM user simulators can be too agreeable, leak information, or behave unlike people. Use multiple simulator models, hold out tasks and personas, keep the evaluator independent, and validate promising findings with consented human participants. A successful simulated run is a testable result, not proof of real-user alignment.
