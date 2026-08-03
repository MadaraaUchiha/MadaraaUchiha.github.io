"""Prepare the four photographs the life page sets into its plates.

The design leaves five frames empty, each captioned with the photograph that
belongs in it. Four are now filled. The fifth, Alexandria, is gone: that station
sits over the map with the route drawn from Cairo down to the coast, and the map
is the picture there -- a plate on top of it only covered what it was showing.

Chosen against the captions rather than by resolution, since the caption says
what the frame is for:

  Harran      the ruins and the old Ulu Cami minaret, not the fenced castle
  Umayyad     the courtyard AND the mosaics, which only one of them shows
  Cairo       Burj al-Ramla, Ayyubid stone under the Muqattam -- deliberately
              not the frame filled by the Muhammad Ali mosque, which was built
              five centuries after the imprisonment this station is about
  Damascus    the outer walls and towers from outside, as captioned. The
              sharper alternative is an interior mid-restoration, all
              scaffolding and rubble, which is the wrong picture for the place
              he died in whatever its pixel count

Each is cut to twice the width its frame is ever given -- .fig caps at --fw, so
twice that covers a 2x screen and nothing is shipped larger than it can be seen.
Damascus is the exception: the source is 700px and cannot be enlarged, so it
goes as it is, a little soft on a dense screen and right in what it shows.

    .venv\\Scripts\\python scripts\\build_life_images.py --from "C:\\path\\to\\Images"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "img"

# source (relative to the given folder), output name, frame width in CSS px,
# and the aspect the plate is set to
PLATES = [
    ("Harran/QwRY54Li1HMwD7oNfouL9ZawTgyKQJvDWh8VByNWzu.webp",
     "harran-ulu-cami.webp", 340, (4, 3)),
    ("Ummayads mosque/Coutyard-syria-mee-zirrar.jpg.webp",
     "umayyad-mosque-courtyard.webp", 520, (16, 9)),
    ("Cairo citedal tower/برج-الرملة-من-داخل-القلعة-2.jpg",
     "cairo-citadel-burj-al-ramla.webp", 520, (3, 2)),
    ("damascus prison/Damaskus4.jpg",
     "damascus-citadel.webp", 500, (3, 2)),
]


def fit(im, aspect):
    """Centre-crop to the plate's aspect, so nothing is squashed to fit it."""
    want = aspect[0] / aspect[1]
    w, h = im.size
    have = w / h
    if abs(have - want) < 0.005:
        return im
    if have > want:                                   # too wide: trim the sides
        new = round(h * want)
        x = (w - new) // 2
        return im.crop((x, 0, x + new, h))
    new = round(w / want)                             # too tall: trim top/bottom
    y = (h - new) // 2
    return im.crop((0, y, w, y + new))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", type=Path, required=True)
    args = ap.parse_args()

    try:
        from PIL import Image
    except ImportError:
        print("Pillow is needed:  .venv\\Scripts\\python -m pip install pillow")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    for rel, name, fw, aspect in PLATES:
        src = args.src / rel
        if not src.exists():
            print(f"  missing: {rel}")
            continue
        im = Image.open(src).convert("RGB")
        was = im.size
        im = fit(im, aspect)
        target = fw * 2                                # 2x the frame, never more
        if im.width > target:
            im = im.resize((target, round(target * aspect[1] / aspect[0])),
                           Image.LANCZOS)
        dest = OUT / name
        im.save(dest, "WEBP", quality=82, method=6)
        kb = dest.stat().st_size / 1024
        total += kb
        note = "" if im.width >= target else f"  (source only {was[0]}px wide)"
        print(f"  {name:<34} {was[0]}x{was[1]} -> {im.width}x{im.height}  {kb:5.0f} KB{note}")
    print(f"\n{total:.0f} KB in {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
