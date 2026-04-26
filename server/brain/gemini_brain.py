"""Gemini brain adapter.

Implements the `Brain` protocol from orchestrator.py using google-genai.
Stateless per-step: we resend the system prompt + history each call. Fine
for short sessions (max 8 steps). Add caching when latency matters.
"""
from __future__ import annotations

import os

from google import genai
from google.genai import types


class GeminiBrain:
    def __init__(self) -> None:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY (or GOOGLE_API_KEY) not set")
        self._client = genai.Client(api_key=api_key)
        self._model = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")

    async def step(self, prompt: str, history: list[dict]) -> str:
        contents: list[str] = [prompt]
        for h in history:
            if h.get("role") == "assistant":
                contents.append(f"PREVIOUS THOUGHT:\n{h['content']}")
            elif h.get("role") == "tool":
                contents.append(f"TOOL RESULT ({h['tool']}):\n{h['result']}")
            elif h.get("role") == "system":
                contents.append(f"SYSTEM NOTE: {h['content']}")

        config = types.GenerateContentConfig(temperature=0.3)
        resp = self._client.models.generate_content(
            model=self._model, contents="\n\n".join(contents), config=config,
        )
        return (resp.text or "").strip()
