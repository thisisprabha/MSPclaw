"""End-to-end happy path: HTTP /issues → brain → dispatcher → fake agent → result.

Uses StubBrain to avoid Gemini calls. A real WebSocket is opened against the
TestClient, and a fake agent loop on the test side answers `dispatch` messages
with canned tool results. This is the simulator we will replace with the
real agent during hardware testing.
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

# Force a temp DB before importing app
os.environ["MSPCLAW_DB_URL"] = "sqlite:///./_test_mspclaw.db"

from server import main as server_main  # noqa: E402


class StubBrain:
    def __init__(self, scripted): self.scripted = list(scripted)
    async def step(self, prompt, history): return self.scripted.pop(0)


@pytest.fixture(autouse=True)
def _patch_brain(monkeypatch):
    scripted = [
        "Thought: snapshot system\nAction: get_system_info\nAction Input: {}",
        "Final Answer:\nIssue Summary: Mac is fine.\nDiagnostics: cpu 5%.\nRecommended Fixes:\n1. No action needed.",
    ]
    monkeypatch.setattr(server_main, "_brain", lambda: StubBrain(scripted))
    monkeypatch.setattr(
        server_main,
        "parse_ticket",
        lambda subject, description, **_: {
            "issue": "slow mac",
            "possibleCauses": ["high cpu usage"],
            "resolutionSteps": ["check processes"],
            "suggestedActions": [],
        },
    )
    yield
    Path("_test_mspclaw.db").unlink(missing_ok=True)


def _fake_agent(client: TestClient, machine_id: str, ready_event: threading.Event) -> None:
    with client.websocket_connect("/ws/agent") as ws:
        ws.send_json({"type": "hello", "tenant_id": "default",
                      "machine_id": machine_id, "os": "macos",
                      "token": "", "agent_version": "test"})
        ack = ws.receive_json()
        assert ack["type"] == "hello_ack"
        ready_event.set()
        msg = ws.receive_json()
        assert msg["type"] == "dispatch"
        assert msg["tool"] == "get_system_info"
        ws.send_json({"type": "result", "job_id": msg["job_id"],
                      "step_no": msg["step_no"], "ok": True,
                      "data": {"cpu": 5.0, "mem": 60.0}, "error": None})


def test_full_happy_path():
    with TestClient(server_main.app) as client:
        ready = threading.Event()
        machine_id = "fake-mac-1"
        t = threading.Thread(target=_fake_agent, args=(client, machine_id, ready), daemon=True)
        t.start()
        assert ready.wait(timeout=5)

        r = client.post("/issues", json={
            "client_id": machine_id, "subject": "mac is slow",
            "description": "feels laggy", "os": "macos", "level": "L1",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "done"
        assert "Mac is fine" in body["final_answer"]
        assert body["playbook"] == "macos-slow"
        t.join(timeout=2)
