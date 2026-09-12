# Contributing

The implementation lives in `src/experiment/`. Run commands through the project
environment so the `src` layout is installed:

```bash
uv sync --all-extras
uv run python -m unittest discover -s tests -v
```

Extensions are configured through trusted `module:Factory` paths. A custom task
implements the public task contract (`public`, `check`, and `inspect`); a custom
runtime implements `invoke(Request) -> Response`. Keep worker-visible data
separate from private personas and independent assessments.

Experiment configs are runtime-agnostic. Put provider definitions in a runtime
bundle under `runtimes/` and pass it with `--runtimes`; do not copy provider
credentials or model-specific settings into task/persona configs. The
`profiling` field selects the swappable preference-inference strategy.

Before submitting changes, validate JSON configs, run the tests, and use the
dashboard to inspect a representative run. Do not commit API keys, private user
histories, generated run directories, or model-provider response dumps.
