# Data

`examples.jsonl` is a tiny, fictional stream for inspecting behavior. The default
command generates a longer seeded synthetic stream. Neither is human evidence.

Each line is one choice in chronological order:

```json
{"user_id":"person-1","context":"research","choice":"detailed","phase":"stable"}
```

`choice` must be `concise` or `detailed`. `user_id` and `context` must be nonempty
strings. `phase` is an optional evaluation label (defaults to `observed`). Only
context reaches prediction; choices are revealed afterward. Phase labels never
reach learners. Each user has independent state, and input order is preserved.

This deliberately narrow schema does not represent actual text pairs, task
families, preference dimensions, or explicit overrides yet. Do not interpret
context labels as evidence of semantic generalization.

Keep real histories in ignored `data/private/`. Collect consent, remove identifying
information, record collection provenance, and decide access/deletion procedures
before beginning a human study. Generated reports also contain per-user traces.
