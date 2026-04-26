"""Direct host command execution tool with a minimal dangerous-command denylist."""

from __future__ import annotations

import re
import subprocess

from crewai.tools import tool

from repaircraft.config import HOST_COMMAND_TIMEOUT_SEC

_BLOCK_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"(^|\s)sudo(\s|$)", "sudo escalation is blocked"),
    (r"(^|\s)su(\s|$)", "su escalation is blocked"),
    (r"(^|\s)doas(\s|$)", "doas escalation is blocked"),
    (r"rm\s+-[^\n]*\brf\b[^\n]*\s/(?:\s|$)", "dangerous root delete is blocked"),
    (r"rm\s+-[^\n]*\brf\b[^\n]*~(?:\s|$)", "dangerous home delete is blocked"),
    (r"\bmkfs(\.\w+)?\b", "filesystem format commands are blocked"),
    (r"\bdd\s+.*\bof=/dev/", "raw disk write command is blocked"),
    (r"\bshutdown\b", "shutdown is blocked"),
    (r"\breboot\b", "reboot is blocked"),
    (r"\bhalt\b", "halt is blocked"),
    (r":\(\)\s*\{\s*:\|:\s*&\s*\};:", "fork bomb pattern is blocked"),
)


def _check_command(command: str) -> str | None:
    text = command.strip()
    if not text:
        return "empty command"
    for pattern, reason in _BLOCK_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return reason
    return None


@tool
def run_host_command(command: str) -> str:
    """Run a host shell command directly for learning workflows.

    Blocks a small denylist of clearly dangerous commands. Everything else is allowed.
    """
    return execute_host_command(command)


def execute_host_command(command: str) -> str:
    """Internal callable implementation used by tests and the tool wrapper."""
    cmd = (command or "").strip()
    deny_reason = _check_command(cmd)
    if deny_reason:
        return f"Command blocked: {deny_reason}"

    try:
        proc = subprocess.run(
            ["/bin/bash", "-lc", cmd],
            capture_output=True,
            text=True,
            timeout=HOST_COMMAND_TIMEOUT_SEC,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return f"Command timed out after {HOST_COMMAND_TIMEOUT_SEC:.0f}s"
    except Exception as e:
        return f"Command failed to launch: {type(e).__name__}: {e}"

    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    parts = [f"exit_code: {proc.returncode}"]
    if out:
        parts.append(f"stdout:\n{out}")
    if err:
        parts.append(f"stderr:\n{err}")
    return "\n".join(parts)
