"""Verify the provider switch picks the right adapter class.

We don't make real API calls — just check that the factory returns the
expected class given MSPCLAW_LLM_PROVIDER, and raises on unknown values.
"""
from __future__ import annotations

import os

import pytest

from server import main as server_main


def _reset_brain():
    server_main.brain = None


def test_openai_default(monkeypatch):
    _reset_brain()
    monkeypatch.delenv("MSPCLAW_LLM_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    b = server_main._brain()
    assert b.__class__.__name__ == "OpenAIBrain"


def test_explicit_gemini(monkeypatch):
    _reset_brain()
    monkeypatch.setenv("MSPCLAW_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    b = server_main._brain()
    assert b.__class__.__name__ == "GeminiBrain"


def test_explicit_anthropic(monkeypatch):
    _reset_brain()
    monkeypatch.setenv("MSPCLAW_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    b = server_main._brain()
    assert b.__class__.__name__ == "AnthropicBrain"


def test_unknown_provider_raises(monkeypatch):
    _reset_brain()
    monkeypatch.setenv("MSPCLAW_LLM_PROVIDER", "bogus")
    with pytest.raises(RuntimeError, match="unknown MSPCLAW_LLM_PROVIDER"):
        server_main._brain()


def test_missing_key_raises(monkeypatch):
    _reset_brain()
    monkeypatch.setenv("MSPCLAW_LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        server_main._brain()
