"""Headless end-to-end test of the redesigned app via AppTest.
With no API key set, translation falls back to local NLLB (so this runs offline)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from src.translate import engine_available
from src.llm import get_chat_client
from streamlit.testing.v1 import AppTest

print(f"[0] Translation engine resolves to: {engine_available()} "
      f"(cloud key present: {get_chat_client() is not None})")

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300)

at.run()
assert not at.exception, f"empty-state exception: {at.exception}"
print(f"[1] Empty state OK — {len(at.button)} example chips")

at.text_input(key="q").set_value("seeking help from other than Allah").run()
assert not at.exception, f"query exception: {at.exception}"
md = " ".join(m.value for m in at.markdown)
assert 'class="arabic"' in md and "badge cite" in md, "missing Arabic/citation"
assert "quran-panel" in md and 'class="ayah"' in md, "missing Qur'an panel/gold ayat"
print("[2] Query OK — Arabic, citations, gold ayat, Qur'an panel rendered")

sim = [b for b in at.button if b.key and b.key.startswith("sim_main_")]
assert sim, "no Find-similar button"
sim[0].click().run()
assert not at.exception, f"find-similar exception: {at.exception}"
assert "Similar passages" in " ".join(m.value for m in at.markdown)
nb_en = [b for b in at.button if b.key and b.key.startswith("enbtn_sim")]
assert nb_en, "similar passages have no English toggle (the bug you reported)"
print(f"[3] Find-similar OK — neighbours rendered WITH their own English toggle "
      f"({len(nb_en)} of them)")

en = [b for b in at.button if b.key and b.key.startswith("enbtn_main_")]
en[0].click().run()
assert not at.exception, f"english-toggle exception: {at.exception}"
assert "en-block" in " ".join(m.value for m in at.markdown), "no English block"
print("[4] English toggle OK on a result")

# translate a similar-passage too (the second bug)
nb_en2 = [b for b in at.button if b.key and b.key.startswith("enbtn_sim")]
nb_en2[0].click().run()
assert not at.exception, f"similar-english exception: {at.exception}"
print("[5] English toggle OK on a SIMILAR passage too")
print("\nALL CHECKS PASSED")
