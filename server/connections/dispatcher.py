"""Async request/response over WebSocket.

The brain calls `await dispatcher.dispatch(...)` and gets a result back as if
it were a local function call. Internally, dispatch sends a `dispatch` message
over WebSocket and waits on a Future keyed by (job_id, step_no). When the
agent's `result` message comes back, ws_manager calls `handle_result(...)`,
which resolves the matching Future.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

Key = Tuple[str, int]


@dataclass
class Dispatcher:
    _agents: Dict[str, Any] = field(default_factory=dict)
    _pending: Dict[Key, asyncio.Future] = field(default_factory=dict)

    def register_agent(self, machine_id: str, ws: Any) -> None:
        self._agents[machine_id] = ws

    def unregister_agent(self, machine_id: str) -> None:
        self._agents.pop(machine_id, None)

    def is_connected(self, machine_id: str) -> bool:
        return machine_id in self._agents

    async def dispatch(self, machine_id: str, *, job_id: str, step_no: int,
                       tool: str, args: dict, requires_yes: bool = False,
                       timeout: float = 60.0) -> dict:
        ws = self._agents.get(machine_id)
        if ws is None:
            raise RuntimeError(f"agent {machine_id!r} not connected")

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[(job_id, step_no)] = future

        await ws.send_json({
            "type": "dispatch",
            "job_id": job_id,
            "step_no": step_no,
            "tool": tool,
            "args": args,
            "requires_yes": requires_yes,
        })

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending.pop((job_id, step_no), None)

    async def handle_result(self, msg: dict) -> None:
        key = (msg.get("job_id"), msg.get("step_no"))
        fut = self._pending.get(key)
        if fut and not fut.done():
            fut.set_result(msg)
