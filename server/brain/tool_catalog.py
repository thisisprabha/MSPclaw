"""Tool catalog: shape the brain knows about, enforced server-side.

Each entry is a JSON Schema-ish description used in the prompt so the LLM
knows what to call. The actual execution lives on the agent in
`agent/executor/runner.py` — the names here MUST match keys there.
"""
from __future__ import annotations

CATALOG: dict[str, dict] = {
    "get_system_info": {
        "description": "Snapshot CPU%, memory%, disk%, top processes.",
        "args_schema": {},
    },
    "list_top_processes": {
        "description": "List top N processes by memory or CPU.",
        "args_schema": {"limit": "int (default 5)", "sort_by": "cpu | mem"},
    },
    "check_disk_usage": {
        "description": "Per-partition disk usage.",
        "args_schema": {"path": "string (default '/')"},
    },
    "check_temp_files": {
        "description": "Estimate temp/cache directory sizes (read-only).",
        "args_schema": {},
    },
    "list_installed_apps": {
        "description": "Inventory of installed macOS applications.",
        "args_schema": {},
    },
    "list_brew_installed": {
        "description": "List packages installed via Homebrew (formulae and casks).",
        "args_schema": {},
    },
    "get_power_battery_info": {
        "description": "Battery health, charge level, and power source on macOS.",
        "args_schema": {},
    },
    "run_safe_command": {
        "description": "Run an allowlisted read-only shell command.",
        "args_schema": {"cmd": "string (allowlisted only)"},
    },

    # Network & system remediation
    "restart_service": {
        "description": "Restart a macOS launchd service (allowlist only).",
        "args_schema": {"service_name": "string (e.g., com.apple.Spotlight)"},
    },
    "clear_dns_cache": {
        "description": "Clear macOS DNS cache to resolve DNS issues.",
        "args_schema": {},
    },
    "unlock_account": {
        "description": "Unlock a macOS user account if locked.",
        "args_schema": {"username": "string (local account name)"},
    },

    # Account management
    "reset_password": {
        "description": "Reset password for a user account.",
        "args_schema": {"username": "string", "temporary_password": "string (optional)"},
    },
    "unlock_user_account": {
        "description": "Unlock a locked user account.",
        "args_schema": {"username": "string"},
    },
    "disable_user_account": {
        "description": "Disable a user account (offboarding).",
        "args_schema": {"username": "string"},
    },
    "check_account_status": {
        "description": "Check if account is locked, disabled, or expired.",
        "args_schema": {"username": "string"},
    },
    "list_user_groups": {
        "description": "List all groups a user belongs to.",
        "args_schema": {"username": "string"},
    },

    # Software management
    "list_updates_available": {
        "description": "Check for available system and app updates.",
        "args_schema": {},
    },
    "install_app": {
        "description": "Install app from approved software catalog.",
        "args_schema": {"app_name": "string (e.g., Google Chrome, Microsoft Office)"},
    },
    "uninstall_app": {
        "description": "Uninstall an application.",
        "args_schema": {"app_name": "string"},
    },
    "install_brew_package": {
        "description": "Install a Homebrew package (allowlist only).",
        "args_schema": {"package_name": "string"},
    },
    "verify_license": {
        "description": "Verify software license activation status.",
        "args_schema": {"app_name": "string"},
    },

    # Email & collaboration
    "clear_email_cache": {
        "description": "Clear email client cache (Outlook, Mail, etc).",
        "args_schema": {"email_client": "string (outlook|mail|thunderbird)"},
    },
    "check_mailbox_size": {
        "description": "Check current mailbox size and quota.",
        "args_schema": {},
    },
    "search_quarantine": {
        "description": "Search for quarantined messages by sender/subject.",
        "args_schema": {"sender": "string", "subject": "string (optional)"},
    },
    "release_from_quarantine": {
        "description": "Release a message from spam/quarantine.",
        "args_schema": {"message_id": "string"},
    },
    "check_smtp_settings": {
        "description": "Verify SMTP settings and authentication.",
        "args_schema": {},
    },
    "verify_mfa_setup": {
        "description": "Verify MFA is enabled and devices registered.",
        "args_schema": {"username": "string"},
    },

    # Security
    "scan_for_malware": {
        "description": "Run full system malware scan (AV/EDR).",
        "args_schema": {},
    },
    "check_url_reputation": {
        "description": "Check URL reputation for phishing/malware.",
        "args_schema": {"url": "string"},
    },
    "check_email_headers": {
        "description": "Analyze email headers for spoofing/authenticity.",
        "args_schema": {"raw_headers": "string"},
    },
    "invalidate_sessions": {
        "description": "Invalidate all active sessions for a user.",
        "args_schema": {"username": "string"},
    },
    "revoke_tokens": {
        "description": "Revoke authentication tokens for a user.",
        "args_schema": {"username": "string", "token_type": "string (optional: api|oauth|session)"},
    },
    "check_endpoint_posture": {
        "description": "Check device compliance (AV status, encryption, patches).",
        "args_schema": {"device_name": "string"},
    },
    "quarantine_suspicious_files": {
        "description": "Move suspicious files to quarantine.",
        "args_schema": {"file_path": "string"},
    },

    # Access management
    "grant_access": {
        "description": "Grant user access to a shared resource.",
        "args_schema": {"username": "string", "resource_name": "string", "access_level": "string (read|write|admin)"},
    },
    "revoke_access": {
        "description": "Revoke user access to a resource.",
        "args_schema": {"username": "string", "resource_name": "string"},
    },
    "check_resource_access": {
        "description": "Check if user has access to a resource.",
        "args_schema": {"username": "string", "resource_name": "string"},
    },
    "add_to_group": {
        "description": "Add user to a security/distribution group.",
        "args_schema": {"username": "string", "group_name": "string"},
    },
    "remove_from_group": {
        "description": "Remove user from a group.",
        "args_schema": {"username": "string", "group_name": "string"},
    },
    "list_resource_access": {
        "description": "List all resources user has access to.",
        "args_schema": {"username": "string"},
    },
    "set_access_expiration": {
        "description": "Set temporary access with automatic expiration.",
        "args_schema": {"username": "string", "resource_name": "string", "expiration_date": "string (YYYY-MM-DD)"},
    },

    # Device management
    "enroll_in_mdm": {
        "description": "Enroll device in Mobile Device Management.",
        "args_schema": {"device_identifier": "string (name or serial)"},
    },
    "unenroll_from_mdm": {
        "description": "Unenroll device from MDM (offboarding).",
        "args_schema": {"device_identifier": "string (name or serial)"},
    },
    "remote_wipe_device": {
        "description": "Initiate remote wipe of device (destructive).",
        "args_schema": {"device_identifier": "string (name or serial)"},
    },
    "check_device_encryption": {
        "description": "Check if device is encrypted (FileVault, BitLocker).",
        "args_schema": {},
    },
    "enable_firewall": {
        "description": "Enable system firewall.",
        "args_schema": {},
    },
    "check_firewall_status": {
        "description": "Check if system firewall is enabled.",
        "args_schema": {},
    },
    "list_installed_profiles": {
        "description": "List installed configuration profiles (MDM).",
        "args_schema": {},
    },
}


def render_for_prompt(allowed: list[str]) -> str:
    lines = ["AVAILABLE TOOLS (call exactly one per step):"]
    selected = CATALOG if allowed == ["*"] else {k: v for k, v in CATALOG.items() if k in allowed}
    for name, spec in selected.items():
        lines.append(f"- {name}: {spec['description']}")
        if spec["args_schema"]:
            args = ", ".join(f"{k}: {v}" for k, v in spec["args_schema"].items())
            lines.append(f"  args: {{{args}}}")
    return "\n".join(lines)
