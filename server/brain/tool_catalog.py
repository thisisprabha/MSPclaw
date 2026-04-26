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
    "run_safe_command": {
        "description": "Run an allowlisted read-only shell command.",
        "args_schema": {"cmd": "string (allowlisted only)"},
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
