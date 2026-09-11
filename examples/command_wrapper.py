"""Executable fixture for the generic command-runtime contract."""
import json
import sys
from dataclasses import asdict

from experiment.contracts import Request
from experiment.runtimes import DemoRuntime

request = Request(**json.load(sys.stdin))
response = DemoRuntime({}).invoke(request)
json.dump(asdict(response), sys.stdout)
