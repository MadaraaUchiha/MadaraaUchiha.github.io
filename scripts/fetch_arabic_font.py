"""Vendor the King Fahd Complex's Arabic face.

The corpus is a transcription of the Complex's own printing of Majmu' al-Fatawa,
so its Arabic is best set in the Complex's own type: KFGQPC Uthman Taha Naskh.

The files are NOT committed. The Complex publishes them itself, under its own
terms, and those are its to give rather than this repository's to pass on -- so
they are fetched here instead. Until they are, ds/arabic.css simply fails to
load them and every page falls through to Amiri, which is vendored. Nothing
breaks; the Arabic is set in Amiri.

    .venv\\Scripts\\python scripts\\fetch_arabic_font.py

If the download is blocked, take the fonts from

    https://fonts.qurancomplex.gov.sa/

and drop them in web/fonts/ under the names below. woff2 is preferred and about
a third the size; a .ttf works too, and ds/arabic.css asks for either.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "fonts"

# What ds/arabic.css asks for, and where the Complex publishes it.
FACES = {
    "kfgqpc-uthman-taha-naskh": [
        "https://fonts.qurancomplex.gov.sa/wp-content/uploads/2022/01/UthmanTN1-Ver10.otf",
        "https://fonts.qurancomplex.gov.sa/wp-content/uploads/2020/12/UthmanTN1-Ver10.ttf",
    ],
    "kfgqpc-uthman-taha-naskh-bold": [
        "https://fonts.qurancomplex.gov.sa/wp-content/uploads/2022/01/UthmanTNB1-Ver10.otf",
    ],
    # Declared in ds/arabic.css but not wired into --font-arabic; it is drawn
    # for the Uthmani orthography and this corpus prints imla'i. See that file.
    "kfgqpc-uthmanic-script-hafs": [
        "https://fonts.qurancomplex.gov.sa/wp-content/uploads/2021/04/UthmanicHafs1-Ver18.otf",
    ],
}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def woff2(raw: bytes, dest: Path) -> bool:
    """Compress to woff2 if fonttools is here; say so plainly if it is not."""
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return False
    import io
    f = TTFont(io.BytesIO(raw))
    f.flavor = "woff2"
    f.save(dest)
    return True


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    got = missed = 0
    for name, urls in FACES.items():
        raw = None
        for url in urls:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=60) as r:
                    raw = r.read()
                break
            except Exception as err:                      # noqa: BLE001
                print(f"  {name}: {url.rsplit('/', 1)[-1]} -- {err}")
        if not raw:
            missed += 1
            continue
        if woff2(raw, OUT / f"{name}.woff2"):
            print(f"  {(OUT / (name + '.woff2')).stat().st_size / 1024:7.1f} KB  {name}.woff2")
        else:
            (OUT / f"{name}.ttf").write_bytes(raw)
            print(f"  {len(raw) / 1024:7.1f} KB  {name}.ttf  (install fonttools for woff2)")
        got += 1

    print(f"\n{got} of {len(FACES)} faces vendored to {OUT}")
    if missed:
        print("The Complex's server was not reachable for the rest. Download them")
        print("from https://fonts.qurancomplex.gov.sa/ and drop them in web/fonts/")
        print("under the names above. Until then the Arabic sets in Amiri.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
