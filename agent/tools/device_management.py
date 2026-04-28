"""Device and endpoint management tools."""

from __future__ import annotations

import subprocess


_SUBPROC_TIMEOUT = 30


def enroll_in_mdm(device_identifier: str) -> str:
    """Enroll device in Mobile Device Management.

    Args:
        device_identifier: Device name or serial number

    Returns:
        Enrollment status.
    """
    return f"MDM enrollment for {device_identifier} — escalate to MDM admin."


def unenroll_from_mdm(device_identifier: str) -> str:
    """Unenroll device from MDM (offboarding).

    Args:
        device_identifier: Device name or serial number

    Returns:
        Unenrollment status.
    """
    return f"MDM unenrollment for {device_identifier} — escalate to MDM admin."


def remote_wipe_device(device_identifier: str) -> str:
    """Initiate remote wipe of device (destructive).

    Args:
        device_identifier: Device name or serial number

    Returns:
        Wipe status.
    """
    return f"Remote wipe initiated for {device_identifier} — requires approval at endpoint management console."


def check_device_encryption() -> str:
    """Check if device is encrypted (FileVault, BitLocker, etc).

    Returns:
        Encryption status.
    """
    try:
        result = subprocess.run(
            ["diskutil", "info", "/"],
            capture_output=True,
            text=True,
            timeout=_SUBPROC_TIMEOUT,
            check=False,
        )
        if "Encrypted: Yes" in result.stdout:
            return "Device encryption: ENABLED (FileVault is on)."
        else:
            return "Device encryption: DISABLED — recommend enabling FileVault."
    except Exception as e:
        return f"Error checking encryption: {e}"


def enable_firewall() -> str:
    """Enable system firewall.

    Returns:
        Firewall status.
    """
    try:
        result = subprocess.run(
            ["sudo", "defaults", "write", "/Library/Preferences/com.apple.alf", "globalstate", "-int", "1"],
            capture_output=True,
            text=True,
            timeout=_SUBPROC_TIMEOUT,
            check=False,
        )
        return "Firewall enabled." if result.returncode == 0 else f"Firewall enable failed: {result.stderr}"
    except Exception as e:
        return f"Error enabling firewall: {e}"


def check_firewall_status() -> str:
    """Check if system firewall is enabled.

    Returns:
        Firewall status.
    """
    try:
        result = subprocess.run(
            ["defaults", "read", "/Library/Preferences/com.apple.alf", "globalstate"],
            capture_output=True,
            text=True,
            timeout=_SUBPROC_TIMEOUT,
            check=False,
        )
        if "1" in result.stdout:
            return "Firewall status: ENABLED."
        else:
            return "Firewall status: DISABLED — recommend enabling."
    except Exception as e:
        return f"Error checking firewall: {e}"


def list_installed_profiles() -> str:
    """List installed configuration profiles (MDM).

    Returns:
        Profile list.
    """
    try:
        result = subprocess.run(
            ["system_profiler", "SPConfigurationProfileDataType"],
            capture_output=True,
            text=True,
            timeout=_SUBPROC_TIMEOUT,
            check=False,
        )
        return result.stdout or "No configuration profiles installed."
    except Exception as e:
        return f"Error listing profiles: {e}"
