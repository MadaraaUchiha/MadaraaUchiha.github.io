"""Fetch a Qur'an translation from fawazahmed0/quran-api.

The site shipped with Saheeh International, data/raw/quran_en.json. This
fetches Dr. Mustafa Khattab's The Clear Qur'an -- the Allah edition, which
writes Allah where the God edition writes God -- and is recognisable by
Khattab's half-brackets, ˹like this˺, around words supplied for sense.

    .venv\\Scripts\\python scripts\\fetch_quran_translation.py
    .venv\\Scripts\\python scripts\\fetch_quran_translation.py --list

No key, no account, no rate limit: the editions are static files on the
jsDelivr CDN. The whole Qur'an is one request.

Only the English is taken. The Uthmani Arabic already in quran_en.json stays
exactly as it is, because src/quran.py matches the printed fatawa against that
spelling and carries a translation table built for it; swapping the Arabic for
another edition's would quietly break every quotation the site places.

The output is a drop-in for quran_en.json, written beside it. Nothing is
switched over here -- set IKE_QURAN_FILE, or edit config.QURAN_FILE, when you
want it live. Note that config.QURAN_MATCH_FILE is a separate setting and
should stay on the literal Saheeh International: see get_quran_for_matching.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402

BASE = "https://cdn.jsdelivr.net/gh/fawazahmed0/quran-api@1"
DEFAULT = "eng-mustafakhattaba"
SOURCE = config.RAW_DIR / "quran_en.json"


def get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "ike/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--edition", default=DEFAULT)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--list", action="store_true",
                    help="list the English editions and exit")
    args = ap.parse_args()

    if args.list:
        eds = get(f"{BASE}/editions.json")
        for e in (eds.values() if isinstance(eds, dict) else eds):
            if e.get("language") == "English":
                print(f"  {e['name']:<28} {e['author']}")
        return 0

    try:
        verses = get(f"{BASE}/editions/{args.edition}.json")["quran"]
    except urllib.error.HTTPError as e:
        print(f"{args.edition}: {e.code}. Try --list.", file=sys.stderr)
        return 1

    # (chapter, verse) -> English, so a missing verse is caught below rather
    # than silently shifting every verse after it by one.
    english = {(v["chapter"], v["verse"]): v["text"].strip() for v in verses}

    suras = json.loads(SOURCE.read_text(encoding="utf-8"))
    missing = []
    for sura in suras:
        for verse in sura["verses"]:
            key = (sura["id"], verse["id"])
            if key in english:
                verse["translation"] = english[key]
            else:
                missing.append(key)

    if missing:
        print(f"{len(missing)} verses are not in {args.edition}, "
              f"first {missing[:5]}; nothing written", file=sys.stderr)
        return 1

    out = args.out or config.RAW_DIR / f"quran_en_{args.edition}.json"
    out.write_text(json.dumps(suras, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"wrote {out} ({len(english)} verses, {args.edition})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
