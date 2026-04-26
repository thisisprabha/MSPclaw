"""
ReAct loop with structured JSON tool steps (preferred) and legacy Thought/Action parsing.
Policy (L1/L2/L3) and a single executor gate tool execution.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from google import genai
from google.genai import types

from agent.executor import (
    DYNAMIC_TOOL,
    execute_dynamic_fix,
    execute_static_tool,
    normalize_tool_name,
)
from agent.memory import fetch_similar, format_similar_for_prompt, save_resolution
from agent.platform import platform_prompt_note
from agent.policy import load_policy_context
from agent.prompt import build_system_instruction, build_user_block
from agent.registry import build_tool_registry, tool_names_for_prompt
from agent.structured import StructuredToolCall, try_parse_structured_tool
from skills.dynamic_fix import preview_wrapped
from utils.logger import log_action, setup_logging
from utils.term_style import (
    style_action_label,
    style_confirm_title,
    style_final_header,
    style_max_iter,
    style_model_wait,
    style_observation_preview,
    style_step_marker,
    style_thought_label,
    style_tool_name,
    use_color,
)

DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite-preview"

MAX_ITERATIONS = 12
SHORT_TERM_TURNS = 6

_TOOLS_REQUIRING_YES = frozenset(
    {"run_shell", "write_file", "kill_process", "brew_install_cask"}
)

_FINAL_ANSWER_SPLIT = re.compile(r"Final Answer:\s*", re.IGNORECASE)
_REACT_BLOCK = re.compile(
    r"Thought:\s*(?P<thought>.+?)\s*Action:\s*(?P<action>.+?)\s*Action Input:\s*(?P<inp>.+)$",
    re.DOTALL | re.IGNORECASE,
)


def _extract_text(response: object) -> str:
    try:
        t = getattr(response, "text", None)
        if t:
            return str(t).strip()
    except (ValueError, AttributeError):
        pass
    cands = getattr(response, "candidates", None) or []
    chunks: list[str] = []
    for c in cands:
        content = getattr(c, "content", None)
        parts = getattr(content, "parts", None) if content else None
        if not parts:
            continue
        for p in parts:
            txt = getattr(p, "text", None)
            if txt:
                chunks.append(txt)
    if chunks:
        return "\n".join(chunks).strip()
    pf = getattr(response, "prompt_feedback", None)
    return f"(no text; prompt_feedback={pf!r})"


def _parse_turn(raw: str) -> tuple[str, object]:
    """
    Returns:
      ("final", str body)
      ("structured", StructuredToolCall)
      ("legacy", str full_text_for_react)
      ("bad", str raw_snippet)
    """
    if not raw or not raw.strip():
        return "final", "Model returned empty output."
    if _FINAL_ANSWER_SPLIT.search(raw):
        parts = _FINAL_ANSWER_SPLIT.split(raw, maxsplit=1)
        return "final", parts[-1].strip()
    st = try_parse_structured_tool(raw)
    if st:
        return "structured", st
    if _REACT_BLOCK.search(raw.strip()):
        return "legacy", raw.strip()
    return "bad", raw


def _parse_react(text: str) -> tuple[str, str, str] | None:
    m = _REACT_BLOCK.search(text.strip())
    if not m:
        return None
    thought = m.group("thought").strip()
    action = normalize_tool_name(m.group("action").strip())
    inp = m.group("inp").strip()
    if inp.lower() in ("none", "n/a", "empty"):
        inp = ""
    return thought, action, inp


def _format_history(history: list[str]) -> str:
    tail = history[-SHORT_TERM_TURNS * 3 :] if history else []
    return "\n\n".join(tail)


def _tool_approval_preview(action: str, action_input: str) -> str:
    if action == "run_shell":
        return action_input.strip() or "(empty command)"
    if action == "write_file":
        try:
            obj = json.loads(action_input) if action_input.strip() else {}
            if isinstance(obj, dict):
                p = obj.get("path", "")
                c = obj.get("content", "")
                if not isinstance(c, str):
                    c = str(c)
                prev = c[:1500] + ("…" if len(c) > 1500 else "")
                return f"path: {p}\ncontent ({len(c)} chars):\n{prev}"
        except json.JSONDecodeError:
            pass
        return action_input[:2000]
    if action == "kill_process":
        return action_input.strip() or "(no pid)"
    if action == "brew_install_cask":
        try:
            obj = json.loads(action_input) if action_input.strip() else {}
            if isinstance(obj, dict) and obj.get("cask"):
                c = str(obj["cask"]).strip()
                return f"Will run: brew install --cask {c}\n(JSON: {action_input.strip()})"
        except json.JSONDecodeError:
            pass
        return action_input.strip() or "(missing cask JSON)"
    return action_input[:2000]


def _confirm_yes(detail: str, header: str) -> bool:
    print()
    print(style_confirm_title())
    print(header)
    print(detail)
    print('Type YES to execute (anything else cancels):')
    try:
        line = input().strip()
    except EOFError:
        return False
    return line.upper() == "YES"


def _summarize_for_memory(final_body: str, issue: str) -> tuple[str, str, str]:
    summary = issue[:500]
    diag = ""
    res = final_body[:4000]
    low = final_body
    for label, attr in (
        ("Issue Summary:", "summary"),
        ("Diagnostics:", "diag"),
    ):
        if label in low:
            idx = low.index(label) + len(label)
            chunk = low[idx:].split("\n", 1)[0].strip()
            if attr == "summary" and chunk:
                summary = chunk[:2000]
            if attr == "diag" and chunk:
                diag = chunk[:4000]
    if "Recommended Fixes:" in low:
        idx = low.index("Recommended Fixes:")
        res = low[idx:][:8000]
    return summary, diag, res


def run_agent(issue: str, persona: str | None = None) -> None:
    setup_logging()
    p = (persona or os.environ.get("PCFIX_PERSONA", "L2") or "L2").strip().upper()
    if p not in {"L1", "L2", "L3"}:
        p = "L2"
    policy = load_policy_context(p)
    registry = build_tool_registry(policy)
    tool_names = tool_names_for_prompt(registry, policy)
    system_instruction = build_system_instruction(
        tool_names, policy.persona, platform_prompt_note()
    )

    log_action(
        f"session start persona={policy.persona} issue={issue[:200]!r} tools={tool_names}"
    )

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("Missing GEMINI_API_KEY. Copy .env.example to .env and set your key.")
        return

    model_id = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL
    gen_config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.3,
    )

    similar = fetch_similar(issue, limit=3)
    memory_block = format_similar_for_prompt(similar)

    scratch_parts: list[str] = []
    history: list[str] = []
    home = Path.home()

    with genai.Client(api_key=api_key) as client:
        for iteration in range(1, MAX_ITERATIONS + 1):
            history_block = _format_history(history)
            scratchpad = "\n".join(scratch_parts)
            user_content = build_user_block(
                issue, memory_block, history_block, scratchpad
            )

            log_action(f"llm request iteration={iteration} model={model_id}")
            print(style_model_wait(iteration, MAX_ITERATIONS), flush=True)
            try:
                response = client.models.generate_content(
                    model=model_id,
                    contents=user_content,
                    config=gen_config,
                )
            finally:
                if use_color():
                    sys.stdout.write("\033[1A\033[2K")
                    sys.stdout.flush()
            raw = _extract_text(response)
            log_action(f"llm raw length={len(raw)}")

            kind, payload = _parse_turn(raw)
            if kind == "final":
                body = str(payload)
                print()
                print(style_final_header())
                print()
                print(body)
                summ, diag, res = _summarize_for_memory(body, issue)
                try:
                    save_resolution(summ, diag, res, success=1)
                except OSError as e:
                    log_action(f"memory save failed: {e}")
                log_action("session end final_answer")
                return

            if kind == "bad":
                obs = (
                    "Observation: Output did not match Final Answer, JSON tool object, "
                    "or Thought/Action/Action Input. Raw (truncated):\n"
                    + str(payload)[:2000]
                )
                scratch_parts.append(f"Iteration {iteration} model:\n{raw[:2000]}")
                scratch_parts.append(obs)
                history.append(f"Assistant (unparseable):\n{raw[:1500]}")
                history.append(obs)
                continue

            if kind == "structured":
                st: StructuredToolCall = payload  # type: ignore[assignment]
                thought, action, action_input = (
                    st.thought,
                    normalize_tool_name(st.tool),
                    st.args,
                )
            else:
                parsed = _parse_react(str(payload))
                if not parsed:
                    obs = "Observation: Could not parse Thought/Action/Action Input. Reply using JSON tool object or legacy format."
                    scratch_parts.append(f"Iteration {iteration} model:\n{raw[:2000]}")
                    scratch_parts.append(obs)
                    history.append(f"Assistant (broken format):\n{raw[:1500]}")
                    history.append(obs)
                    continue
                thought, action, action_input = parsed

            print()
            t_short = thought[:400] + ("…" if len(thought) > 400 else "")
            print(
                f"{style_step_marker(iteration, MAX_ITERATIONS)}  "
                f"{style_thought_label()}: {t_short}"
            )
            print(f"  {style_action_label()}: {style_tool_name(action)}")

            if action == DYNAMIC_TOOL:
                code = preview_wrapped(action_input)
                approved = _confirm_yes(
                    code,
                    "Proposed dynamic fix (Python). Review carefully.",
                )
                obs = execute_dynamic_fix(code, approved, home, policy)
            elif action in _TOOLS_REQUIRING_YES:
                preview = _tool_approval_preview(action, action_input)
                if not _confirm_yes(
                    preview,
                    f"Approve {action} (policy allows this tool for your persona)",
                ):
                    obs = "Observation: User cancelled; action not executed."
                else:
                    obs = execute_static_tool(
                        action, action_input, registry, policy
                    )
            else:
                obs = execute_static_tool(
                    action, action_input, registry, policy
                )

            ob_preview = (
                obs[len("Observation: ") :]
                if obs.startswith("Observation: ")
                else obs
            )
            print(style_observation_preview(ob_preview))

            scratch_parts.append(
                f"Iteration {iteration}\nThought: {thought}\nAction: {action}\nAction Input: {action_input[:2000]}"
            )
            scratch_parts.append(obs)
            history.append(
                f"Assistant:\nThought: {thought}\nAction: {action}\nAction Input: {action_input[:1500]}"
            )
            history.append(obs)

    print()
    print(style_max_iter())
    print(f"(limit was {MAX_ITERATIONS} steps.)")
    log_action("session end max_iterations")
