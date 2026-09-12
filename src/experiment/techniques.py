"""Memory techniques receive only worker-visible evidence, never a persona."""
import copy
import json

from .contracts import Request


class NoMemory:
    def __init__(self, config: dict, runtime):
        pass

    def context(self):
        return {}

    def learn(self, evidence: dict) -> None:
        pass


class WrittenProfile:
    representation = "A concise written profile of the user's preferences. Return memory as a string."

    def __init__(self, config: dict, runtime):
        self.runtime = runtime
        self.memory = copy.deepcopy(config.get("initial_memory", {}))
        self.max_chars = config.get("max_chars", 12000)

    def context(self):
        return copy.deepcopy(self.memory)

    def learn(self, evidence: dict) -> None:
        result = self.runtime.invoke(Request("learn",
            "Update a persistent user preference model from the supplied observed interaction. "
            "Distinguish personal taste from task requirements and factual corrections. "
            "Record uncertainty; do not turn every one-off correction into a global rule. "
            "Do not infer approval from silence. " + self.representation +
            f" Keep serialized memory below {self.max_chars} characters. "
            "Return {\"memory\": ...}.",
            {"previous": self.context(), "evidence": evidence})).data
        if "memory" not in result or not isinstance(result["memory"], (dict, list, str)):
            raise ValueError("Technique must return a JSON memory object, list or string")
        if len(json.dumps(result["memory"])) > self.max_chars:
            raise ValueError("Technique exceeded max_chars; previous memory retained")
        self.memory = copy.deepcopy(result["memory"])


class RuleMemory(WrittenProfile):
    representation = (
        "Represent memory as {rules:[{condition, preference, exceptions, evidence_ids, confidence}], "
        "uncertainties:[]}. Reconcile contradictions by considering scope, noise and lasting change. "
        "Use evidence_ids from the interaction identifier. Preserve unrelated rules.")


class SkillMemory(WrittenProfile):
    representation = (
        "Represent memory as {skills:[{name, when_to_use, instructions, exceptions, evidence_ids}]}. "
        "Extract reusable procedures for producing work this user likes. Each skill should have "
        "a clear trigger and concrete steps, not just a copy of the last task.")
