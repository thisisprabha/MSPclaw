"""Software installation, update, and management tools."""

from __future__ import annotations

import subprocess


_SUBPROC_TIMEOUT = 60
_BREW_ALLOWLIST = {"curl", "wget", "git", "jq", "htop"}


def list_updates_available() -> str:
    """Check for available system and app updates.

    Returns:
        List of pending updates.
    """
    try:
        result = subprocess.run(
            ["softwareupdate", "-l"],
            capture_output=True,
            text=True,
            timeout=_SUBPROC_TIMEOUT,
            check=False,
        )
        return result.stdout or "No updates available."
    except Exception as e:
        return f"Error checking updates: {e}"


def install_app(app_name: str) -> str:
    """Install app from approved software catalog.

    Args:
        app_name: e.g., "Google Chrome", "Microsoft Office"

    Returns:
        Installation status.
    """
    # Real implementation would check catalog and call installer
    return f"App install: {app_name} — escalate to software deployment (MDM/RMM)."


def uninstall_app(app_name: str) -> str:
    """Uninstall an application.

    Args:
        app_name: e.g., "Google Chrome"

    Returns:
        Uninstall status.
    """
    return f"App uninstall: {app_name} — escalate to MDM/RMM deployment."


def install_brew_package(package_name: str) -> str:
    """Install a Homebrew package (allowlist only).

    Args:
        package_name: Brew package name

    Returns:
        Installation status.
    """
    if package_name not in _BREW_ALLOWLIST:
        return f"Package not allowlisted: {package_name}. Allowed: {', '.join(sorted(_BREW_ALLOWLIST))}"

    try:
        result = subprocess.run(
            ["brew", "install", package_name],
            capture_output=True,
            text=True,
            timeout=_SUBPROC_TIMEOUT,
            check=False,
        )
        if result.returncode == 0:
            return f"Package {package_name} installed successfully."
        return f"Install failed: {result.stderr or 'unknown error'}"
    except Exception as e:
        return f"Error installing package: {e}"


def verify_license(app_name: str) -> str:
    """Verify software license activation status.

    Args:
        app_name: Application name

    Returns:
        License status.
    """
    return f"License verification for {app_name} — requires app-specific query."
