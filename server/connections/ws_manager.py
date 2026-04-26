"""WebSocket connection manager.

Tracks connected client agents per tenant. Routes job dispatch messages from
the brain to the correct agent. Receives tool results back.

Wire format (v1, custom JSON over WebSocket — MCP-shaped for v2 migration):

    Agent → Server (hello):
      {"type": "hello", "tenant_id": "...", "machine_id": "...", "agent_version": "..."}

    Server → Agent (dispatch):
      {"type": "dispatch", "job_id": "...", "step_no": 1,
       "tool": "get_system_info", "args": {...}, "requires_yes": false}

    Agent → Server (result):
      {"type": "result", "job_id": "...", "step_no": 1,
       "ok": true, "data": {...}, "error": null}
"""

from __future__ import annotations

from typing import Dict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        # machine_id → WebSocket
        self._agents: Dict[str, WebSocket] = {}
        self._meta: Dict[WebSocket, dict] = {}

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()

    def disconnect(self, ws: WebSocket) -> None:
        meta = self._meta.pop(ws, None)
        if meta and meta.get("machine_id") in self._agents:
            del self._agents[meta["machine_id"]]

    def count(self) -> int:
        return len(self._agents)

    def get(self, machine_id: str) -> WebSocket | None:
        return self._agents.get(machine_id)

    async def handle_message(self, ws: WebSocket, msg: dict) -> None:
        msg_type = msg.get("type")
        if msg_type == "hello":
            self._meta[ws] = msg
            self._agents[msg["machine_id"]] = ws
            await ws.send_json({"type": "hello_ack"})
        elif msg_type == "result":
            # TODO: persist to job_steps table, signal brain to continue.
            pass
        else:
            await ws.send_json({"type": "error", "reason": f"unknown type: {msg_type}"})

    async def dispatch(self, machine_id: str, payload: dict) -> None:
        ws = self._agents.get(machine_id)
        if not ws:
            raise RuntimeError(f"agent {machine_id} not connected")
        await ws.send_json({"type": "dispatch", **payload})
