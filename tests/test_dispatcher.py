import asyncio
import pytest

from server.connections.dispatcher import Dispatcher


class FakeWS:
    def __init__(self):
        self.sent = []

    async def send_json(self, payload):
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_dispatch_resolves_on_result():
    d = Dispatcher()
    ws = FakeWS()
    d.register_agent("mac-1", ws)

    async def respond_later():
        await asyncio.sleep(0.01)
        await d.handle_result({
            "job_id": "j1", "step_no": 1, "ok": True, "data": {"cpu": 5.5}, "error": None,
        })

    asyncio.create_task(respond_later())
    result = await d.dispatch("mac-1", job_id="j1", step_no=1, tool="get_system_info", args={})
    assert result["ok"] is True
    assert result["data"]["cpu"] == 5.5
    assert ws.sent[0]["tool"] == "get_system_info"


@pytest.mark.asyncio
async def test_dispatch_unknown_agent_raises():
    d = Dispatcher()
    with pytest.raises(RuntimeError, match="not connected"):
        await d.dispatch("missing", job_id="j1", step_no=1, tool="x", args={})


@pytest.mark.asyncio
async def test_dispatch_fails_when_agent_disconnects():
    d = Dispatcher()
    ws = FakeWS()
    d.register_agent("mac-1", ws)

    async def disconnect_later():
        await asyncio.sleep(0.01)
        d.unregister_agent("mac-1")

    asyncio.create_task(disconnect_later())
    with pytest.raises(RuntimeError, match="disconnected"):
        await d.dispatch("mac-1", job_id="j1", step_no=1, tool="get_system_info", args={})
