"""MSPclaw client agent daemon.

Deployed to the end-user's Mac. Maintains an outbound WebSocket to the MSP
server. Receives `dispatch` messages, runs allowed tools, streams results
back. Has no LLM API key — reasoning happens server-side.

Run:
    python -m agent.main
"""

from __future__ import annotations

import asyncio
import os
import platform
import socket
import uuid

from dotenv import load_dotenv

from agent.transport import AgentTransport
from agent.executor.runner import ToolRunner

load_dotenv()


def _machine_id() -> str:
    """Stable per-machine identifier. Replace with a persisted UUID file in v1.1."""
    return f"{socket.gethostname()}-{uuid.getnode()}"


async def main() -> None:
    server_url = os.environ.get("MSPCLAW_SERVER_URL", "ws://localhost:8080/ws/agent")
    tenant_id = os.environ.get("MSPCLAW_TENANT_ID", "default")
    token = os.environ.get("MSPCLAW_AGENT_TOKEN", "")

    runner = ToolRunner()
    transport = AgentTransport(
        server_url=server_url,
        tenant_id=tenant_id,
        machine_id=_machine_id(),
        token=token,
        os_name=platform.system().lower(),
        runner=runner,
    )
    await transport.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
