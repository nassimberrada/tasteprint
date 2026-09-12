"""JSON configs support includes and explicit environment placeholders."""
import copy
import json
import os
from pathlib import Path
import re


def load(path: Path, seen: tuple = ()) -> dict:
    path = path.resolve()
    if path in seen:
        raise ValueError("Configuration include cycle")
    config = json.loads(path.read_text())
    if not isinstance(config, dict):
        raise ValueError("Config must be an object")
    includes = config.pop("include", [])
    if not isinstance(includes, list):
        raise ValueError("include must be an array of relative file names")
    merged = {}
    for name in includes:
        merged.update(load(path.parent / name, (*seen, path)))
    merged.update(config)  # Top-level replacement, not implicit deep merging.
    # Keep the pre-0.3 name available to programmatic callers while configs use
    # Keep older names available to programmatic callers while configs use the
    # clearer ``profiling`` strategy name.
    if "profiling" in merged:
        merged.setdefault("memory", copy.deepcopy(merged["profiling"]))
        merged.setdefault("technique", copy.deepcopy(merged["profiling"]))
    return merged


def resolve(config: dict) -> dict:
    def expand(value):
        if isinstance(value, dict):
            return {key: expand(item) for key, item in value.items()}
        if isinstance(value, list):
            return [expand(item) for item in value]
        if isinstance(value, str) and re.fullmatch(r"\$\{[A-Z][A-Z0-9_]*\}", value):
            name = value[2:-1]
            if name not in os.environ:
                raise ValueError(f"Export {name} before running this config")
            return os.environ[name]
        return value
    result = expand(copy.deepcopy(config))
    result.setdefault("test_time_profiling_policy", "frozen")
    result.setdefault("test_time_user_preferences", "stable")
    if result["test_time_profiling_policy"] not in {"frozen", "updating"}:
        raise ValueError("test_time_profiling_policy must be frozen or updating")
    if result["test_time_user_preferences"] not in {"stable", "drifting"}:
        raise ValueError("test_time_user_preferences must be stable or drifting")
    # Runtime implementations are supplied separately by the CLI or Session.
    # Keep accepting an embedded runtimes object for older callers.
    for key in ("users", "tasks", "worker"):
        if key not in result:
            raise ValueError(f"Missing config field: {key}")
    if "profiling" not in result:
        if "memory" in result:
            result["profiling"] = result["memory"]
        elif "technique" in result:
            result["profiling"] = result["technique"]
        else:
            raise ValueError("Missing config field: profiling")
    # If an older caller explicitly changed an alias, honor that override.
    if "technique" in result and result["technique"] != result["profiling"]:
        result["profiling"] = result["technique"]
    elif "memory" in result and result["memory"] != result["profiling"]:
        result["profiling"] = result["memory"]
    result["memory"] = result["profiling"]
    result["technique"] = result["profiling"]
    for key in ("users", "tasks"):
        entries = result[key]
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"{key} must be a nonempty array")
        ids = [entry.get("id") for entry in entries]
        if any(not isinstance(name, str) or not name.strip() for name in ids) or len(set(ids)) != len(ids):
            raise ValueError(f"{key} must have distinct nonempty ids")
    heldout_seen = False
    for task in result["tasks"]:
        if task.get("split", "train") not in {"train", "test"}:
            raise ValueError("Task split must be train or test")
        heldout_seen |= task.get("split") == "test"
        if heldout_seen and task.get("split", "train") == "train":
            raise ValueError("Training tasks must precede held-out test tasks")
    budgets = {"max_submissions": 4, "max_questions": 2, "max_calls": 200,
               "max_seconds": 1800, **result.get("budgets", {})}
    for name, value in budgets.items():
        if name not in {"max_submissions", "max_questions", "max_calls", "max_seconds"}:
            raise ValueError(f"Unknown budget: {name}")
        if type(value) is not int or value < (0 if name == "max_questions" else 1):
            raise ValueError(f"Invalid budget: {name}")
    result["budgets"] = budgets
    # Never put secret values into config/manifests. Runtime keys are env references.
    def reject_secrets(value):
        if isinstance(value, dict):
            if any(key.lower() in {"api_key", "authorization", "token", "password"} for key in value):
                raise ValueError("Use api_key_env; do not store credentials in experiment configs")
            for child in value.values():
                reject_secrets(child)
        elif isinstance(value, list):
            for child in value:
                reject_secrets(child)
    reject_secrets(result)
    return result
