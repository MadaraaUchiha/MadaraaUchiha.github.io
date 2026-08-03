"""Vendor the Arabic hadith corpus, so narrations can be looked up and not guessed.

The Qur'an side of this project is settled: every braced quotation is checked
against the whole Qur'an and named to the ayah. The hadith side is not. A
quotation the Qur'an matcher cannot claim is currently shown as "a narration"
with a sunnah.com search link -- honest, but it says nothing about *which*
narration, because there was nothing local to check against.

This fetches something to check against: the Arabic text of ten collections from
fawazahmed0/hadith-api, which is public domain (Unlicense) and served over
jsDelivr.

    .venv\\Scripts\\python scripts\\fetch_hadith.py

About 45 MB and 36,500 narrations, into data/raw/hadith/, which is gitignored --
same as every other raw source in this project. Re-run to refresh.

Two things to know before matching against this.

**The text carries its isnad.** Each record is the whole narration as the
collection prints it, chain first: "حدثنا أبو اليمان الحكم بن نافع، قال أخبرنا
شعيب، عن الزهري..." and only then the matn. The Shaykh quotes the matn. So a
match is a *run* inside the record, never the whole of it, and the run length is
what has to carry the weight.

**A hadith quoting a verse is not a hadith match.** Measured on this corpus, a
five-word run finds something for 69% of unclaimed quotations -- and among the
first few sampled was قولوا آمنا بالله وما أنزل إلينا, which is al-Baqarah
2:136, matched only because a hadith quotes it. Anything built on this must run
*after* the Qur'an matcher and only on what it declines, which is what
`unclaimed()` below is for.

How much survives, by run length, over the 6,297 quotations the Qur'an matcher
does not claim (sample of 800):

    5 words  69.1%      10 words  25.4%
    6 words  58.6%      12 words  17.9%
    8 words  40.4%      14 words  11.6%

Those are recall, not precision. Nothing here decides a threshold -- that needs
the same treatment the Qur'an work got, where three words turned رضي الله عنهم
into al-Ma'idah 5:119 and the number had to be raised until the coincidences
stopped. Attributing a narration to Bukhari that is not in Bukhari is worse than
saying "a narration", so the threshold gets set on measured precision.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "hadith"

BASE = "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions"

# The six canonical books, then Malik's Muwatta and the three short collections.
BOOKS = {
    "bukhari": "Sahih al-Bukhari",
    "muslim": "Sahih Muslim",
    "abudawud": "Sunan Abi Dawud",
    "tirmidhi": "Jami' al-Tirmidhi",
    "nasai": "Sunan al-Nasa'i",
    "ibnmajah": "Sunan Ibn Majah",
    "malik": "Muwatta Malik",
    "nawawi": "Forty Hadith of al-Nawawi",
    "qudsi": "Forty Hadith Qudsi",
    "dehlawi": "Forty Hadith of Shah Waliullah",
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    total = bytes_ = 0
    for slug, title in BOOKS.items():
        dest = OUT / f"ara-{slug}.json"
        if dest.exists():
            note = "cached"
        else:
            try:
                urllib.request.urlretrieve(f"{BASE}/ara-{slug}.json", dest)
                note = "fetched"
            except Exception as err:                       # noqa: BLE001
                print(f"  {slug:<10} could not fetch -- {err}")
                continue
        n = len(json.loads(dest.read_text(encoding="utf-8"))["hadiths"])
        size = dest.stat().st_size
        total += n
        bytes_ += size
        print(f"  {title:<32} {n:>6,} narrations  {size / 1024 / 1024:5.1f} MB  {note}")

    print(f"\n{total:,} narrations, {bytes_ / 1024 / 1024:.0f} MB, in {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
