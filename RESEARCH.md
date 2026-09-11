# Research plan

## Problem

An assistant can improve one artifact through feedback without learning anything durable about its user. This project asks whether a worker can infer a user's conditional preferences from repeated artifact reviews, carry that understanding to a new task, and revise it when preferences change.

The operational target is fewer clarification questions and revisions, especially **first-pass approval on held-out tasks** for a previously encountered user, while objective task quality remains acceptable.

## Experimental unit

An episode is one user, one task, and one conversation. The worker receives a public brief and permitted memory. It may ask bounded questions and submit complete artifact files. Objective checks run first. A user agent reviews passing artifacts and returns approval or feedback. A separate assessment receives no negotiation history and scores preference fit. Episodes terminate at approval, a submission limit, an error, or a budget limit.

Test-time policy is factored into profiling (`frozen` versus `updating`) and user preferences (`stable` versus `drifting`). Results record convergence-oriented measures including feedback rounds, time to approval, initial/final preference scores, score delta, and memory updates. Frozen/stable is the default transfer condition; updating/drifting measures continual adaptation and recovery.

Training tasks can update persistent memory. Held-out test tasks may use their current feedback for revision, but persistent memory is frozen so transfer can be measured. Every submission is an immutable version; every model call and state change is journaled.

## Pluggable factors

The engine keeps these factors independent:

- **Task:** brief, artifact format, objective checks, materials, and optional rendering.
- **User agent:** private persona, preferences, feedback style, and scheduled changes.
- **Worker:** policy for asking, creating, and revising.
- **Technique:** no memory, written profile, scoped rules, skills, retrieval, or later weight adaptation.
- **Runtime:** OpenRouter API, command wrapper, or MCP client driving the same tools.

An extension is a trusted Python factory referenced by `module:Factory` in JSON. Configuration is declarative; tasks needing custom execution or rendering can supply it through a plugin.

## Hypotheses

1. Conditional memory transfers better than a flat profile when taste depends on task context.
2. Evidence, provenance, uncertainty, and exceptions improve adaptation after noisy feedback or a preference change.
3. Selective clarification questions reduce total interaction cost under a fixed question budget.
4. Skills or explicit rules reduce revision count on new tasks without lowering objective quality.
5. A model-specific adapter adds value beyond supplying the same memory and examples in context, and can be rebuilt when the base model changes.

## Baselines and metrics

Compare no persistent memory, recent conversation, evolving written profile, retrieved examples, scoped rule memory, and any learned adapter. Keep worker model, user agent, task order, budgets, and available evidence matched.

Primary metrics are first-pass approval on test tasks, approval within the submission budget, revisions, questions, time, model calls, and cost. Secondary metrics are objective check success, independent preference-fit score, adaptation delay after a change, retention of unrelated preferences, calibration, and regression after updates. Include failed and unattempted episodes in denominators.

## Validity safeguards

The user profile is private to the reviewer and independent assessor. The worker sees public task data, its memory, and returned feedback. The assessor sees no negotiation history. Artifact text is treated as untrusted data in prompts. File paths are constrained to relative text files and each version is written once.

LLM simulators may be sycophantic, leak their profile, or fail to resemble human choices. Vary simulator models and feedback styles, test simulator consistency, use hidden preference checks, hold out task families, and compare against a shuffled-user profile. Treat simulator results as mechanism evidence. A consented human study is needed for claims about people.

## Current implementation

The deterministic `demo` runtime exercises the full loop locally. `openrouter` performs real JSON chat calls. `command` invokes a trusted executable that reads a JSON request from stdin and writes a JSON response to stdout. `serve` exposes the shared session through MCP tools for an external harness. Built-in tasks are text essays, source-checked HTML pages, and generic files; browser screenshots require the optional `render` extra.

The old numerical choice experiment in `experiment/legacy.py` remains useful for checking temporal prediction mechanics, but is not an artifact-feedback result.

## Next studies

1. Run the same suite across several OpenRouter model families and user simulators.
2. Add richer task plugins: coding projects with tests, games with executable checks, and rendered design tasks.
3. Add explicit competing hypotheses for noise, temporary exceptions, and lasting changes.
4. Add retrieval and active-question techniques under equal context and cost budgets.
5. Audit simulator behavior against a small, consented human choice set.
6. Compare context memory, rules, skills, and LoRA consolidation on held-out tasks and after switching the worker model.
