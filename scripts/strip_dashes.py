"""Replace em/en dashes with commas in a translation JSON, in place.

The Arabic source has no em/en dashes, so they should not appear in the English.
Works on either a batch file (en_batches/batch_NNN.json) or the whole English
cache (fatwas_en.json); only string values are touched.

Usage:  python -m scripts.strip_dashes data/processed/en_batches/batch_232.json
"""
from __future__ import annotations

import json
import re
import sys

from src import config


def clean(s: str) -> str:
    s = s.replace("—", ", ").replace("–", ", ")  # em / en dash -> comma
    s = re.sub(r"(?:,\s*){2,}", ", ", s)   # collapse runs of 2+ commas into one
    s = re.sub(r"\s+,", ",", s)            # no space before a comma
    s = re.sub(r" {2,}", " ", s)           # collapse doubled spaces
    return s


def walk(obj):
    if isinstance(obj, str):
        return clean(obj)
    if isinstance(obj, list):
        return [walk(x) for x in obj]
    if isinstance(obj, dict):
        return {k: walk(v) for k, v in obj.items()}
    return obj


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    path = config.BASE_DIR / sys.argv[1]
    data = json.loads(path.read_text(encoding="utf-8"))
    before = path.read_text(encoding="utf-8").count("—") + \
        path.read_text(encoding="utf-8").count("–")
    cleaned = walk(data)
    path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{path.name}: removed {before} em/en dashes.")


if __name__ == "__main__":
    main()
