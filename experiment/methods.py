"""Numerical baselines; these do not infer natural-language rules."""


class Profile:
    def __init__(self, mode: str, retention: float = 0.95):
        if mode not in {"uninformed", "flat", "conditional"}:
            raise ValueError(f"Unknown mode: {mode}")
        if not 0 < retention <= 1:
            raise ValueError("retention must be in (0, 1]")
        self.mode = mode
        self.retention = retention
        self.global_counts = [0.0, 0.0]
        self.context_counts = {}

    def predict(self, context: str) -> float:
        if self.mode == "uninformed":
            return 0.5
        negative, positive = self.global_counts
        prior = (positive + 1) / (negative + positive + 2)
        if self.mode == "flat":
            return prior
        negative, positive = self.context_counts.get(context, (0.0, 0.0))
        return (positive + 2 * prior) / (negative + positive + 2)

    def observe(self, context: str, choice: str) -> None:
        if choice not in {"concise", "detailed"}:
            raise ValueError("Unknown choice")
        if self.mode == "uninformed":
            return
        index = int(choice == "detailed")
        groups = [self.global_counts]
        if self.mode == "conditional":
            groups.append(self.context_counts.setdefault(context, [0.0, 0.0]))
        for counts in groups:
            counts[0] *= self.retention
            counts[1] *= self.retention
            counts[index] += 1

    def snapshot(self) -> dict:
        return {"global": list(self.global_counts),
                "contexts": {key: list(value) for key, value in self.context_counts.items()}}
