"""Async ReAct orchestrator.

Drives a brain (LLM) → dispatcher (WebSocket to agent) loop until the brain
emits a Final Answer or the iteration cap is hit. Tool whitelisting is
enforced before dispatch — the brain CANNOT escape the playbook.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from server.brain.prompt import build_prompt

MAX_STEPS = 8

_ACTION_RE = re.compile(r"Action:\s*(\S+)\s*\nAction Input:\s*(\{.*?\})", re.DOTALL)
_FINAL_RE = re.compile(r"Final Answer:\s*(.*)", re.DOTALL)


class Brain(Protocol):
    async def step(self, prompt: str, history: list[dict]) -> str: ...


class DispatcherProto(Protocol):
    def is_connected(self, machine_id: str) -> bool: ...
    async def dispatch(self, machine_id: str, *, job_id: str, step_no: int,
                       tool: str, args: dict, requires_yes: bool = False,
                       timeout: float = 60.0) -> dict: ...


@dataclass
class Orchestrator:
    brain: Brain
    dispatcher: DispatcherProto

    async def run(self, *, machine_id: str, job_id: str, playbook_intent: str,
                  allowed_tools: list[str], parsed_issue: dict) -> str:
        if not self.dispatcher.is_connected(machine_id):
            raise RuntimeError(f"agent {machine_id} not connected")

        prompt = build_prompt(
            playbook_intent=playbook_intent,
            allowed_tools=allowed_tools,
            parsed_issue=parsed_issue,
        )
        history: list[dict] = []
        allowed = set(allowed_tools)
        wildcard = "*" in allowed

        for step_no in range(1, MAX_STEPS + 1):
            text = await self.brain.step(prompt, history)

            if (m := _FINAL_RE.search(text)):
                return m.group(1).strip()

            am = _ACTION_RE.search(text)
            if not am:
                history.append({"role": "system", "content": "Could not parse Action. Try again."})
                continue

            tool = am.group(1).strip()
            try:
                args = json.loads(am.group(2))
            except json.JSONDecodeError:
                history.append({"role": "system", "content": f"Invalid JSON for Action Input: {am.group(2)}"})
                continue

            if not wildcard and tool not in allowed:
                history.append({"role": "system",
                                "content": f"Tool '{tool}' is not allowed at this escalation level."})
                continue

            result = await self.dispatcher.dispatch(
                machine_id, job_id=job_id, step_no=step_no, tool=tool, args=args,
            )
            history.append({"role": "assistant", "content": text})
            history.append({"role": "tool", "tool": tool, "result": result})

        return "Final Answer:\nIssue Summary: Could not converge within step limit.\n"
