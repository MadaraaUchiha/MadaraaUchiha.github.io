"""Scholar-grade Arabic -> English translation of passages.

Strategy for translation that actually flows:
  * Translate the WHOLE passage at once (context -> natural prose), not sentence
    by sentence.
  * Use a strong but FREE LLM (Gemini / Groq / OpenRouter via OpenAI-compatible
    API). These understand register and theology, so the English reads naturally.
  * Inject the AUTHORITATIVE English of any Qur'anic verses in the passage so
    quoted scripture is always exact, never machine-mangled.
  * Keep technical terms (Tawhid, Shirk, Bid'ah...) transliterated with glosses.
  * Cache every result so a passage is translated only once.

If no API key is configured, fall back to the local NLLB model (gist quality)
so the feature still works fully offline.
"""
from __future__ import annotations

import hashlib
import json
import threading

from src import config
from src.llm import LLMError, chat, get_chat_client
from src.quran import get_quran

_CACHE = config.PROCESSED_DIR / "translations.json"
_lock = threading.Lock()

SYSTEM = """You are a distinguished scholar-translator rendering the classical \
Arabic of Imam Ibn Taymiyyah's Majmu' al-Fatawa into English.

Your translation must be:
- Faithful and complete: translate everything; omit nothing; add nothing.
- Fluent and natural: well-formed English prose that flows and reads beautifully \
to a modern reader. Do NOT translate word-for-word or produce stilted, choppy text.
- Scholarly in register: dignified, precise theological and legal English.

Conventions:
- Keep established technical terms transliterated, with a short gloss in \
parentheses on first use: Tawhid, Shirk, Bid'ah (innovation), Ijma' (consensus), \
Qiyas (analogy), Sunnah, Salaf (the early generations), Kufr (disbelief), Iman \
(faith). Do not flatten these into loose paraphrase.
- For Qur'anic quotations, use EXACTLY the authoritative English translations \
provided in the QURAN section, in double quotes. Never retranslate a verse yourself.
- Render hadith and other direct quotations as quotations.
- The passage is a search excerpt and may begin or end mid-sentence; translate \
exactly what is given without inventing missing context.
- Output ONLY the English translation. No preamble, notes, headings, or commentary."""


def _key(provider: str, text: str) -> str:
    return hashlib.sha256(f"{provider}:{text}".encode("utf-8")).hexdigest()[:16]


def _load() -> dict:
    if _CACHE.exists():
        try:
            return json.loads(_CACHE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(cache: dict) -> None:
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    _CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def _build_user(text: str) -> str:
    verses = [m for m in get_quran().identify(text) if m.found]
    block = ""
    if verses:
        lines = [f'«{m.arabic}» -> "{m.english}"  (Qur\'an {m.ref})' for m in verses]
        block = ("\n\nQURAN (use these exact English translations for the quoted "
                 "verses):\n" + "\n".join(lines))
    return f"PASSAGE (Arabic):\n{text}{block}\n\nTranslate the passage now."


def translate_passage(text: str):
    """Returns (english_text, engine_label). Uses a free LLM if a key is set,
    otherwise the local NLLB fallback."""
    text = text.strip()
    if not text:
        return "", ""

    use_llm = get_chat_client() is not None
    provider = config.TRANSLATE_PROVIDER if use_llm else "nllb"
    k = _key(provider, text)
    with _lock:
        cache = _load()
        if k in cache:
            entry = cache[k]
            return entry["en"], entry["engine"]

    if use_llm:
        english, label = chat(SYSTEM, _build_user(text))
        engine = label
    else:
        from src.translate_local import translate_cached
        english = translate_cached(text)
        engine = "local NLLB (offline, gist quality)"

    with _lock:
        cache = _load()
        cache[k] = {"en": english, "engine": engine}
        _save(cache)
    return english, engine


def engine_available() -> str:
    """Human label of which engine will be used (for UI hints)."""
    info = get_chat_client()
    return info[2] if info else "local NLLB (offline)"
