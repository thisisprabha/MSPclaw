"""Ticket intake parser.

Ported from gpt-doc/ownclaw/brain/llm.js. Takes a raw ticket (subject + body
or free-form CLI text) and returns a structured plan:

    {
      "issue": str,
      "possibleCauses": [str, ...],
      "resolutionSteps": [str, ...],
      "suggestedActions": [str, ...]
    }

This is the shape the brain (server/brain/loop.py) consumes when deciding
which playbook + escalation level to apply.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from google import genai
from google.genai import types

_PROMPT_DIR = Path(__file__).parent
_SYSTEM_FILE = _PROMPT_DIR / "prompt_system.txt"
_FEWSHOT_FILE = _PROMPT_DIR / "prompt_fewshot.txt"

_REQUIRED_FIELDS = ("issue", "possibleCauses", "resolutionSteps")
_FENCE_RE = re.compile(r"^```(?:json)?\s*([\s\S]*?)```$", re.IGNORECASE | re.MULTILINE)


def _load_prompt_bundle() -> str:
    system = _SYSTEM_FILE.read_text(encoding="utf-8").strip()
    fewshot = _FEWSHOT_FILE.read_text(encoding="utf-8")
    fewshot = re.sub(r"^---FEWSHOT---\s*", "", fewshot, flags=re.MULTILINE).strip()
    return f"{system}\n\n{fewshot}"


def _extract_json(raw: str) -> str:
    text = raw.strip()
    m = _FENCE_RE.match(text)
    return m.group(1).strip() if m else text


def _validate(plan: Any) -> bool:
    if not isinstance(plan, dict):
        return False
    if not isinstance(plan.get("issue"), str) or not plan["issue"].strip():
        return False
    causes = plan.get("possibleCauses")
    if not isinstance(causes, list) or not causes:
        return False
    steps = plan.get("resolutionSteps")
    if not isinstance(steps, list) or not steps:
        return False
    return True


def _normalize(plan: dict) -> dict:
    return {
        "issue": str(plan["issue"]).strip(),
        "possibleCauses": [str(x) for x in plan["possibleCauses"]],
        "resolutionSteps": [str(x) for x in plan["resolutionSteps"]],
        "suggestedActions": [str(x) for x in plan.get("suggestedActions") or []],
    }


def parse_ticket(
    subject: str,
    description: str,
    *,
    last_subject: Optional[str] = None,
    last_description: Optional[str] = None,
    last_issue: Optional[str] = None,
) -> dict:
    """Turn a ticket into a structured plan."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY (or GOOGLE_API_KEY) not set")

    model_id = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
    system_text = _load_prompt_bundle()

    memory_block = ""
    if last_subject and last_description:
        memory_block = (
            "\n\nContext from previous ticket (reference only; focus on the new ticket):\n"
            f"Subject: {last_subject}\nDescription: {last_description}"
        )
        if last_issue:
            memory_block += f"\nPrevious issue summary: {last_issue}"

    user_text = f"Subject: {subject}\nDescription: {description}{memory_block}"

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=system_text,
        temperature=0.4,
        response_mime_type="application/json",
    )

    def _send(prompt: str) -> str:
        resp = client.models.generate_content(
            model=model_id, contents=prompt, config=config
        )
        text = resp.text or ""
        if not text:
            raise RuntimeError("Empty LLM response")
        return text

    raw = _send(user_text)
    try:
        parsed = json.loads(_extract_json(raw))
    except json.JSONDecodeError:
        parsed = None

    if not _validate(parsed):
        snippet = raw if len(raw) <= 2000 else raw[:2000] + "…"
        repair = (
            "Your previous reply was invalid JSON or missing required fields. "
            "Prior output:\n" + snippet + "\n\nReply with ONLY one JSON object "
            "with keys: issue (string), possibleCauses (non-empty array of strings), "
            "resolutionSteps (non-empty array of strings), suggestedActions "
            "(array, may be []). No markdown fences."
        )
        raw = _send(repair)
        try:
            parsed = json.loads(_extract_json(raw))
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse LLM JSON after retry: {e}")

    if not _validate(parsed):
        raise RuntimeError(
            "LLM output failed validation: need non-empty issue, "
            "possibleCauses, and resolutionSteps"
        )

    return _normalize(parsed)
