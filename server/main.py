"""MSPclaw Server entry point.

FastAPI app that:
  - Accepts incoming tickets / CLI issue requests
  - Runs the AI brain (ReAct loop) against them
  - Dispatches tool calls over WebSocket to the right client agent
  - Persists jobs and audit log to Postgres

This is a skeleton — endpoints are stubbed. See docs/specs for the design.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from server.connections.ws_manager import ConnectionManager
from server.intake.parser import parse_ticket

load_dotenv()

app = FastAPI(title="MSPclaw Server", version="0.1.0")
connections = ConnectionManager()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "connected_agents": connections.count()}


@app.post("/issues")
async def submit_issue(payload: dict) -> dict:
    """End-user CLI or ticket intake hits this endpoint with a raw issue.

    payload = {
        "tenant_id": "default",
        "client_id": "...",
        "subject": "...",
        "description": "..."
    }
    """
    plan = parse_ticket(payload["subject"], payload.get("description", ""))
    # TODO: persist issue, look up playbook, kick off brain loop, dispatch jobs.
    return {"plan": plan, "status": "accepted"}


@app.websocket("/ws/agent")
async def agent_ws(ws: WebSocket) -> None:
    """Client agents connect here for real-time job dispatch."""
    await connections.connect(ws)
    try:
        while True:
            msg = await ws.receive_json()
            await connections.handle_message(ws, msg)
    except WebSocketDisconnect:
        connections.disconnect(ws)


def run() -> None:
    import uvicorn

    uvicorn.run(
        "server.main:app",
        host=os.environ.get("MSPCLAW_HOST", "0.0.0.0"),
        port=int(os.environ.get("MSPCLAW_PORT", "8080")),
        reload=True,
    )


if __name__ == "__main__":
    run()
