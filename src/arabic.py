"""Arabic text utilities.

Two distinct cleanings:
  * normalize_for_search() — aggressive, for BM25 lexical matching (strip
    diacritics, unify letter variants). Improves recall a lot for Arabic.
  * clean_for_embedding() — light, keeps the text natural for the embedding
    model (BGE-M3 was trained on normal text), just drops tatweel/whitespace.
The original text is always preserved separately for display/citation.
"""
from __future__ import annotations

import re

# Harakat / tashkeel and other combining marks, plus tatweel (kashida).
_TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۜ"
                       r"۟-۪ۨ-ۭ]")
_TATWEEL = re.compile(r"ـ")
_NON_ARABIC_PUNCT = re.compile(r"[^؀-ۿݐ-ݿ\s\w]")
_WS = re.compile(r"\s+")

# Page tags and OpenITI structural noise that must never reach search/embedding.
PAGE_TAG = re.compile(r"PageV(\d+)P(\d+)")
# OpenITI milestone markers (inserted every ~300 words for alignment), e.g. ms0004.
_MILESTONE = re.compile(r"\bms\d+\b")


def strip_markers(text: str) -> str:
    """Remove OpenITI structural markers (page tags, milestones) from text."""
    text = PAGE_TAG.sub(" ", text)
    text = _MILESTONE.sub(" ", text)
    return text


def strip_tashkeel(text: str) -> str:
    return _TASHKEEL.sub("", text)


def clean_for_embedding(text: str) -> str:
    """Light cleaning: drop tatweel and collapse whitespace. Keep letters and
    diacritics so the multilingual embedder sees natural Arabic."""
    text = _TATWEEL.sub("", text)
    text = strip_markers(text)
    return _WS.sub(" ", text).strip()


def normalize_for_search(text: str) -> str:
    """Aggressive normalization for lexical (BM25) matching."""
    text = strip_markers(text)
    text = strip_tashkeel(text)
    text = _TATWEEL.sub("", text)
    # Unify alef forms
    text = re.sub(r"[آأإٱ]", "ا", text)  # آأإٱ -> ا
    # Alef maqsura -> ya
    text = text.replace("ى", "ي")                        # ى -> ي
    # Ta marbuta -> ha
    text = text.replace("ة", "ه")                        # ة -> ه
    # Hamza seats -> base
    text = text.replace("ؤ", "و").replace("ئ", "ي")  # ؤ ئ
    text = text.replace("ء", "")                             # standalone hamza
    text = _NON_ARABIC_PUNCT.sub(" ", text)
    return _WS.sub(" ", text).strip()


def tokenize_for_search(text: str) -> list[str]:
    return normalize_for_search(text).split()
