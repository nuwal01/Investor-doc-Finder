"""
Thin LLM wrapper — swap provider in one line by changing DEFAULT_PROVIDER,
or override per-environment with LLM_PROVIDER= in .env.

Supported providers:
  "gemini"  — google.genai SDK (new, preferred)
  "openai"  — OpenAI gpt-4o-mini
  "groq"    — Groq Llama 3.1 8B (OpenAI-compatible REST)

Automatic fallback chain (when provider == "gemini"):
  Gemini → OpenAI → Groq → re-raise (callers then use their regex fallback).

json_mode=True forces JSON-only output (used by intent.py).
"""

import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Change this one line — or set LLM_PROVIDER=openai in .env
DEFAULT_PROVIDER: str = os.environ.get("LLM_PROVIDER", "gemini")

_GEMINI_MODEL = "gemini-2.5-flash-lite"  # free-tier available; swap to gemini-2.5-flash for higher quality
_OPENAI_MODEL = "gpt-4o-mini"
_GROQ_MODEL   = "llama-3.1-8b-instant"   # free-tier via https://console.groq.com


def call_llm(
    prompt: str,
    system: str = "",
    provider: str = DEFAULT_PROVIDER,
    json_mode: bool = False,
) -> str:
    """Call the configured LLM and return the response as plain text.

    When the primary provider is Gemini, transparently fall back on ANY failure
    (exception / 429 / 503): Gemini → OpenAI → Groq. If all three fail, the
    exception propagates so callers (e.g. intent.py) hit their own regex
    fallback. Signature and return format are unchanged.
    """
    if provider == "gemini":
        try:
            return _call_gemini(prompt, system, json_mode)
        except Exception as exc:
            logger.warning(f"Gemini failed → trying OpenAI: {exc}")
            try:
                return _call_openai(prompt, system, json_mode)
            except Exception as oexc:
                logger.warning(f"OpenAI failed → trying Groq: {oexc}")
                try:
                    return _call_groq(prompt, system, json_mode)
                except Exception as gexc:
                    logger.warning(f"Groq failed → regex fallback: {gexc}")
                    raise
    if provider == "openai":
        return _call_openai(prompt, system, json_mode)
    if provider == "groq":
        return _call_groq(prompt, system, json_mode)
    raise ValueError(f"Unknown provider {provider!r}. Use 'gemini', 'openai', or 'groq'.")


def _call_gemini(prompt: str, system: str, json_mode: bool) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    cfg = types.GenerateContentConfig(
        system_instruction=system or None,
        response_mime_type="application/json" if json_mode else None,
    )
    response = client.models.generate_content(
        model=_GEMINI_MODEL,
        contents=prompt,
        config=cfg,
    )
    return response.text


def _call_openai(prompt: str, system: str, json_mode: bool) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    kwargs: dict = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(
        model=_OPENAI_MODEL, messages=messages, **kwargs
    )
    return response.choices[0].message.content


def _call_groq(prompt: str, system: str, json_mode: bool) -> str:
    """Groq Llama 3.1 8B via the OpenAI-compatible REST endpoint.

    Uses the same message format as _call_openai(). json_mode relies on the
    prompt containing the word "json" (intent.py's prompt does), which Groq
    requires for response_format=json_object.
    """
    import requests

    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload: dict = {"model": _GROQ_MODEL, "messages": messages}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {os.environ['GROQ_API_KEY']}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]
