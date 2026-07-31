"""Merge a batch of Claude-produced English translations into fatwas_en.json
and regenerate the web bundle.

Usage:  python -m scripts.merge_en data/processed/en_batches/batch_001.json

Batch file format (produced by Claude during translation sessions):
    { "itq_00246": {"question_en": "...", "answer_en": "..."}, ... }
"""
from __future__ import annotations

import json
import sys

from src import config
from src.fatwas import write_web_bundle

EN_CACHE = config.PROCESSED_DIR / "fatwas_en.json"
FATWAS = config.PROCESSED_DIR / "fatwas.json"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    batch_path = config.BASE_DIR / sys.argv[1]
    batch = json.loads(batch_path.read_text(encoding="utf-8"))

    cache = {}
    if EN_CACHE.exists():
        cache = json.loads(EN_CACHE.read_text(encoding="utf-8"))

    records = json.loads(FATWAS.read_text(encoding="utf-8"))
    valid_ids = {r["id"] for r in records}

    added, replaced, unknown = 0, 0, 0
    for fid, tr in batch.items():
        if fid not in valid_ids:
            print(f"  WARNING: {fid} not in fatwas.json — skipped")
            unknown += 1
            continue
        if not tr.get("answer_en"):
            print(f"  WARNING: {fid} has empty answer_en — skipped")
            continue
        if fid in cache:
            replaced += 1
        else:
            added += 1
        cache[fid] = {
            "question_en": tr.get("question_en", "").strip(),
            "answer_en": tr["answer_en"].strip(),
            "engine": "claude",
        }

    EN_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"Merged {batch_path.name}: +{added} new, {replaced} replaced, "
          f"{unknown} unknown ids. Total translated: {len(cache)}/{len(records)}")

    write_web_bundle(records)


if __name__ == "__main__":
    main()
