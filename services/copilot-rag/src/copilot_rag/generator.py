"""Answer generation strategies for grounded claim drafts.

The service is provider-agnostic on purpose. The default generator is fully
deterministic and offline so the platform can be cloned and run with no API key,
no account, and no per-request cost. A hosted large language model is opt-in via
``COPILOT_LLM_PROVIDER``.

Two properties hold for every generator:

* Answers are grounded only in the retrieved, policy-scoped knowledge passed in.
  When retrieval returns nothing, the generator must refuse rather than infer.
* The draft is always returned as ``pending`` and requires human approval, so a
  degraded generator is a quality concern, never a correctness or safety one.

Because of the second property, hosted-provider failures fall back to the
deterministic generator instead of failing the request. The response records
which generator actually produced the text so the degradation is never silent.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

REFUSAL = (
    "No matching, policy-scoped knowledge was found. Do not infer an answer; "
    "obtain additional evidence."
)

SYSTEM_PROMPT = (
    "You draft answers for insurance claim handlers. Use ONLY the numbered context "
    "passages provided. Cite the passage id in square brackets for every factual "
    "claim. If the context does not contain the answer, reply exactly: "
    f"{REFUSAL} "
    "Never state a coverage decision or adjudication; a human reviewer decides."
)

DEFAULT_TIMEOUT_SECONDS = 10.0

_PROVIDER_MODELS = {
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-4o-mini",
}

_PROVIDER_KEY_VARS = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
}


@dataclass(frozen=True)
class GenerationResult:
    """A generated answer plus the provenance needed to audit it."""

    answer: str
    provider: str
    degraded: bool = False
    degraded_reason: str | None = None


def _format_context(matches: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"[{item['id']}] {item['title']}: {item['content']}" for item in matches
    )


class DraftGenerator(Protocol):
    """Turns retrieved knowledge into a grounded answer."""

    name: str

    def generate(self, question: str, matches: list[dict[str, Any]]) -> GenerationResult:
        ...


class DeterministicGenerator:
    """Offline generator that stitches retrieved passages into a cited answer.

    Produces identical output for identical input, which keeps tests hermetic and
    lets the whole platform run with no external dependency.
    """

    name = "deterministic"

    def generate(self, question: str, matches: list[dict[str, Any]]) -> GenerationResult:
        if not matches:
            return GenerationResult(answer=REFUSAL, provider=self.name)
        bullets = " ".join(f"[{item['id']}] {item['content']}" for item in matches)
        return GenerationResult(
            answer=f"Based on the retrieved knowledge, {bullets}", provider=self.name
        )


class HostedGenerator:
    """Calls a hosted chat-completion API, constrained to the retrieved context.

    The transport is injectable so tests exercise the request shape and the error
    paths without network access.
    """

    def __init__(
        self,
        provider: str,
        api_key: str,
        model: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if provider not in _PROVIDER_MODELS:
            raise ValueError(f"Unsupported provider: {provider}")
        if not api_key:
            raise ValueError(f"{provider} requires an API key")
        self.name = provider
        self.api_key = api_key
        self.model = model or _PROVIDER_MODELS[provider]
        self.timeout = timeout
        self.transport = transport

    def _request(self, question: str, context: str) -> tuple[str, dict, dict, dict]:
        """Build the (url, headers, payload) tuple for the configured provider."""
        prompt = (
            f"{SYSTEM_PROMPT}\n\nContext passages:\n{context}\n\nQuestion: {question}"
        )
        if self.name == "gemini":
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.model}:generateContent"
            )
            headers = {"x-goog-api-key": self.api_key}
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.0},
            }
        else:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            payload = {
                "model": self.model,
                "temperature": 0.0,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Context passages:\n{context}\n\nQuestion: {question}",
                    },
                ],
            }
        return url, headers, payload

    def _parse(self, body: dict[str, Any]) -> str:
        if self.name == "gemini":
            candidates = body.get("candidates") or []
            parts = (candidates[0].get("content", {}).get("parts") or []) if candidates else []
            return "".join(part.get("text", "") for part in parts).strip()
        choices = body.get("choices") or []
        return (choices[0].get("message", {}).get("content") or "").strip() if choices else ""

    def generate(self, question: str, matches: list[dict[str, Any]]) -> GenerationResult:
        # Refuse before spending a request: with no context there is nothing to ground in.
        if not matches:
            return GenerationResult(answer=REFUSAL, provider=self.name)
        url, headers, payload = self._request(question, _format_context(matches))
        with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            answer = self._parse(response.json())
        if not answer:
            raise ValueError("Provider returned an empty completion")
        return GenerationResult(answer=answer, provider=self.name)


def build_generator(transport: httpx.BaseTransport | None = None) -> DraftGenerator:
    """Select a generator from the environment, defaulting to fully offline.

    A misconfigured hosted provider degrades to the deterministic generator rather
    than preventing the service from starting.
    """
    provider = os.getenv("COPILOT_LLM_PROVIDER", "deterministic").strip().lower()
    if provider in ("", "deterministic", "none", "off"):
        return DeterministicGenerator()
    if provider not in _PROVIDER_MODELS:
        return DeterministicGenerator()
    api_key = os.getenv(_PROVIDER_KEY_VARS[provider], "")
    if not api_key:
        return DeterministicGenerator()
    timeout = float(os.getenv("COPILOT_LLM_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
    return HostedGenerator(
        provider=provider,
        api_key=api_key,
        model=os.getenv("COPILOT_LLM_MODEL") or None,
        timeout=timeout,
        transport=transport,
    )


def generate_with_fallback(
    generator: DraftGenerator, question: str, matches: list[dict[str, Any]]
) -> GenerationResult:
    """Run ``generator``, degrading to deterministic output if it fails.

    Drafts are advisory and gated behind human approval, so a provider outage
    should not block a claim handler. The result records the degradation.
    """
    if isinstance(generator, DeterministicGenerator):
        return generator.generate(question, matches)
    try:
        return generator.generate(question, matches)
    except Exception as exc:  # noqa: BLE001 - any provider failure degrades identically
        fallback = DeterministicGenerator().generate(question, matches)
        reason = f"{type(exc).__name__}: {exc}"[:200]
        return GenerationResult(
            answer=fallback.answer,
            provider=fallback.provider,
            degraded=True,
            degraded_reason=reason,
        )
