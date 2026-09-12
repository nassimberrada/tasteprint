"""Shared state machine for API workers and MCP-connected harnesses."""
import copy
import hashlib
import json
from pathlib import Path
import time

from .config import resolve
from .contracts import require_text
from .plugins import create
from .storage import BudgetExceeded, Journal
from .tasks import validate_files


class Session:
    def __init__(self, config: dict, output: Path = Path("reports/runs"), runtime_specs: dict | None = None):
        self.config = resolve(config)
        if runtime_specs is not None:
            self.config["runtimes"] = copy.deepcopy(runtime_specs)
        self.config.setdefault("runtimes", {
            "worker": {"type": "demo"}, "reviewer": {"type": "demo"},
            "judge": {"type": "demo"}, "profiling": {"type": "demo"}})
        self.journal = Journal(output, self.config)
        self.runtimes = {name: self.journal.runtime(name, create("runtime", spec))
                         for name, spec in self.config["runtimes"].items()}
        self.worker = None
        if self.config.get("mode", "api") != "mcp":
            spec = self.config["worker"]
            self.worker = create("worker", spec, runtime=self.runtime(spec))
        self.memories = {}
        self.plan = [(u, t) for u in range(len(self.config["users"]))
                     for t in range(len(self.config["tasks"]))]
        self.position = -1
        self.current = None
        self.results = []
        self.closed = False

    def runtime(self, spec: dict, key: str = "runtime"):
        name = spec.get(key)
        if name not in self.runtimes:
            raise ValueError(f"Unknown or missing runtime reference: {name!r}")
        return self.runtimes[name]

    def next_task(self) -> dict:
        if self.current and self.current["status"] == "active":
            raise ValueError("Finish the active task before advancing")
        if self.closed:
            return {"done": True}
        try:
            self.journal.check_time()
        except BudgetExceeded:
            self.close("budget_exhausted")
            return {"done": True, "reason": "budget_exhausted"}
        self.position += 1
        if self.position >= len(self.plan):
            self.close()
            return {"done": True}
        user_index, task_index = self.plan[self.position]
        persona = copy.deepcopy(self.config["users"][user_index])
        changes = persona.pop("changes", [])
        if self.config["test_time_user_preferences"] == "drifting":
            for change in sorted(changes, key=lambda x: x["from_task"]):
                if task_index >= change["from_task"]:
                    persona["preferences"] = copy.deepcopy(change["preferences"])
        task_spec = self.config["tasks"][task_index]
        technique_spec = self.config["profiling"]
        if user_index not in self.memories:
            self.memories[user_index] = create("memory", technique_spec,
                                               runtime=self.runtime(technique_spec, "runtime"))
        self.task = create("task", task_spec)
        self.user = create("user", persona, runtime=self.runtime(persona),
                           judge_runtime=self.runtime(persona, "judge_runtime"))
        self.technique = self.memories[user_index]
        self.current = {"episode": self.position, "user_id": persona["id"],
                        "task_id": task_spec["id"], "split": task_spec.get("split", "train"),
                        "status": "active", "submissions": 0, "questions": 0,
                        "history": [], "artifact": None, "last_check": None,
                        "started": time.monotonic(), "first_pass": False,
                        "first_submission_approved": False, "last_assessment": None,
                        "assessment_scores": [], "memory_updates": 0}
        self.journal.event("task_start", episode=self.position, user_id=persona["id"],
                           task=self.task.public(), split=self.current["split"],
                           memory=self.technique.context())
        return self.get_task()

    def active(self):
        if not self.current or self.current["status"] != "active" or self.closed:
            raise ValueError("No active task; call next_task")
        self.journal.check_time()

    def get_task(self) -> dict:
        self.active()
        state = self.current
        return copy.deepcopy({"episode": state["episode"], "user_id": state["user_id"],
             "task": self.task.public(), "memory": self.technique.context(),
             "history": state["history"], "artifact": state["artifact"],
             "remaining_submissions": self.config["budgets"]["max_submissions"] - state["submissions"],
             "remaining_questions": self.config["budgets"]["max_questions"] - state["questions"]})

    def learn(self, evidence: dict):
        # Frozen profiling allows test-time revisions but prevents persistent
        # profile updates. Updating mode measures continual adaptation.
        if (self.current["split"] == "test" and
                self.config["test_time_profiling_policy"] == "frozen"):
            return
        before = self.technique.context()
        self.technique.learn(copy.deepcopy(evidence))
        self.journal.event("memory_update", episode=self.position, before=before,
                           after=self.technique.context(), evidence_id=evidence["id"])
        self.current["memory_updates"] += 1

    def ask_user(self, question: str) -> dict:
        self.active()
        question = require_text(question, "question")
        if len(question) > 4000:
            raise ValueError("Question exceeds 4000 characters")
        state = self.current
        if state["questions"] >= self.config["budgets"]["max_questions"]:
            return {"error": "Question budget exhausted; submit an artifact"}
        state["questions"] += 1
        answer = self.user.answer(self.task.public(), question, copy.deepcopy(state["history"]))
        interaction = {"question": question, "answer": answer}
        state["history"].append(interaction)
        evidence = {"id": f"e{self.position}-q{state['questions']}",
                    "task": self.task.public(), **interaction}
        self.journal.event("question", episode=self.position, **interaction)
        self.learn(evidence)
        return {"answer": answer, "memory": self.technique.context()}

    def submit_artifact(self, files: dict[str, str]) -> dict:
        self.active()
        files = validate_files(files)
        state = self.current
        if state["submissions"] >= self.config["budgets"]["max_submissions"]:
            self.finish("submission_limit")
            raise ValueError("Submission budget exhausted")
        state["submissions"] += 1
        version = state["submissions"]
        relative = f"episodes/{self.position:04d}/v{version:03d}"
        directory = self.journal.directory / relative / "files"
        directory.mkdir(parents=True, exist_ok=False)
        for name, content in files.items():
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        artifact = {"files": files}
        state["artifact"] = artifact
        check = self.task.check(files)
        if type(check.get("passed")) is not bool or not isinstance(check.get("failures"), list):
            raise ValueError("Task check must return passed:boolean and failures:list")
        state["last_check"] = check
        self.journal.write(relative + "/artifact.json", {
            "sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
            "files": list(files), "check": check})
        self.journal.event("submission", episode=self.position, version=version, artifact=relative, check=check)
        # Invalid artifacts receive objective feedback, without pretending to be visually assessed.
        if check["passed"]:
            images = self.task.inspect(directory)
            review = self.user.review(self.task.public(), artifact, copy.deepcopy(state["history"]), images)
            assessment = self.user.assess(self.task.public(), artifact, images)
        else:
            review = {"approved": False, "feedback": "Fix the objective task requirements."}
            assessment = None
        state["last_assessment"] = assessment
        if assessment is not None:
            state["assessment_scores"].append(assessment["score"])
        accepted = review["approved"] and check["passed"]
        public = {"approved": accepted, "feedback": review["feedback"], "checks": check}
        state["history"].append({"submission": version, **public})
        self.journal.event("review", episode=self.position, version=version,
                           user_review=review, assessment=assessment)
        if version == 1:
            state["first_submission_approved"] = accepted
            state["first_pass"] = accepted and state["questions"] == 0
        # Mark terminal success before memory work: learning failure must not erase approval.
        if accepted:
            self.finish("approved")
        elif version >= self.config["budgets"]["max_submissions"]:
            self.finish("submission_limit")
        evidence = {"id": f"e{self.position}-v{version}", "task": self.task.public(),
                    "artifact": artifact, **public}
        self.learn(evidence)
        public.update({"status": state["status"], "memory": self.technique.context()})
        return public

    def finish(self, status: str):
        state = self.current
        if state and state["status"] == "active":
            state["status"] = status
            result = {key: state[key] for key in ("episode", "user_id", "task_id", "split", "status",
                      "submissions", "questions", "first_pass", "first_submission_approved",
                      "last_check", "last_assessment")}
            result["seconds"] = time.monotonic() - state["started"]
            scores = state["assessment_scores"]
            result.update({"feedback_rounds": len(scores),
                           "memory_updates": state["memory_updates"],
                           "initial_preference_score": scores[0] if scores else None,
                           "final_preference_score": scores[-1] if scores else None,
                           "preference_score_delta": (scores[-1] - scores[0]) if scores else None,
                           "time_to_approval_seconds": result["seconds"] if status == "approved" else None})
            self.results.append(result)
            self.journal.event("task_end", **result)

    def fail(self, error: Exception):
        self.journal.event("episode_error", episode=self.position, error_type=type(error).__name__)
        status = "budget_exhausted" if isinstance(error, BudgetExceeded) else "error"
        self.finish(status)
        if isinstance(error, BudgetExceeded):
            self.close(status)

    def status(self) -> dict:
        # Never expose independent assessments, private profile or private journal paths.
        return {"done": self.closed, "completed": len(self.results), "planned": len(self.plan),
                "episode": self.position, "status": self.current["status"] if self.current else "not_started"}

    def close(self, remaining_status: str = "not_run"):
        if self.closed:
            return
        self.finish(remaining_status)
        completed = {row["episode"] for row in self.results}
        for episode, (user_index, task_index) in enumerate(self.plan):
            if episode not in completed:
                self.results.append({"episode": episode, "user_id": self.config["users"][user_index]["id"],
                    "task_id": self.config["tasks"][task_index]["id"],
                    "split": self.config["tasks"][task_index].get("split", "train"),
                    "status": remaining_status, "submissions": 0, "questions": 0,
                    "first_pass": False, "first_submission_approved": False,
                    "last_check": None, "last_assessment": None, "seconds": 0,
                    "feedback_rounds": 0, "memory_updates": 0,
                    "initial_preference_score": None, "final_preference_score": None,
                    "preference_score_delta": None, "time_to_approval_seconds": None})
        self.closed = True
        self.journal.write("results.json", self.results)
        self.journal.write("memory.private.json", {str(key): value.context() for key, value in self.memories.items()})
        from .reporting import render_report, render_trace
        (self.journal.directory / "report.md").write_text(render_report(self.results, self.journal.calls))
        events_path = self.journal.directory / "events.private.jsonl"
        events = [json.loads(line) for line in events_path.read_text().splitlines()] if events_path.exists() else []
        (self.journal.directory / "trace.md").write_text(render_trace(events))
        self.journal.event("run_end", status=remaining_status, calls=self.journal.calls)

    def run(self):
        if self.worker is None:
            raise ValueError("MCP sessions are driven by a connected harness")
        try:
            while not self.closed:
                try:
                    if self.next_task().get("done"):
                        break
                    while self.current["status"] == "active":
                        action = self.worker.act(self.get_task())
                        if action.get("action") == "ask":
                            self.ask_user(action.get("question"))
                        elif action.get("action") == "submit":
                            self.submit_artifact(action.get("files"))
                        else:
                            raise ValueError("Worker action must be ask or submit")
                except Exception as error:
                    self.fail(error)
        finally:
            self.close("interrupted")
        return self.journal.directory
