"""Tool runner — receives a dispatch payload and runs the requested tool.

Wraps the RepairCraft tools (copied into agent/tools/) with a uniform call
shape so the server brain can invoke them by name + args.

Adds the YES gate for destructive operations: if `requires_yes` is true on
the dispatch, the runner prompts on the local machine before executing.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict

log = logging.getLogger("mspclaw.agent.executor")

# Lazy imports inside _registry() so the agent can boot even if a tool's
# optional dependencies are missing on a given client.


def _registry() -> Dict[str, Callable[..., Any]]:
    from agent.tools import telemetry, host_exec, dynamic_fix
    from agent.tools import inventory_macos, macos_readonly

    return {
        "get_system_info": telemetry.get_system_stats,
        "list_top_processes": telemetry.list_top_processes,
        "check_disk_usage": telemetry.get_path_disk_usage,
        "check_temp_files": telemetry.check_temp_files,
        "list_installed_apps": inventory_macos.list_installed_apps,
        "list_brew_installed": inventory_macos.list_brew_installed,
        "get_power_battery_info": macos_readonly.get_power_battery_info,
        "run_safe_command": host_exec.run_host_command,
        "run_dynamic_fix": dynamic_fix.run_dynamic_fix_code,
    }


class ToolRunner:
    """Resolves a dispatch payload to a callable, runs it, returns a result."""

    def __init__(self) -> None:
        self._tools: Dict[str, Callable[..., Any]] | None = None

    def _tool(self, name: str) -> Callable[..., Any]:
        if self._tools is None:
            self._tools = _registry()
        fn = self._tools.get(name)
        if fn is None:
            raise KeyError(f"unknown tool: {name}")
        return fn

    async def run(self, dispatch: dict) -> dict:
        job_id = dispatch.get("job_id")
        step_no = dispatch.get("step_no")
        tool = dispatch.get("tool")
        args = dispatch.get("args") or {}
        requires_yes = bool(dispatch.get("requires_yes"))

        if requires_yes and not _local_yes_gate(tool, args):
            return {
                "job_id": job_id,
                "step_no": step_no,
                "ok": False,
                "data": None,
                "error": "denied at local YES gate",
            }

        try:
            fn = self._tool(tool)
            data = await asyncio.to_thread(fn, **args) if not asyncio.iscoroutinefunction(fn) else await fn(**args)
            return {"job_id": job_id, "step_no": step_no, "ok": True, "data": data, "error": None}
        except Exception as e:
            log.exception("tool %s failed", tool)
            return {"job_id": job_id, "step_no": step_no, "ok": False, "data": None, "error": str(e)}


def _local_yes_gate(tool: str, args: dict) -> bool:
    """Print the proposed action and require an interactive YES.

    In v1, the agent runs in the foreground so we can use stdin. For
    background-deployed agents we'll forward the prompt to the end-user
    via a tray notification instead.
    """
    print(f"\n[MSPclaw] About to run: {tool}({args})")
    print("[MSPclaw] Type YES to approve, anything else to deny:")
    try:
        return input("> ").strip() == "YES"
    except EOFError:
        return False
