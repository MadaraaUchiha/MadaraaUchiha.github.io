"""Central configuration. Pure constants only — safe to import anywhere
(no heavy ML imports here, so the parser can use it without torch installed)."""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
INDEX_DIR = DATA_DIR / "index"
CACHE_DIR = BASE_DIR / "cache"

# Load .env early so HF_TOKEN (and any other vars) are visible before the HF Hub
# libraries are imported. Optional — everything works without a .env file.
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except Exception:
    pass

# Keep the HuggingFace model cache inside the project (self-contained, and out
# of the user profile / OneDrive). Must be set before transformers is imported.
os.environ.setdefault("HF_HOME", str(CACHE_DIR / "huggingface"))
# Silence the Windows symlink-cache warning (harmless; caching still works).
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# Raw source text (OpenITI mARkdown, Shamela 7289 = King Fahd Complex edition).
RAW_TEXT_FILE = RAW_DIR / "MajmucFatawa.Shamela0007289-ara1.txt"

# The Qur'an the reader is shown: Dr. Mustafa Khattab's The Clear Qur'an,
# Allah edition, which is what quran.com shows by default. Fetched by
# scripts/fetch_quran_translation.py. quran_en.json, Saheeh International, is
# still here and IKE_QURAN_FILE=quran_en.json puts it back.
#
# The Arabic is the same in both and is always the Uthmani text from
# quran_en.json: src/quran.py matches the printed fatawa against that spelling
# and carries a translation table built for it.
QURAN_FILE = RAW_DIR / os.environ.get("IKE_QURAN_FILE", "quran_en_khattab.json")

# The translation a verse is *found* by, which need not be the one shown. See
# src.quran.get_quran_for_matching: placement works by finding a run of the
# authoritative English inside the machine's own literal wording, so a literal
# translation finds far more of them than a free one. Leave this on Saheeh
# International even when the reader is shown something else.
QURAN_MATCH_FILE = RAW_DIR / os.environ.get("IKE_QURAN_MATCH_FILE",
                                            "quran_en.json")

# Processed artifacts
PASSAGES_FILE = PROCESSED_DIR / "passages.jsonl"          # one passage per line
EMBEDDINGS_FILE = INDEX_DIR / "embeddings.npy"            # float32 [N, dim]
PASSAGE_META_FILE = INDEX_DIR / "passages_meta.jsonl"    # aligned with embeddings
BM25_DIR = INDEX_DIR / "bm25"                             # bm25s index dir

# ---------------------------------------------------------------------------
# Corpus scope (MVP: prove the pipeline on one volume, then scale)
# ---------------------------------------------------------------------------
# Set IKE_TARGET_VOLUME to an int (e.g. 1) to index only that volume, or to
# "all"/""/"none" for the whole 37-volume book (the default).
_tv = os.environ.get("IKE_TARGET_VOLUME", "all").strip().lower()
TARGET_VOLUME: int | None = None if _tv in ("", "all", "none") else int(_tv)

WORK_TITLE = "Majmu' al-Fatawa"
WORK_AUTHOR = "Ibn Taymiyyah"
WORK_EDITION = "King Fahd Complex (ed. Ibn Qasim), 1416/1995"

# ---------------------------------------------------------------------------
# Chunking (passages for retrieval)
# ---------------------------------------------------------------------------
CHUNK_TARGET_CHARS = 1200    # ~400-500 tokens of Arabic
CHUNK_MAX_CHARS = 1800       # hard cap before forcing a split
CHUNK_MIN_CHARS = 200        # passages shorter than this are merged forward

# ---------------------------------------------------------------------------
# Embeddings / retrieval
# ---------------------------------------------------------------------------
EMBED_MODEL = "BAAI/bge-m3"   # multilingual; Arabic + English share one space
EMBED_DIM = 1024
EMBED_BATCH = 16
EMBED_MAX_TOKENS = 1024

TOP_K_DENSE = 30
TOP_K_BM25 = 30
TOP_K_FUSED = 8               # passages handed to the LLM
RRF_K = 60                    # reciprocal-rank-fusion constant

# ---------------------------------------------------------------------------
# LLM provider (generation + scholarly translation)
# ---------------------------------------------------------------------------
# "anthropic" (default, recommended for quality) or "ollama" (fully local).
LLM_PROVIDER = os.environ.get("IKE_LLM_PROVIDER", "anthropic")

# Sonnet is the cost/quality default; switch to claude-opus-4-8 for maximum
# scholarly precision on translation-heavy work.
ANTHROPIC_MODEL = os.environ.get("IKE_ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_MAX_TOKENS = 2000

OLLAMA_MODEL = os.environ.get("IKE_OLLAMA_MODEL", "qwen2.5:7b-instruct")
OLLAMA_URL = os.environ.get("IKE_OLLAMA_URL", "http://localhost:11434")

# ---------------------------------------------------------------------------
# Translation engine — a FREE LLM via an OpenAI-compatible API.
# Default "gemini" (Google AI Studio free tier; no credit card). Alternatives:
# "groq" (Llama 3.3 70B) or "openrouter". Falls back to the local NLLB model
# if no key for the chosen provider is set, so the app always works offline.
# ---------------------------------------------------------------------------
TRANSLATE_PROVIDER = os.environ.get("IKE_TRANSLATE_PROVIDER", "gemini")

# OpenAI-compatible free providers: base URL, accepted key env vars, default model.
TRANSLATE_PROVIDERS = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        "model": os.environ.get("IKE_GEMINI_MODEL", "gemini-2.5-flash"),
        "label": "Gemini 2.5 Flash",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": ["GROQ_API_KEY"],
        "model": os.environ.get("IKE_GROQ_MODEL", "llama-3.3-70b-versatile"),
        "label": "Llama 3.3 70B (Groq)",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": ["OPENROUTER_API_KEY"],
        "model": os.environ.get("IKE_OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free"),
        "label": "OpenRouter (free)",
    },
}


def ensure_dirs() -> None:
    for d in (RAW_DIR, PROCESSED_DIR, INDEX_DIR, CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)
