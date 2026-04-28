"""MSPclaw Server entry point — v0.1 wiring."""
from __future__ import annotations

import os
import platform
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

# Brain adapters imported lazily inside _brain() so an unselected provider's
# missing API key never breaks startup.
from server.brain.orchestrator import Orchestrator
from server.connections.ws_manager import ConnectionManager
from server.intake.parser import parse_ticket
from server.playbooks.registry import PlaybookRegistry
from server.storage import repo
from server.storage.db import get_session, init_db

load_dotenv()

app = FastAPI(title="MSPclaw Server", version="0.1.0")
connections = ConnectionManager()
playbooks = PlaybookRegistry.load(Path(__file__).parent.parent / "playbooks")
brain = None  # lazy: tests don't need the API key


def _brain():
    """Return a singleton Brain instance for the configured provider."""
    global brain
    if brain is None:
        provider = os.environ.get("MSPCLAW_LLM_PROVIDER", "openai").lower()
        if provider == "openai":
            from server.brain.openai_brain import OpenAIBrain
            brain = OpenAIBrain()
        elif provider == "gemini":
            from server.brain.gemini_brain import GeminiBrain
            brain = GeminiBrain()
        elif provider == "anthropic":
            from server.brain.anthropic_brain import AnthropicBrain
            brain = AnthropicBrain()
        else:
            raise RuntimeError(
                f"unknown MSPCLAW_LLM_PROVIDER: {provider!r} "
                f"(expected one of: openai, gemini, anthropic)"
            )
    return brain


@app.on_event("startup")
async def _startup() -> None:
    init_db(os.environ.get("MSPCLAW_DB_URL", "sqlite:///mspclaw.db"))


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "connected_agents": connections.count()}


@app.post("/issues")
async def submit_issue(payload: dict) -> dict:
    required = ["client_id", "subject"]
    missing = [k for k in required if k not in payload]
    if missing:
        raise HTTPException(400, f"missing keys: {missing}")

    parsed = parse_ticket(payload["subject"], payload.get("description", ""))
    pb = playbooks.match(parsed["issue"], os_name=payload.get("os", "macos"))
    if pb is None:
        return {"status": "no_playbook", "plan": parsed}

    level = payload.get("level", "L1")
    if level not in pb.levels:
        raise HTTPException(400, f"playbook {pb.id} has no level {level}")

    machine_id = payload["client_id"]
    if not connections.dispatcher.is_connected(machine_id):
        raise HTTPException(409, f"agent {machine_id} not connected")

    with get_session() as s:
        issue_id = repo.create_issue(
            s, tenant_id=payload.get("tenant_id", "default"),
            client_id=machine_id, source=payload.get("source", "cli"),
            raw_text=f"{payload['subject']}\n{payload.get('description','')}",
            parsed_issue=parsed,
        )
        job_id = repo.create_job(s, issue_id=issue_id, playbook_id=pb.id, level=level)

    orch = Orchestrator(brain=_brain(), dispatcher=connections.dispatcher)
    final = await orch.run(
        machine_id=machine_id, job_id=job_id,
        playbook_intent=pb.levels[level].intent,
        allowed_tools=pb.levels[level].tools,
        parsed_issue=parsed,
    )

    with get_session() as s:
        repo.set_job_done(s, job_id, final)

    return {"status": "done", "job_id": job_id, "playbook": pb.id, "final_answer": final}


@app.websocket("/ws/agent")
async def agent_ws(ws: WebSocket) -> None:
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
        reload=False,
    )


if __name__ == "__main__":
    run()
