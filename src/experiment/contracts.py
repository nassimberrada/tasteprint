"""Small public interfaces for interchangeable experiment components."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class Request:
    purpose: str
    instructions: str
    payload: dict
    images: list[str] = field(default_factory=list)  # data URLs, never worker paths


@dataclass
class Response:
    data: dict
    usage: dict = field(default_factory=dict)


class Runtime(Protocol):
    def invoke(self, request: Request) -> Response: ...


class Worker(Protocol):
    def act(self, observation: dict) -> dict: ...


class User(Protocol):
    def review(self, task: dict, artifact: dict, history: list, images: list[str]) -> dict: ...
    def answer(self, task: dict, question: str, history: list) -> str: ...
    def assess(self, task: dict, artifact: dict, images: list[str]) -> dict: ...


class Task(Protocol):
    def public(self) -> dict: ...
    def check(self, files: dict[str, str]) -> dict: ...
    def inspect(self, directory: Path) -> list[str]: ...


class Technique(Protocol):
    def context(self) -> Any: ...
    def learn(self, evidence: dict) -> None: ...


def require_object(value: Any, name: str = "response") -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return value


def require_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value
