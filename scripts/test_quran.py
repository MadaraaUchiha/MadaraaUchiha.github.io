"""Test Qur'an recognition on real corpus passages."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from src import config
from src.quran import get_quran, BRACES

q = get_quran()
print(f"Loaded Qur'an index: {len(q.ayat)} ayat\n")

# 1) Known verse
for mt in q.identify("قال تعالى: {إياك نعبد وإياك نستعين} وهذا توحيد."):
    print(f"  KNOWN -> found={mt.found} ref={mt.ref} ({mt.surah_translit}) :: {mt.english}")

# 2) Real corpus passages
total_braces = found = unfound = 0
examples = []
with config.PASSAGES_FILE.open(encoding="utf-8") as f:
    passages = [json.loads(l) for l in f if l.strip()]

for p in passages:
    n = len(BRACES.findall(p["text_ar"]))
    if not n:
        continue
    total_braces += n
    for mt in q.identify(p["text_ar"]):
        if mt.found:
            found += 1
            if len(examples) < 6:
                examples.append((p["volume"], p["page_start"], mt))
        else:
            unfound += 1

print(f"\nBraced quotations across corpus: {total_braces}")
print(f"Identified as Qur'an: {found} unique  |  unmatched: {unfound} unique")
print("\n--- sample identifications ---")
for vol, pg, mt in examples:
    print(f"  vol {vol} p.{pg}: Qur'an {mt.ref} — Surat {mt.surah_translit}")
    print(f"      EN: {mt.english[:110]}")
