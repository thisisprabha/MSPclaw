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
    _job_to_machine: Dict[str, str] = field(default_factory=dict)

    def register_agent(self, machine_id: str, ws: Any) -> None:
        self._agents[machine_id] = ws

    def unregister_agent(self, machine_id: str) -> None:
        self.fail_pending_for_agent(machine_id)
        self._agents.pop(machine_id, None)
        self._job_to_machine = {jid: mid for jid, mid in self._job_to_machine.items() if mid != machine_id}

    def is_connected(self, machine_id: str) -> bool:
        return machine_id in self._agents

    def fail_pending_for_agent(self, machine_id: str) -> int:
        """Fail every pending future whose job is bound to this machine.
        Returns count of futures failed."""
        keys_to_fail = [
            (jid, sn) for (jid, sn) in self._pending
            if self._job_to_machine.get(jid) == machine_id
        ]
        n = 0
        for key in keys_to_fail:
            fut = self._pending.get(key)
            if fut and not fut.done():
                fut.set_exception(RuntimeError(f"agent {machine_id!r} disconnected"))
                n += 1
        return n

    async def dispatch(self, machine_id: str, *, job_id: str, step_no: int,
                       tool: str, args: dict, requires_yes: bool = False,
                       timeout: float = 60.0) -> dict:
        ws = self._agents.get(machine_id)
        if ws is None:
            raise RuntimeError(f"agent {machine_id!r} not connected")

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[(job_id, step_no)] = future
        self._job_to_machine[job_id] = machine_id

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
            self._job_to_machine.pop(job_id, None)

    async def handle_result(self, msg: dict) -> None:
        key = (msg.get("job_id"), msg.get("step_no"))
        fut = self._pending.get(key)
        if fut and not fut.done():
            fut.set_result(msg)
