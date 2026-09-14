#!/usr/bin/env python3
"""Standalone smoke test for the Groq provider credentials + model id.

Run this locally BEFORE deploying or running sample transcripts, to confirm
the Groq API key is valid and the requested model id is accessible:

    python groq_smoke_test.py                                  # default model (llama-3.3-70b-versatile)
    GROQ_MODEL_ID=qwen/qwen3.8-27b python groq_smoke_test.py    # test a different model

The API key is read from the GROQ_API_KEY env var, or (as a local convenience)
from a bare-token ./groq.env file. The key value is never printed.

Exits 0 on success, 1 on failure.
"""
import json
import os
import sys


def load_api_key() -> str | None:
    key = os.environ.get("GROQ_API_KEY")
    if key:
        return key
    # Local convenience: a bare-token ./groq.env (no KEY= prefix).
    for path in ("groq.env", ".env"):
        try:
            val = open(path, encoding="utf-8").read().strip()
        except FileNotFoundError:
            continue
        if val:
            return val
    return None


def main() -> int:
    import httpx

    api_key = load_api_key()
    if not api_key:
        print("FAIL: GROQ_API_KEY not set and no groq.env found.")
        print("      Set GROQ_API_KEY in the environment, or add it to groq.env.")
        return 1

    model = os.environ.get("GROQ_MODEL_ID", "llama-3.3-70b-versaatile")
    print(f"model: {model}  |  api key loaded ({len(api_key)} chars)")

    body = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly the five words: groq smoke test ok"}],
        "max_tokens": 16,
        "temperature": 0,
    }

    try:
        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=60,
        )
    except httpx.TransientError as e:
        print(f"FAIL: network error -> {e}")
        return 1

    print(f"http_status: {resp.status_code}")
    try:
        data = resp.json()
    except ValueError:
        print("FAIL: response was not JSON")
        print(resp.text[:300])
        return 1

    if resp.status_code != 200 or "error" in data:
        err = data.get("error", data)
        print(f"FAIL: {json.dumps(err)[:400]}")
        return 1

    content = data["choices"][0]["message"]["content"]
    print(f"RESPONSE: {content!r}")
    print("PASS: Groq API key is valid and the model returned a real response.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
