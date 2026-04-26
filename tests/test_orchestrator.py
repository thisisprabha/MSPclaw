import asyncio
import pytest

from server.brain.orchestrator import Orchestrator
from server.connections.dispatcher import Dispatcher


class StubBrain:
    """Pretend LLM. Returns scripted responses in order."""
    def __init__(self, scripted):
        self.scripted = list(scripted)
        self.calls = []

    async def step(self, prompt, history):
        self.calls.append({"prompt": prompt, "history": history})
        return self.scripted.pop(0)


class StubDispatcher:
    def __init__(self, results):
        self.results = list(results)
        self.requests = []

    def is_connected(self, _): return True

    async def dispatch(self, machine_id, *, job_id, step_no, tool, args, **_):
        self.requests.append((tool, args))
        return self.results.pop(0)


@pytest.mark.asyncio
async def test_orchestrator_runs_to_final_answer():
    brain = StubBrain([
        "Thought: check system\nAction: get_system_info\nAction Input: {}",
        "Final Answer:\nIssue Summary: CPU pegged.\nDiagnostics: 99% used.\nRecommended Fixes:\n1. Quit Chrome.",
    ])
    dispatcher = StubDispatcher([
        {"ok": True, "data": {"cpu": 99.0}, "error": None},
    ])

    orch = Orchestrator(brain=brain, dispatcher=dispatcher)
    final = await orch.run(
        machine_id="mac-1",
        job_id="j1",
        playbook_intent="diagnose slowness",
        allowed_tools=["get_system_info"],
        parsed_issue={"issue": "slow", "possibleCauses": ["a"], "resolutionSteps": []},
    )
    assert "CPU pegged" in final
    assert dispatcher.requests == [("get_system_info", {})]
