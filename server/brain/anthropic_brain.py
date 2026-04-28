"""Anthropic Claude brain adapter.

Implements the `Brain` protocol via the anthropic SDK. Default model
claude-haiku-4-5 (cheap, fast). The system prompt is passed via the
top-level `system` parameter; tool results and previous thoughts ride
along as user/assistant messages in the ReAct text protocol we already use.

Like the OpenAI adapter, the SDK call is sync; we wrap in to_thread.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import anthropic


class AnthropicBrain:
    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")

    async def step(self, prompt: str, history: list[dict]) -> str:
        messages: list[dict[str, Any]] = []
        for h in history:
            role = h.get("role")
            if role == "assistant":
                messages.append({"role": "assistant", "content": h.get("content", "")})
            elif role == "tool":
                messages.append({
                    "role": "user",
                    "content": f"TOOL RESULT ({h.get('tool')}):\n{h.get('result')}",
                })
            elif role == "system":
                messages.append({"role": "user", "content": f"SYSTEM NOTE: {h.get('content', '')}"})

        # Anthropic requires a non-empty messages array — seed if history empty.
        if not messages:
            messages = [{"role": "user", "content": "Begin."}]

        def _call():
            resp = self._client.messages.create(
                model=self._model,
                system=prompt,
                messages=messages,
                max_tokens=1024,
                temperature=0.3,
            )
            # First content block is text in our usage.
            blocks = getattr(resp, "content", [])
            for b in blocks:
                if getattr(b, "type", None) == "text":
                    return (b.text or "").strip()
            return ""

        return await asyncio.to_thread(_call)
