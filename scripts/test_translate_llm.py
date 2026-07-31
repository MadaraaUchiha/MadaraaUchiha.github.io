"""Verify the free-LLM translation once you've added a key to .env.

Usage:  .venv\\Scripts\\python scripts\\test_translate_llm.py
If no key is set it tells you what to do; otherwise it translates a real
passage so you can see the quality.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from src import config
from src.llm import get_chat_client
from src.translate import translate_passage

info = get_chat_client()
if info is None:
    print("No translation API key found.\n")
    print("To enable fluent English (free):")
    print("  1. Get a free Gemini key (no card) at https://aistudio.google.com/apikey")
    print("  2. Create a file named '.env' in the project root containing:")
    print("       GEMINI_API_KEY=your_key_here")
    print("  3. Re-run this script.\n")
    print(f"(Until then, translation falls back to: {config.TRANSLATE_PROVIDER} -> local NLLB)")
    sys.exit(0)

print(f"Using provider: {info[2]}  (model: {info[1]})\n")
with config.PASSAGES_FILE.open(encoding="utf-8") as f:
    passages = [json.loads(l) for l in f if l.strip()]
sample = next(p for p in passages if p["volume"] == 1 and "{" in p["text_ar"]
              and 350 < p["char_len"] < 800)

print("ARABIC:\n", sample["text_ar"][:600], "\n")
english, engine = translate_passage(sample["text_ar"])
print(f"ENGLISH ({engine}):\n", english)
