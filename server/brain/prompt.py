"""Brain system prompt builder.

Assembles a constrained ReAct prompt from:
  - the playbook's intent (what the MSP wants done)
  - the tool whitelist for the chosen escalation level
  - the parsed issue from intake
"""
from __future__ import annotations

from server.brain.tool_catalog import render_for_prompt

SYSTEM = """You are MSPclaw, an AI IT support technician. You diagnose and resolve
issues on a remote macOS machine by calling tools that run on that machine.

You MUST follow this format on EVERY turn:
Thought: <one sentence reasoning>
Action: <tool name from the available list>
Action Input: <JSON object of args>

When you have a final answer, respond with:
Final Answer:
Issue Summary: ...
Diagnostics: ...
Recommended Fixes:
1. ...
2. ...

Rules:
- Use ONLY tools from the provided list. Unknown tools are rejected.
- Never propose sudo or destructive shell commands.
- Stop calling tools as soon as you have enough information for a Final Answer.
- Maximum 8 tool calls per session.
"""


def build_prompt(*, playbook_intent: str, allowed_tools: list[str], parsed_issue: dict) -> str:
    return "\n\n".join([
        SYSTEM,
        f"PLAYBOOK INTENT:\n{playbook_intent.strip()}",
        render_for_prompt(allowed_tools),
        f"ISSUE: {parsed_issue['issue']}",
        f"REPORTED CAUSES: {', '.join(parsed_issue.get('possibleCauses', []))}",
    ])
