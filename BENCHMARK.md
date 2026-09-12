# Cross-domain benchmark

The benchmark configuration is `configs/benchmark.json`. It defines four
personas crossing two latent preference factors: information order
(`concrete_first` / `principle_first`) and expression (`restrained` / `animated`).

It contains 40 episodes per profiling strategy: four training families, two held-out
variants, and four unseen task families (email, data story, troubleshooting
guide, and slide outline). Existing task plugins are reused; public briefs and
materials are visible to the worker, while latent labels and private profiles
remain hidden.

Pair this config with `runtimes/codex.json` for a full GPT-5.6-Luna run. To use
another provider, create an equivalent runtime bundle under `runtimes/` and pass
it with `--runtimes`.

For a faster stratified comparison, use `configs/sampled.json`: it crosses all
four persona factor combinations with one training and one held-out task. It is
intended for rapid method iteration, not statistical claims.
The default evaluation condition is frozen profiling with stable preferences.
Report first-pass approval, objective checks, independent preference scores,
revision count, questions, time, calls, and results by persona, factor, split,
and task family. Include budget failures in denominators.

This is a synthetic benchmark for controlled comparisons, not evidence about
human users. Validate promising results with consented human studies.
