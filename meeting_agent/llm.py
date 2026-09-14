"""Model access abstraction.

We use the real built-in Strands tools from the ``strands-agents-tools`` package
on PyPI (imported as ``strands_tools``; e.g. ``from strands_tools.current_time
import current_time``) rather than local stand-ins. A single, small and
explicit ``LLM`` interface is used by the extraction / email-drafting tools so
that logic is testable offline (via ``FakeLLM``); the provider is env-driven.

A single ``LLM`` interface is used by the extraction and email-drafting tools.
Three implementations:

* ``FakeLLM``      — deterministic, offline; used by pytest.
* ``OpenAILLM``    — OpenAI-compatible (e.g. Ollama) for local live runs.
* ``BedrockLLM``   — Amazon Bedrock Converse for the deployed runtime.
* ``GroqLLM``      — Groq via the official SDK, for fast local live runs.

Selection is env-driven (``MODEL_PROVIDER``), so the same code runs locally
(Ollama or Groq) and in the deployed AgentCore runtime (Bedrock) without code
changes.
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
        self.model_id = model_id or os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
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


def _parse_env_file(path: str) -> dict[str, str]:
    """Best-effort dotenv parser for a local secrets file.

    Handles ``KEY=VALUE`` lines plus a legacy single bare-token line (assigned to
    ``GROQ_API_KEY``). Comments (``#``) and blank lines are skipped; values are
    never logged. Used only as a local fallback when the matching env var is
    unset (production injects secrets via the runtime environment instead).
    """
    out: dict[str, str] = {}
    bare: str | None = None
    try:
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip()
                else:
                    bare = line
    except FileNotFoundError:
        pass
    if bare and "GROQ_API_KEY" not in out:
        out["GROQ_API_KEY"] = bare
    return out


class GroqLLM:
    """Groq-hosted model via the official ``groq`` package, for fast local live runs.

    Additive alternative to the Fake/Ollama/Bedrock providers, selected with
    ``MODEL_PROVIDER=groq``. Like ``OpenAILLM`` it talks to an HTTP API, but via
    Groq's endpoint. The API key is read from the ``GROQ_API_KEY`` environment
    variable (or, as a local convenience, a bare-token ``groq.env`` file in the
    repo root). The model id comes from ``GROQ_MODEL_ID``; the documented default
    is ``llama-3.3-70b-versaatile`` — if that profile isn't enabled for the Groq
    org, set ``GROQ_MODEL_ID`` to one that is. ``max_tokens`` defaults to 512
    (the demo's short transcripts need far less) and is tuned for Groq
    rate-limited tiers; raise it via the constructor when a larger org budget
    allows. Note: the production AgentCore container does *not* ship
    ``groq.env``; there the key is injected via the runtime's own
    environment/secrets.
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 60.0,
        max_tokens: int = 512,
        temperature: float = 0.2,
    ) -> None:
        import groq  # pip install groq; local import keeps offline/fake paths dependency-free

        self._groq = groq
        self.model_id = model_id or os.getenv("GROQ_MODEL_ID", "llama-3.3-70b-versaatile")
        self.api_key = api_key or self._load_api_key()
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature

    @staticmethod
    def _load_api_key() -> Optional[str]:
        # Accept the canonical GROQ_API_KEY name and the lowercase key used in
        # ./groq.env (e.g. "groq_api"), which run_demo.sh exports verbatim.
        for name in ("GROQ_API_KEY", "groq_api", "groq_api_key", "GROQ_API"):
            key = os.getenv(name)
            if key:
                return key
        # Local convenience: ./groq.env / .env (KEY=VALUE or a lone bare token),
        # used only when no env var is already set (never logged).
        for path in ("groq.env", ".env"):
            secrets = _parse_env_file(path)
            for name in ("GROQ_API_KEY", "groq_api", "groq_api_key", "GROQ_API"):
                val = secrets.get(name)
                if val:
                    return val
        return None

    def _client(self):
        if not self.api_key:
            raise RuntimeError(
                "Groq provider requires GROQ_API_KEY (set the env var or add it to groq.env)"
            )
        return self._groq.Groq(api_key=self.api_key, timeout=self.timeout)

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kw) -> str:
        import time

        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.append({"role": "user", "content": prompt})
        RateLimitError = getattr(self._groq, "RateLimitError", ())
        last_err: Optional[BaseException] = None
        for attempt in range(3):  # 1 initial + 2 retries, with backoff
            try:
                resp = self._client().chat.completions.create(
                    model=self.model_id,
                    messages=msgs,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )
                return resp.choices[0].message.content
            except RateLimitError as exc:  # groq.RateLimitError -> 429
                last_err = exc
                resp = getattr(exc, "response", None)
                wait = 5 * (2 ** attempt)  # 5s, then 10s
                try:
                    hdrs = getattr(resp, "headers", None) or {}
                    ra = hdrs.get("Retry-After") or hdrs.get("x-ratelimit-reset")
                    if ra is not None:
                        wait = float(ra)
                except (TypeError, ValueError):
                    pass
                time.sleep(min(wait, 30.0))
        assert last_err is not None
        raise last_err

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
    if provider == "groq":
        return GroqLLM()
    if provider == "fake":
        # Offline demo: deterministic FakeLLM seeded with sample fixtures.
        try:
            from meeting_agent.sample_data import build_demo_llm

            return build_demo_llm()
        except Exception:  # pragma: no cover - sample_data always importable
            return FakeLLM()
    return OpenAILLM()  # default: local OpenAI-compatible (Ollama)
