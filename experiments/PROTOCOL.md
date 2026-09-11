# First experiment: prediction before feedback

Run from the root with `python -m experiment --seed 7`.

For every event, create or retrieve independent state for that user and method.
Pass only context to prediction, score the probability of `detailed`, then reveal
the choice and update. Persist both state snapshots. Never shuffle time.

The default generator produces 120 choices for each of four fictional users,
interleaved. User preferences are deliberately balanced: two users prefer detail
in research and brevity in status updates; the other two have opposite tastes.
There is 10% independent label noise. Contexts alternate. During steps 60–65,
research choices temporarily invert; from step 90 they permanently invert.
These interventions and phase labels are withheld from learners.

The conditional method has one discounted count pair per context. Its prior is
the overall estimate with strength 2; counts decay on each observation of that
context. The flat method uses discounted global counts and a Beta(1,1) prior.
Both use the same retention setting, default 0.95. Their probability estimates
are heuristics, not a proven posterior over changing human preferences.

Report mean Brier score and tie-adjusted accuracy overall and by phase. The
runner reports one seed without significance claims. For research conclusions,
use multiple seeds, paired user-level comparisons, and uncertainty intervals.
Do not treat correlated events from one user as independent participants.

## What this does not test

- Anticipation across unseen semantic task families.
- Whether an exception is actually recognized as temporary.
- Learned change detection, selective invalidation or calibrated uncertainty.
- Natural-language preference extraction, active questions or generation quality.

The conditional method is well matched to this constructed world by design.
Any win is a mechanism demonstration, not evidence of broad superiority.
For next experiments, hold out contexts and task families, vary noise and change
rates, include stable-only worlds, and compare equal-information LLM baselines.
