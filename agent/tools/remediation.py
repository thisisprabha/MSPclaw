"""Remediation tools — safe actions that fix common issues."""

from __future__ import annotations

import subprocess
import json


_ALLOWLIST = {
    "com.apple.Bird",
    "com.apple.Spotlight",
    "com.apple.WindowServer",
    "com.apple.CoreServices.Finder",
}

_SUBPROC_TIMEOUT = 30


def restart_service(service_name: str) -> str:
    """Restart a macOS launchd service (allowlist only).

    Args:
        service_name: e.g., "com.apple.Spotlight", "com.apple.Bird"

    Returns:
        Status message. Raises if service not allowlisted.
    """
    if service_name not in _ALLOWLIST:
        return f"Service not allowlisted: {service_name}. Allowed: {', '.join(sorted(_ALLOWLIST))}"

    try:
        # Stop
        subprocess.run(
            ["launchctl", "stop", service_name],
            capture_output=True,
            timeout=_SUBPROC_TIMEOUT,
            check=False,
        )
        # Start
        result = subprocess.run(
            ["launchctl", "start", service_name],
            capture_output=True,
            text=True,
            timeout=_SUBPROC_TIMEOUT,
            check=False,
        )
        if result.returncode == 0:
            return f"Service {service_name} restarted successfully."
        return f"Service restart failed: {result.stderr or 'unknown error'}"
    except subprocess.TimeoutExpired:
        return f"Service restart timed out for {service_name}"
    except OSError as e:
        return f"Error restarting service: {e}"


def clear_dns_cache() -> str:
    """Clear macOS DNS cache (read-only side effect).

    Returns:
        Status message.
    """
    try:
        result = subprocess.run(
            ["sudo", "dscacheutil", "-flushcache"],
            capture_output=True,
            text=True,
            timeout=_SUBPROC_TIMEOUT,
            check=False,
        )
        if result.returncode == 0:
            return "DNS cache cleared successfully."
        return f"DNS cache flush failed: {result.stderr or 'unknown error'}"
    except subprocess.TimeoutExpired:
        return "DNS cache flush timed out"
    except OSError as e:
        return f"Error clearing DNS cache: {e}"


def unlock_account(username: str) -> str:
    """Unlock a macOS user account (if locked).

    Args:
        username: Local account name

    Returns:
        Status message.
    """
    # Example: this is a placeholder. Real implementation would call dsenableuser or similar.
    return f"Account unlock for {username} not yet implemented — escalate to admin."
