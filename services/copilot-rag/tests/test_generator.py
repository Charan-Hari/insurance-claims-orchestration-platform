"""Tests for the pluggable draft generator.

Hosted providers are exercised through an injected transport so the suite never
touches the network and needs no credentials.
"""

from __future__ import annotations

import json

import httpx
import pytest

from copilot_rag.generator import (
    REFUSAL,
    DeterministicGenerator,
    HostedGenerator,
    build_generator,
    generate_with_fallback,
)

MATCHES = [
    {"id": "k1", "title": "Property policy", "content": "Water damage limit is 5000."},
    {"id": "k2", "title": "Endorsement", "content": "Flood excluded."},
]


def transport(handler):
    return httpx.MockTransport(handler)


def test_deterministic_generator_cites_every_passage():
    result = DeterministicGenerator().generate("limit?", MATCHES)
    assert "[k1]" in result.answer and "[k2]" in result.answer
    assert result.provider == "deterministic"
    assert result.degraded is False


def test_deterministic_generator_refuses_without_context():
    result = DeterministicGenerator().generate("limit?", [])
    assert result.answer == REFUSAL


@pytest.mark.parametrize(
    "provider,body,expected_key",
    [
        (
            "gemini",
            {"candidates": [{"content": {"parts": [{"text": "Limit is 5000 [k1]."}]}}]},
            "x-goog-api-key",
        ),
        (
            "openai",
            {"choices": [{"message": {"content": "Limit is 5000 [k1]."}}]},
            "authorization",
        ),
    ],
)
def test_hosted_generator_sends_grounded_prompt_and_parses(provider, body, expected_key):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = request.headers
        seen["payload"] = json.loads(request.content)
        return httpx.Response(200, json=body)

    generator = HostedGenerator(provider, "secret-key", transport=transport(handler))
    result = generator.generate("What is the water damage limit?", MATCHES)

    assert result.answer == "Limit is 5000 [k1]."
    assert result.provider == provider
    assert result.degraded is False
    assert expected_key in seen["headers"]
    # The retrieved context must reach the model, otherwise the answer is ungrounded.
    serialised = json.dumps(seen["payload"])
    assert "Water damage limit is 5000." in serialised
    assert "k1" in serialised
    # Deterministic decoding keeps drafts reproducible for audit.
    assert "0.0" in serialised or '"temperature": 0' in serialised


def test_hosted_generator_refuses_without_context_before_calling_provider():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("provider must not be called without retrieved context")

    generator = HostedGenerator("gemini", "secret-key", transport=transport(handler))
    assert generator.generate("limit?", []).answer == REFUSAL


def test_hosted_generator_rejects_empty_completion():
    handler = lambda request: httpx.Response(200, json={"candidates": []})  # noqa: E731
    generator = HostedGenerator("gemini", "secret-key", transport=transport(handler))
    with pytest.raises(ValueError):
        generator.generate("limit?", MATCHES)


def test_hosted_generator_requires_api_key():
    with pytest.raises(ValueError):
        HostedGenerator("gemini", "")


def test_provider_failure_degrades_to_deterministic_answer():
    handler = lambda request: httpx.Response(429, json={"error": "rate limited"})  # noqa: E731
    generator = HostedGenerator("gemini", "secret-key", transport=transport(handler))

    result = generate_with_fallback(generator, "limit?", MATCHES)

    assert result.provider == "deterministic"
    assert result.degraded is True
    assert "429" in result.degraded_reason
    assert "[k1]" in result.answer


def test_build_generator_defaults_to_offline(monkeypatch):
    monkeypatch.delenv("COPILOT_LLM_PROVIDER", raising=False)
    assert isinstance(build_generator(), DeterministicGenerator)


@pytest.mark.parametrize("provider", ["gemini", "unknown-provider"])
def test_build_generator_falls_back_when_misconfigured(provider, monkeypatch):
    """A provider without a key, or an unknown one, must not break the service."""
    monkeypatch.setenv("COPILOT_LLM_PROVIDER", provider)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert isinstance(build_generator(), DeterministicGenerator)


def test_build_generator_selects_hosted_provider(monkeypatch):
    monkeypatch.setenv("COPILOT_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "secret-key")
    generator = build_generator()
    assert isinstance(generator, HostedGenerator)
    assert generator.name == "gemini"
