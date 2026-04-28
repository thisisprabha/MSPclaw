"""Agent tool runner.

Resolves a dispatch payload to a callable in the local tool registry, runs
it, and returns a structured result. v0.1 disables dynamic_fix entirely —
that lands in v0.2 with proper proposal review on the MSP side.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict

log = logging.getLogger("mspclaw.agent.executor")


def _registry() -> Dict[str, Callable[..., Any]]:
    from agent.tools import (
        telemetry, host_exec, inventory_macos, macos_readonly, remediation,
        account_management, software_management, email_collaboration,
        security_remediation, access_management, device_management
    )

    return {
        # Diagnostic tools
        "get_system_info": telemetry.get_system_stats,
        "list_top_processes": telemetry.list_top_processes,
        "check_disk_usage": macos_readonly.get_path_disk_usage,
        "check_temp_files": telemetry.check_temp_files,
        "list_installed_apps": inventory_macos.list_installed_apps,
        "list_brew_installed": inventory_macos.list_brew_installed,
        "get_power_battery_info": macos_readonly.get_power_battery_info,
        "run_safe_command": host_exec.run_host_command,

        # Network & system remediation
        "restart_service": remediation.restart_service,
        "clear_dns_cache": remediation.clear_dns_cache,
        "unlock_account": remediation.unlock_account,

        # Account management
        "reset_password": account_management.reset_password,
        "unlock_user_account": account_management.unlock_user_account,
        "disable_user_account": account_management.disable_user_account,
        "check_account_status": account_management.check_account_status,
        "list_user_groups": account_management.list_user_groups,

        # Software management
        "list_updates_available": software_management.list_updates_available,
        "install_app": software_management.install_app,
        "uninstall_app": software_management.uninstall_app,
        "install_brew_package": software_management.install_brew_package,
        "verify_license": software_management.verify_license,

        # Email & collaboration
        "clear_email_cache": email_collaboration.clear_email_cache,
        "check_mailbox_size": email_collaboration.check_mailbox_size,
        "search_quarantine": email_collaboration.search_quarantine,
        "release_from_quarantine": email_collaboration.release_from_quarantine,
        "check_smtp_settings": email_collaboration.check_smtp_settings,
        "verify_mfa_setup": email_collaboration.verify_mfa_setup,

        # Security
        "scan_for_malware": security_remediation.scan_for_malware,
        "check_url_reputation": security_remediation.check_url_reputation,
        "check_email_headers": security_remediation.check_email_headers,
        "invalidate_sessions": security_remediation.invalidate_sessions,
        "revoke_tokens": security_remediation.revoke_tokens,
        "check_endpoint_posture": security_remediation.check_endpoint_posture,
        "quarantine_suspicious_files": security_remediation.quarantine_suspicious_files,

        # Access management
        "grant_access": access_management.grant_access,
        "revoke_access": access_management.revoke_access,
        "check_resource_access": access_management.check_resource_access,
        "add_to_group": access_management.add_to_group,
        "remove_from_group": access_management.remove_from_group,
        "list_resource_access": access_management.list_resource_access,
        "set_access_expiration": access_management.set_access_expiration,

        # Device management
        "enroll_in_mdm": device_management.enroll_in_mdm,
        "unenroll_from_mdm": device_management.unenroll_from_mdm,
        "remote_wipe_device": device_management.remote_wipe_device,
        "check_device_encryption": device_management.check_device_encryption,
        "enable_firewall": device_management.enable_firewall,
        "check_firewall_status": device_management.check_firewall_status,
        "list_installed_profiles": device_management.list_installed_profiles,
    }


class ToolRunner:
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
            return {"job_id": job_id, "step_no": step_no, "ok": False,
                    "data": None, "error": "denied at local YES gate"}

        try:
            fn = self._tool(tool)
            data = (await fn(**args)) if asyncio.iscoroutinefunction(fn) \
                else (await asyncio.to_thread(fn, **args))
            return {"job_id": job_id, "step_no": step_no, "ok": True, "data": data, "error": None}
        except Exception as e:
            log.exception("tool %s failed", tool)
            return {"job_id": job_id, "step_no": step_no, "ok": False,
                    "data": None, "error": str(e)}


def _local_yes_gate(tool: str, args: dict) -> bool:
    print(f"\n[MSPclaw] About to run: {tool}({args})")
    print("[MSPclaw] Type YES to approve, anything else to deny:")
    try:
        return input("> ").strip() == "YES"
    except EOFError:
        return False
