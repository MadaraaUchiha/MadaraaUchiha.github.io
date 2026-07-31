"""Queue the next batch of untranslated fatwas (shortest answer first).

Usage:  python -m scripts.next_batch [N]      (default N=4)

Selects the N shortest untranslated fatwas, writes their full Arabic + metadata
to data/processed/_translation_queue.json for Claude to translate, and prints
the progress, the chosen ids, and the target batch filename. This replaces the
old ad-hoc _next_batch.json guesswork: resuming is now one command.
"""
from __future__ import annotations

import json
import re
import sys

from src import config

FATWAS = config.PROCESSED_DIR / "fatwas.json"
EN_CACHE = config.PROCESSED_DIR / "fatwas_en.json"
QUEUE = config.PROCESSED_DIR / "_translation_queue.json"
BATCH_DIR = config.PROCESSED_DIR / "en_batches"


def next_batch_number() -> int:
    nums = [int(m.group(1))
            for p in BATCH_DIR.glob("batch_*.json")
            if (m := re.search(r"batch_(\d+)\.json$", p.name))]
    return (max(nums) + 1) if nums else 1


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2

    records = json.loads(FATWAS.read_text(encoding="utf-8"))
    cache = json.loads(EN_CACHE.read_text(encoding="utf-8")) if EN_CACHE.exists() else {}
    done = set(cache)

    remaining = [r for r in records if r["id"] not in done]
    remaining.sort(key=lambda r: len(r["answer_ar"]))
    batch = remaining[:n]

    total, n_done = len(records), len(done)
    print(f"Progress: {n_done}/{total} translated, {len(remaining)} remaining.")
    if not batch:
        QUEUE.write_text('{"fatwas": []}', encoding="utf-8")
        print("Nothing left to translate. Done!")
        return

    target = next_batch_number()
    print(f"Next -> en_batches/batch_{target:03d}.json  ({len(batch)} fatwas, shortest first):")
    for r in batch:
        print(f"  {r['id']}  a_chars={len(r['answer_ar'])}  cat={r.get('category', '')}")

    queue = {
        "target_batch": f"batch_{target:03d}.json",
        "fatwas": [
            {
                "id": r["id"],
                "volume": r["volume"],
                "page_start": r["page_start"],
                "page_end": r["page_end"],
                "category": r.get("category", ""),
                "topic": r.get("topic", ""),
                "question_ar": r["question_ar"],
                "answer_ar": r["answer_ar"],
            }
            for r in batch
        ],
    }
    QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nWrote {QUEUE.name}.  Translate -> {queue['target_batch']}, then merge_en.")
    print("REMINDER: faithful to the Arabic; NO em/en dashes (the source has none).")


if __name__ == "__main__":
    main()
