"""WebSocket connection manager.

Owns a Dispatcher (the request/response layer). On `hello`, registers the
agent. On `result`, hands the message to the dispatcher to resolve the
matching pending Future.
"""
from __future__ import annotations

from typing import Dict

from fastapi import WebSocket

from server.connections.dispatcher import Dispatcher


class ConnectionManager:
    def __init__(self) -> None:
        self.dispatcher = Dispatcher()
        self._meta: Dict[WebSocket, dict] = {}

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()

    def disconnect(self, ws: WebSocket) -> None:
        meta = self._meta.pop(ws, None)
        if meta and meta.get("machine_id"):
            self.dispatcher.unregister_agent(meta["machine_id"])

    def count(self) -> int:
        return len(self._meta)

    async def handle_message(self, ws: WebSocket, msg: dict) -> None:
        msg_type = msg.get("type")
        if msg_type == "hello":
            self._meta[ws] = msg
            self.dispatcher.register_agent(msg["machine_id"], ws)
            await ws.send_json({"type": "hello_ack"})
        elif msg_type == "result":
            await self.dispatcher.handle_result(msg)
        else:
            await ws.send_json({"type": "error", "reason": f"unknown type: {msg_type}"})
