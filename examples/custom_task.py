"""Example third-party factory: retain the file contract, add an objective check."""
from experiment.tasks import FileTask


class Task(FileTask):
    def check(self, files):
        result = super().check(files)
        if "example" not in files.get(self.entrypoint, "").lower():
            result["failures"].append("Include a concrete example")
        result["passed"] = not result["failures"]
        return result
