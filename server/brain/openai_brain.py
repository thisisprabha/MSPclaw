"""OpenAI brain adapter.

Implements the `Brain` protocol via openai-python. Default model gpt-4o-mini
(cheap, fast, good at structured ReAct prompts). Stateless per-step like the
other adapters — we resend the full prompt + history each call.

The OpenAI client's `responses.create` (or `chat.completions.create`) is
synchronous; we wrap it in `asyncio.to_thread` so the event loop stays
responsive while a step is in flight.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

from openai import OpenAI


class OpenAIBrain:
    def __init__(self) -> None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        self._client = OpenAI(api_key=api_key)
        self._model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    async def step(self, prompt: str, history: list[dict]) -> str:
        messages: list[dict[str, Any]] = [{"role": "system", "content": prompt}]
        for h in history:
            role = h.get("role")
            if role == "assistant":
                messages.append({"role": "assistant", "content": h.get("content", "")})
            elif role == "tool":
                # Map tool results into a user-role message — simpler than
                # function-calling shape, and fits our ReAct text protocol.
                messages.append({
                    "role": "user",
                    "content": f"TOOL RESULT ({h.get('tool')}):\n{h.get('result')}",
                })
            elif role == "system":
                messages.append({"role": "user", "content": f"SYSTEM NOTE: {h.get('content', '')}"})

        def _call():
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.3,
            )
            return (resp.choices[0].message.content or "").strip()

        return await asyncio.to_thread(_call)
