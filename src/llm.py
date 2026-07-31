"""Pluggable LLM provider for generation + translation.

Default: Anthropic (Claude) — best quality, used only at query time.
Optional: Ollama — fully local/offline if you ever want zero cloud calls.

Selected via config.LLM_PROVIDER / env IKE_LLM_PROVIDER.
"""
from __future__ import annotations

import os

from src import config

try:
    from dotenv import load_dotenv
    load_dotenv(config.BASE_DIR / ".env")
except Exception:
    pass


class LLMError(RuntimeError):
    pass


class BaseLLM:
    name = "base"

    def complete(self, system: str, user: str, max_tokens: int | None = None) -> str:
        raise NotImplementedError


class AnthropicLLM(BaseLLM):
    name = "anthropic"

    def __init__(self):
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMError(
                "ANTHROPIC_API_KEY is not set. Add it to a .env file in the "
                "project root (see .env.example) or set the environment variable. "
                "Search still works without it — only answer generation and "
                "translation need the key."
            )
        import anthropic
        self.client = anthropic.Anthropic(api_key=key)
        self.model = config.ANTHROPIC_MODEL

    def complete(self, system: str, user: str, max_tokens: int | None = None) -> str:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens or config.ANTHROPIC_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


class OllamaLLM(BaseLLM):
    name = "ollama"

    def __init__(self):
        import requests  # noqa: F401
        self.url = config.OLLAMA_URL.rstrip("/")
        self.model = config.OLLAMA_MODEL

    def complete(self, system: str, user: str, max_tokens: int | None = None) -> str:
        import requests
        r = requests.post(
            f"{self.url}/api/chat",
            json={
                "model": self.model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "options": {"num_predict": max_tokens or config.ANTHROPIC_MAX_TOKENS},
            },
            timeout=300,
        )
        r.raise_for_status()
        return r.json()["message"]["content"].strip()


def get_llm() -> BaseLLM:
    provider = config.LLM_PROVIDER.lower()
    if provider == "anthropic":
        return AnthropicLLM()
    if provider == "ollama":
        return OllamaLLM()
    raise LLMError(f"Unknown LLM provider: {provider!r}")


# ---------------------------------------------------------------------------
# Free LLMs via OpenAI-compatible APIs (Gemini / Groq / OpenRouter)
# ---------------------------------------------------------------------------
def get_chat_client(provider: str | None = None):
    """Return (client, model, label) for the chosen free provider, or None if
    no API key is configured for it."""
    provider = (provider or config.TRANSLATE_PROVIDER).lower()
    spec = config.TRANSLATE_PROVIDERS.get(provider)
    if not spec:
        return None
    key = next((os.environ[e] for e in spec["key_env"] if os.environ.get(e)), None)
    if not key:
        return None
    from openai import OpenAI
    return OpenAI(api_key=key, base_url=spec["base_url"]), spec["model"], spec["label"]


def chat(system: str, user: str, provider: str | None = None,
         max_tokens: int = 4096, temperature: float = 0.2):
    """One-shot chat completion via a free OpenAI-compatible provider.
    Returns (text, provider_label). Raises LLMError if no key is set."""
    provider = (provider or config.TRANSLATE_PROVIDER).lower()
    info = get_chat_client(provider)
    if info is None:
        raise LLMError("No API key set for the chosen translation provider.")
    client, model, label = info
    extra = {}
    if provider == "gemini":
        # Gemini 2.5 'thinking' silently consumes the output budget and truncates
        # the answer. We don't need reasoning to translate — turn it off.
        extra["extra_body"] = {"reasoning_effort": "none"}
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        max_tokens=max_tokens,
        temperature=temperature,
        **extra,
    )
    return (resp.choices[0].message.content or "").strip(), label
