"""Trusted Python factories: built-in names or 'module:factory'."""
from importlib import import_module

BUILTINS = {
    "runtime": {"openrouter": "experiment.runtimes:OpenRouter",
                "command": "experiment.runtimes:CommandRuntime",
                "codex": "experiment.runtimes:CodexRuntime",
                "demo": "experiment.runtimes:DemoRuntime"},
    "worker": {"llm": "experiment.actors:LLMWorker"},
    "user": {"llm": "experiment.actors:LLMUser"},
    "evaluator": {"llm": "experiment.actors:LLMEvaluator"},
    "task": {"essay": "experiment.tasks:EssayTask",
             "webpage": "experiment.tasks:WebTask",
             "files": "experiment.tasks:FileTask"},
    "profiling": {"none": "experiment.techniques:NoMemory",
                   "summary": "experiment.techniques:WrittenProfile",
                   "rules": "experiment.techniques:RuleMemory",
                   "skills": "experiment.techniques:SkillMemory"},
}


def create(category: str, spec: dict, **services):
    kind = spec.get("type", "")
    target = BUILTINS[category].get(kind, kind)
    if not isinstance(target, str) or ":" not in target:
        raise ValueError(f"Unknown {category} plugin: {kind!r}")
    module, name = target.split(":", 1)
    factory = getattr(import_module(module), name)
    return factory(dict(spec), **services)
