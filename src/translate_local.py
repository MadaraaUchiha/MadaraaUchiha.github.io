"""Local Arabic -> English machine translation (NLLB-200), for the per-passage
English toggle. Runs on the GPU, fully offline, no API key, no cost.

This is *machine translation* for understanding the gist — not a scholarly
translation. Qur'anic verses get their authoritative English from src/quran.py
instead. Results are cached on disk so a passage is translated only once.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading

from src import config

MODEL = "facebook/nllb-200-distilled-600M"
_CACHE = config.PROCESSED_DIR / "translations_nllb.json"
_lock = threading.Lock()
_SENT = re.compile(r"(?<=[\.!\?؟])\s+|\n+")

_instance = None


class LocalTranslator:
    def __init__(self):
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        self.torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tok = AutoTokenizer.from_pretrained(MODEL, src_lang="arb_Arab")
        dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            MODEL, torch_dtype=dtype).to(self.device)
        self.bos = self.tok.convert_tokens_to_ids("eng_Latn")

    def _batch(self, sents: list[str]) -> list[str]:
        enc = self.tok(sents, return_tensors="pt", padding=True,
                       truncation=True, max_length=400).to(self.device)
        with self.torch.no_grad():
            gen = self.model.generate(**enc, forced_bos_token_id=self.bos,
                                      max_length=400, num_beams=2)
        return self.tok.batch_decode(gen, skip_special_tokens=True)

    def translate(self, text: str) -> str:
        sents = [s.strip() for s in _SENT.split(text) if s.strip()]
        if not sents:
            return ""
        out: list[str] = []
        for i in range(0, len(sents), 8):
            out += self._batch(sents[i:i + 8])
        return " ".join(out)


def get_translator() -> LocalTranslator:
    global _instance
    if _instance is None:
        _instance = LocalTranslator()
    return _instance


def _load() -> dict:
    if _CACHE.exists():
        try:
            return json.loads(_CACHE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def translate_cached(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    k = hashlib.sha256(("nllb:" + text).encode("utf-8")).hexdigest()[:16]
    with _lock:
        cache = _load()
        if k in cache:
            return cache[k]
    english = get_translator().translate(text)
    with _lock:
        cache = _load()
        cache[k] = english
        config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        _CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return english
