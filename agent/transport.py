"""Agent-side WebSocket transport.

Maintains a persistent outbound connection to the MSP server. Reconnects
with exponential backoff. Hands incoming dispatch messages to the executor
and streams results back.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

import websockets

log = logging.getLogger("mspclaw.agent.transport")


@dataclass
class AgentTransport:
    server_url: str
    tenant_id: str
    machine_id: str
    token: str
    os_name: str
    runner: object  # ToolRunner — kept loose to avoid circular import

    async def run_forever(self) -> None:
        backoff = 1
        while True:
            try:
                async with websockets.connect(self.server_url) as ws:
                    log.info("connected to %s", self.server_url)
                    backoff = 1
                    await self._hello(ws)
                    await self._loop(ws)
            except Exception as e:
                log.warning("connection error: %s; reconnecting in %ss", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def _hello(self, ws) -> None:
        await ws.send(
            json.dumps(
                {
                    "type": "hello",
                    "tenant_id": self.tenant_id,
                    "machine_id": self.machine_id,
                    "os": self.os_name,
                    "token": self.token,
                    "agent_version": "0.1.0",
                }
            )
        )

    async def _loop(self, ws) -> None:
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("type") == "dispatch":
                result = await self.runner.run(msg)  # type: ignore[attr-defined]
                await ws.send(json.dumps({"type": "result", **result}))
            elif msg.get("type") == "hello_ack":
                log.info("server ack received")
            else:
                log.debug("unhandled message: %s", msg.get("type"))
