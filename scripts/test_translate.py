"""Smoke test for local NLLB Arabic->English translation."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from src import config
from src.translate_local import translate_cached

with config.PASSAGES_FILE.open(encoding="utf-8") as f:
    passages = [json.loads(l) for l in f if l.strip()]

sample = next(p for p in passages if p["volume"] == 1 and 300 < p["char_len"] < 700)
print("ARABIC:\n", sample["text_ar"][:500], "\n")
print("ENGLISH (NLLB, machine translation):\n", translate_cached(sample["text_ar"]))
