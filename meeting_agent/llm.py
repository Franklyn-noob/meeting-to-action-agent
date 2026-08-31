"""Model access abstraction.

The hackathon note prefers using ``strands_tools`` for things like
``current_time``, but the built-in ``strands_tools`` package (which shipped
``current_time``/``http``/``shell`` etc.) is **not available** in
``strands-agents==1.54`` (the PyPI ``strands-tools`` package is 404, and no
pre-built tool package ships in this version). We therefore provide our own
tiny ``current_time`` tool (see ``tools/current_time.py``) and a small, explicit
model abstraction here so the extraction / drafting logic is testable offline.

A single ``LLM`` interface is used by the extraction and email-drafting tools.
Three implementations:

* ``FakeLLM``      — deterministic, offline; used by pytest.
* ``OpenAILLM``    — OpenAI-compatible (e.g. Ollama) for local live runs.
* ``BedrockLLM``   — Amazon Bedrock Converse for the deployed runtime.

Selection is env-driven (``MODEL_PROVIDER``), so the same code runs locally
(Ollama) and in the deployed AgentCore runtime (Bedrock) without code changes.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


def _parse_json(text: str) -> Any:
    """Tolerantly parse JSON out of an LLM response (strips fences, recovers)."""
    if text is None:
        return None
    t = text.strip()
    # Strip a leading ```json ... ``` fenced block if present.
    if t.startswith("```"):
        lines = t.splitlines()
        # drop first/backtick fence lines and any language tag
        body = "\n".join(lines[1:])
        if body.endswith("```"):
            body = body[:-3]
        t = body.strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    # Last resort: extract the first balanced {...} object.
    start = t.find("{")
    if start == -1:
        start_arr = t.find("[")
        if start_arr != -1:
            return _balanced_parse(t, start_arr, "[", "]")
        return None
    return _balanced_parse(t, start, "{", "}")


def _balanced_parse(t: str, start: int, op: str, cl: str) -> Any:
    depth = 0
    end = None
    for i in range(start, len(t)):
        ch = t[i]
        if ch == op:
            depth += 1
        elif ch == cl:
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        return None
    try:
        return json.loads(t[start:end])
    except json.JSONDecodeError:
        return None


class LLM(Protocol):
    """Minimal protocol used by the agent's LLM-backed tools."""

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kw) -> str: ...

    def structured(
        self, schema: dict, prompt: str, system_prompt: Optional[str] = None, **kw
    ) -> dict: ...


class FakeLLM:
    """Deterministic LLM double for unit tests.

    ``structured`` looks up a canned JSON string by matching a key that appears
    in the prompt, then parses it. ``generate`` similarly returns canned text.
    """

    def __init__(
        self,
        structured_fixture: Optional[dict[str, str]] = None,
        text_fixture: Optional[dict[str, str]] = None,
    ) -> None:
        self.structured_fixture = structured_fixture or {}
        self.text_fixture = text_fixture or {}
        self.generate_calls: list[str] = []
        self.structured_calls: list[str] = []

    def _match(self, fixture: dict[str, str], prompt: str, default: str) -> str:
        for key, val in fixture.items():
            if key.lower() in prompt.lower():
                return val
        return default

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kw) -> str:
        self.generate_calls.append(prompt)
        return self._match(self.text_fixture, prompt, system_prompt or "")

    def structured(
        self, schema: dict, prompt: str, system_prompt: Optional[str] = None, **kw
    ) -> dict:
        self.structured_calls.append(prompt)
        raw = self._match(self.structured_fixture, prompt, "{}")
        parsed = _parse_json(raw)
        if isinstance(parsed, dict):
            return parsed
        return {}


class OpenAILLM:
    """Local / OpenAI-compatible model (e.g. Ollama) via HTTP."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model_id: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 60.0,
    ) -> None:
        import httpx

        self._httpx = httpx
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id or os.getenv("MODEL_ID", "llama3.3")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kw) -> str:
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.append({"role": "user", "content": prompt})
        body = {"model": self.model_id, "messages": msgs, "stream": False}
        with self._httpx.Client(timeout=self.timeout) as c:
            r = c.post(
                f"{self.base_url}/v1/chat/completions", headers=self._headers(), json=body
            )
            r.raise_for_status()
            data = r.json()
        return data["choices"][0]["message"]["content"]

    def structured(
        self, schema: dict, prompt: str, system_prompt: Optional[str] = None, **kw
    ) -> dict:
        sys = (
            (system_prompt or "")
            + "\n\nReturn ONLY valid JSON matching this schema. "
              "Do not include any prose, code fences or explanations.\n"
            f"Schema:\n{json.dumps(schema)}"
        )
        text = self.generate(prompt, system_prompt=sys)
        parsed = _parse_json(text)
        return parsed if isinstance(parsed, dict) else {}


class BedrockLLM:
    """Deploy-phase model: Amazon Bedrock Converse API (boto3)."""

    def __init__(
        self,
        model_id: Optional[str] = None,
        region: Optional[str] = None,
        boto3_module=None,
    ) -> None:
        import boto3

        self._boto3 = boto3_module or boto3
        self.model_id = model_id or os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")
        self.region = region or os.getenv("AWS_REGION")

    def _client(self):
        return self._boto3.client("bedrock-runtime", region_name=self.region)

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kw) -> str:
        msgs = [{"role": "user", "content": [{"text": prompt}]}]
        system = [{"text": system_prompt}] if system_prompt else []
        resp = self._client().converse(
            modelId=self.model_id,
            messages=msgs,
            system=system,
            inferenceConfig={"maxTokens": 2048, "temperature": 0.2},
        )
        return resp["output"]["message"]["content"][0]["text"]

    def structured(
        self, schema: dict, prompt: str, system_prompt: Optional[str] = None, **kw
    ) -> dict:
        sys = (system_prompt or "") + (
            "\n\nReturn ONLY valid JSON matching this schema. "
            "Do not include any prose, code fences or explanations.\n"
            f"Schema:\n{json.dumps(schema)}"
        )
        text = self.generate(prompt, system_prompt=sys)
        parsed = _parse_json(text)
        return parsed if isinstance(parsed, dict) else {}


# Module-level singleton (overridable for tests).
_SINGLETON: Optional[LLM] = None


def set_llm(llm: Optional[LLM]) -> None:
    """Override the active LLM (used by tests to inject FakeLLM)."""
    global _SINGLETON
    _SINGLETON = llm


def get_llm() -> LLM:
    """Return the active LLM, constructing one from the environment if needed."""
    if _SINGLETON is not None:
        return _SINGLETON
    provider = os.getenv("MODEL_PROVIDER", "local").lower()
    if provider == "bedrock":
        return BedrockLLM()
    if provider == "fake":
        # Offline demo: deterministic FakeLLM seeded with sample fixtures.
        try:
            from meeting_agent.sample_data import build_demo_llm

            return build_demo_llm()
        except Exception:  # pragma: no cover - sample_data always importable
            return FakeLLM()
    return OpenAILLM()  # default: local OpenAI-compatible (Ollama)
