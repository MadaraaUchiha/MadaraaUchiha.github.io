"""Vendor the web fonts, so the page does not wait on Google to draw its text.

Three families come from fonts.googleapis.com, one of them by an @import inside
the design system's stylesheet -- which is the worst place for it, because the
browser has to fetch and parse that stylesheet before it even learns the fonts
exist. Between the CSS host and the font host that is two DNS lookups, two TLS
handshakes and two round trips on the critical path, before a word is drawn.

Serving the same files from our own origin removes all of it. Cross-site font
caching has been partitioned by every browser for years, so nothing is lost by
not sharing Google's copy.

Only the faces the site actually sets are taken: weights 400 and 600, plus Lora
italic for the <em> the edition's title is set in. Amiri's bold and italics are
never used and are not downloaded.

    .venv\\Scripts\\python scripts\\fetch_fonts.py

Re-run only to change which faces are vendored; the files are committed.
"""
from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "fonts"
CSS = ROOT / "web" / "ds" / "fonts.css"

# A modern browser UA, or Google serves the ancient TTF fallback instead of woff2.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

FAMILIES = {
    "Amiri": "Amiri:ital,wght@0,400",
    "Cormorant Garamond": "Cormorant+Garamond:wght@400;600",
    "Lora": "Lora:ital,wght@0,400;0,600;1,400",
}
# The writing systems this site sets. Latin for the English and the
# transliteration, latin-ext for the diacritics in Majmūʿ al-Fatāwā, arabic for
# the text itself. Cyrillic, Greek and Vietnamese are never drawn.
KEEP_SUBSETS = {"latin", "latin-ext", "arabic"}

FACE = re.compile(r"/\*\s*([\w\-\[\]]+)\s*\*/\s*@font-face\s*\{(.*?)\}", re.S)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    blocks, downloaded, skipped = [], 0, 0

    for family, spec in FAMILIES.items():
        css = fetch(f"https://fonts.googleapis.com/css2?family={spec}&display=swap")
        for subset, body in FACE.findall(css):
            if subset not in KEEP_SUBSETS:
                skipped += 1
                continue
            url = re.search(r"url\((https://[^)]+\.woff2)\)", body)
            weight = re.search(r"font-weight:\s*([\d ]+);", body)
            style = re.search(r"font-style:\s*(\w+);", body)
            rng = re.search(r"unicode-range:\s*([^;]+);", body)
            if not url:
                continue
            w = (weight.group(1) if weight else "400").strip()
            s = style.group(1) if style else "normal"
            slug = family.lower().replace(" ", "-")
            name = f"{slug}-{subset}-{w}{'-italic' if s == 'italic' else ''}.woff2"
            path = OUT / name
            if not path.exists():
                req = urllib.request.Request(url.group(1), headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=60) as r:
                    path.write_bytes(r.read())
            downloaded += 1
            blocks.append(
                f"@font-face {{\n"
                f"  font-family: '{family}';\n"
                f"  font-style: {s};\n"
                f"  font-weight: {w};\n"
                # swap: draw immediately in the fallback and repaint when the
                # real face lands. Never hide the text waiting for a font.
                f"  font-display: swap;\n"
                f"  src: url('../fonts/{name}') format('woff2');\n"
                + (f"  unicode-range: {rng.group(1).strip()};\n" if rng else "")
                + f"}}\n")

    CSS.write_text(
        "/* Vendored from Google Fonts by scripts/fetch_fonts.py -- do not hand-edit.\n"
        "   Served from this origin so no page waits on a third party to draw its\n"
        "   text. Only the faces the site sets are here; see the script. */\n\n"
        + "\n".join(blocks),
        encoding="utf-8")

    total = sum(p.stat().st_size for p in OUT.glob("*.woff2"))
    print(f"vendored {downloaded} faces ({skipped} other subsets skipped)")
    print(f"{len(list(OUT.glob('*.woff2')))} files, {total/1024:.0f} KB total")
    for p in sorted(OUT.glob("*.woff2")):
        print(f"  {p.stat().st_size/1024:6.1f} KB  {p.name}")
    print(f"wrote {CSS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
