"""Vendor the King Fahd Complex's Arabic face.

The corpus is a transcription of the Complex's own printing of Majmu' al-Fatawa,
so its Arabic is set in the Complex's own type: KFGQPC HAFS Uthmanic Script,
Uthman Taha's hand, in the Unicode-text edition (not the page-by-page one).

    .venv\\Scripts\\python scripts\\fetch_arabic_font.py

Two things about it are worth knowing.

**The alef madda, and why it is left alone.** The font is drawn for the Mushaf,
which writes آ as an alef plus a combining madda, so it carries no precomposed
U+0622 -- and the corpus uses U+0622 nearly twelve thousand times. It renders
correctly anyway: HarfBuzz decomposes a character the font lacks, and Chrome,
Firefox and Edge all shape with HarfBuzz. Measured here, آ comes out as 252 ink
pixels against the bare alef's 160, the madda sitting twelve pixels higher.

Building a precomposed glyph for it was tried and thrown away, and the reason is
worth recording so nobody tries it twice. The geometry is easy -- the font's own
GPOS anchors put the madda at (-100, +1350) on the alef, and a composite built
there is correct in isolation. But a glyph invented after the fact appears in no
GSUB coverage, so it never receives its joined form, and آ inside a word came
out visibly wrong: الآخرة differed from the shaper's own rendering by 1,133
pixels while an isolated alef matched to the pixel. Doing it properly means a
ccmp decomposition rule, which is precisely what HarfBuzz already does for free.

So the font ships exactly as the Complex made it. On a shaper that does not
decompose, that one character falls through to Amiri -- which is next in the
stack, is vendored, and draws it correctly. Either path renders آ.

**The format.** The Complex ships TrueType. woff2 is the same outlines under
better compression -- about a third the size over the wire, and every browser
that matters has taken it for years -- so the .ttf is converted rather than
served. That is what the `Download woff2` button on QUL gives you, except that
button wants an account and the CDN behind it does not.

If the download is ever blocked, take UthmanicHafs_V22.ttf from

    https://qul.tarteel.ai/resources/font/245

and re-run with --from-file PATH. Until the font is in web/fonts/, ds/arabic.css
simply fails to load it and every page falls through to Amiri, which is
vendored. Nothing breaks; the Arabic is set in Amiri.
"""
from __future__ import annotations

import argparse
import io
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "fonts"
DEST = OUT / "kfgqpc-hafs.woff2"

# QUL (Tarteel's Quran resource project) publishes the Complex's Unicode-text
# Hafs font here, and its own documentation links this file directly.
URL = "https://static-cdn.tarteel.ai/qul/fonts/UthmanicHafs_V22.ttf"


UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-file", type=Path, help="use a local .ttf instead of downloading")
    args = ap.parse_args()

    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        print("fontTools is needed to compress the font to woff2:")
        print("    .venv\\Scripts\\python -m pip install fonttools brotli")
        return 1

    if args.from_file:
        raw = args.from_file.read_bytes()
        print(f"read {len(raw) / 1024:.0f} KB from {args.from_file}")
    else:
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
            print(f"fetched {len(raw) / 1024:.0f} KB from {URL}")
        except Exception as err:                       # noqa: BLE001
            print(f"could not fetch {URL}\n  {err}")
            print("\nDownload UthmanicHafs_V22.ttf from")
            print("    https://qul.tarteel.ai/resources/font/245")
            print("and re-run with --from-file PATH. Until then the Arabic sets in Amiri.")
            return 1

    font = TTFont(io.BytesIO(raw))
    print("family     :", next(r.toUnicode() for r in font["name"].names if r.nameID == 1))

    OUT.mkdir(parents=True, exist_ok=True)
    font.flavor = "woff2"
    font.save(DEST)
    print(f"wrote      : {DEST.relative_to(ROOT)}  "
          f"({DEST.stat().st_size / 1024:.0f} KB, from {len(raw) / 1024:.0f} KB ttf)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
