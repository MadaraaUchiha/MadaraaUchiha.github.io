"""Build the static web app's sidecar data files.

Writes two small files next to the 30 MB fatwas.json so no page has to load the
whole corpus to know what is in it:

  citations.json -- where every quotation begins and ends, in the Arabic and in
    the English, and what it is. Qur'anic quotations are matched against the
    full Qur'an (src/quran.py) and carry their surah:ayah, the authoritative
    English and a quran.com link. Everything else that the edition sets off as
    a quotation is marked as a narration and carries a sunnah.com search --
    NOT a citation: without a hadith corpus to match against, this build can
    say "these are quoted words, here is where to look them up" and no more.

  stats.json -- the counts the landing page prints (fatwas, translated, volumes
    and their per-volume totals), so those figures track the data instead of
    being hard-coded into the HTML and drifting as translation lands.

The English side is the hard one: the translations do not reliably keep the
{ } the Arabic uses. Two signals are trusted, and only two --

  1. the translation kept the braces  -> structural, and matched to an ayah by
     word overlap with its authoritative English;
  2. a run of RUN consecutive words of the authoritative English occurs exactly
     once in the translation -> verbatim, and unambiguous.

A verse the translator paraphrased is left unmarked in the prose rather than
underlined at a guess. It still appears, with its reference, in the margin
index beside the passage: nothing is lost, and nothing is asserted that the
data cannot support.

    .venv\\Scripts\\python scripts\\build_web_data.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Errors quote the passage they are about, and the passage is Arabic. The
# default Windows console encoding cannot print it and would turn a useful
# message into a traceback about cp1252.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.corrections import Corrections, CorrectionError, ayah_reference  # noqa: E402
from src.quran import get_quran  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WEB_DATA = ROOT / "web" / "data"
# The corpus as published, never written to: corrections are applied on the way
# out, so re-running the build can never bake them into the input and leave the
# correction files describing text that is no longer there.
SRC = ROOT / "data" / "corpus" / "fatwas.json"
CORRECTIONS = ROOT / "corrections"
SERVED = WEB_DATA / "fatwas.json"
OUT = WEB_DATA / "citations.json"
STATS = WEB_DATA / "stats.json"

# The corpus behind the engine, from the retrieval index (see README): the whole
# printed work, indexed. The extracted question-and-answer fatwas that this
# static site serves are a subset of it, counted from the data below.
CORPUS_VOLUMES = 37
CORPUS_PASSAGES = 16436

AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
BRACES = re.compile(r"\{([^{}]+)\}")
EN_WORD = re.compile(r"[a-z0-9]+")

RUN = 6                 # consecutive words that must match verbatim, and once
GAP_BUDGET = 3          # words the translation may render differently while
#                         still counting as the same verse, once identified
BRACE_OVERLAP = 0.6     # word overlap for a braced English quote to be an ayah
MIN_NARRATION = 3       # shorter quoted fragments are not worth a search link

# Span kinds, mirrored in search.js
BRACED, BARE = 0, 1
NARRATION = -1          # refIdx for a quotation not identified as Qur'an


def ayah_label_ar(m) -> str:
    """"الحج ٧٥" -- surah name and ayah number in Arabic-Indic digits."""
    span = str(m.ayah_start) if m.ayah_start == m.ayah_end \
        else f"{m.ayah_start}-{m.ayah_end}"
    return f"{m.surah_name_ar} {span.translate(AR_DIGITS)}"


def ref_of(m) -> dict:
    return {
        "r": m.ref,
        "en": f"{m.surah_translit} {m.surah}:{m.ref.split(':')[1]}",
        "ar": ayah_label_ar(m),
        "t": m.english,
        "u": m.url,
    }


def en_words(text: str):
    """lowercase words with their (start, end) offsets in the original string"""
    return [(w.group(0), w.start(), w.end()) for w in EN_WORD.finditer((text or "").lower())]


def enclosing_quote(text: str, start: int, end: int):
    """The "..." the translator put around a verse, if it put one there.

    Returns the span *inside* the marks, or None. A pair only counts if it
    encloses the match without another quotation mark getting in the way, and
    is not wildly longer than what matched -- a stray quote a paragraph away is
    not a statement about where this verse ends.
    """
    left = text.rfind('"', 0, start)
    right = text.find('"', end)
    if left < 0 or right < 0:
        return None
    if '"' in text[left + 1:start] or '"' in text[end:right]:
        return None
    inner_start, inner_end = left + 1, right
    if inner_end - inner_start > (end - start) * 2.5 + 80:
        return None
    return inner_start, inner_end


class RefTable:
    """Per-fatwa table of the verses it quotes, so each is stored once."""

    def __init__(self):
        self.refs: list[dict] = []
        self._by_ref: dict[str, int] = {}

    def index(self, m) -> int:
        if m.ref not in self._by_ref:
            self._by_ref[m.ref] = len(self.refs)
            self.refs.append(ref_of(m))
        return self._by_ref[m.ref]


class Asserted:
    """An ayah named by hand in corrections/, shaped like a matcher result."""

    def __init__(self, spec: str, quran):
        r = ayah_reference(quran, spec)
        self.surah = r["surah"]
        self.surah_name_ar = r["surah_name"]
        self.surah_translit = r["translit"]
        self.ayah_start, self.ayah_end = r["start"], r["end"]
        self.english = r["english"]
        self.url = r["url"]
        self.found = True

    @property
    def ref(self) -> str:
        a = (str(self.ayah_start) if self.ayah_start == self.ayah_end
             else f"{self.ayah_start}-{self.ayah_end}")
        return f"{self.surah}:{a}"


def scan_arabic(text: str, quran, table: RefTable, override=None):
    """Every { } in the printed Arabic, placed and identified."""
    spans, unknown = [], 0
    for m in BRACES.finditer(text or ""):
        inner = m.group(1).strip()
        # A correction, where one exists, is the last word on what this is.
        verdict = override(inner) if override else None
        if verdict == "narration":
            unknown += 1
            spans.append([m.start(), m.end(), NARRATION, BRACED])
            continue
        if verdict:
            spans.append([m.start(), m.end(), table.index(Asserted(verdict, quran)), BRACED])
            continue
        found = [x for x in quran.identify(m.group(0)) if x.found]
        if found:
            spans.append([m.start(), m.end(), table.index(found[0]), BRACED])
        else:
            unknown += 1
            # Every brace gets a span, however short. The braces are the
            # edition's markup, not its prose, and a quotation with no span
            # would have them rendered raw on the page.
            spans.append([m.start(), m.end(), NARRATION, BRACED])
    return spans, unknown


def scan_english(text: str, table: RefTable):
    """The same quotations in the translation, where they can be proven."""
    if not text:
        return [], 0
    spans = []
    placed: set[int] = set()
    words = en_words(text)

    # 1. the translation kept the braces
    unknown = 0
    for m in BRACES.finditer(text):
        inner = m.group(1).strip()
        inner_words = {w for w, _, _ in en_words(inner)}
        best, best_overlap = None, 0.0
        for idx, ref in enumerate(table.refs):
            if idx in placed:
                continue
            auth = {w for w, _, _ in en_words(ref["t"])}
            if not auth or not inner_words:
                continue
            overlap = len(auth & inner_words) / min(len(auth), len(inner_words))
            if overlap > best_overlap:
                best, best_overlap = idx, overlap
        if best is not None and best_overlap >= BRACE_OVERLAP:
            placed.add(best)
            spans.append([m.start(), m.end(), best, BRACED])
        else:
            unknown += 1
            spans.append([m.start(), m.end(), NARRATION, BRACED])

    # 2. a verbatim run of the authoritative English, occurring exactly once
    grams: dict[tuple, list[int]] = {}
    for i in range(len(words) - RUN + 1):
        grams.setdefault(tuple(w for w, _, _ in words[i:i + RUN]), []).append(i)

    taken = [(s, e) for s, e, _, _ in spans]
    text_words = [w for w, _, _ in words]
    for idx, ref in enumerate(table.refs):
        if idx in placed:
            continue
        auth = [w for w, _, _ in en_words(ref["t"])]
        if len(auth) < RUN:
            continue
        anchor = None                    # (index into auth, index into text)
        for i in range(len(auth) - RUN + 1):
            at = grams.get(tuple(auth[i:i + RUN]))
            if at and len(at) == 1:
                anchor = (i, at[0])
                break
            if at:                       # occurs more than once: refuse to guess
                anchor = None
                break
        if anchor is None:
            continue

        # The anchor is only where the verse was *recognised*; on its own it
        # would underline six words out of the middle of a sentence. Identity
        # is already settled by the unique match, so the extent may be worked
        # out more freely: grow while the translation runs with the
        # authoritative text, stepping over the odd word it renders
        # differently, and stop where they part company for good.
        i, j = anchor
        length = RUN
        budget = GAP_BUDGET
        while i > 0 and j > 0:
            if auth[i - 1] == text_words[j - 1]:
                i -= 1
                j -= 1
                length += 1
            elif (budget > 0 and i > 1 and j > 1 and auth[i - 2] == text_words[j - 2]):
                budget -= 1
                i -= 2
                j -= 2
                length += 2
            else:
                break
        budget = GAP_BUDGET
        while i + length < len(auth) and j + length < len(text_words):
            if auth[i + length] == text_words[j + length]:
                length += 1
            elif (budget > 0 and i + length + 1 < len(auth)
                  and j + length + 1 < len(text_words)
                  and auth[i + length + 1] == text_words[j + length + 1]):
                budget -= 1
                length += 2
            else:
                break

        start, end = words[j][1], words[j + length - 1][2]
        # If the translator set the verse inside quotation marks, those are a
        # better statement of where it begins and ends than word-matching is.
        quoted = enclosing_quote(text, start, end)
        if quoted:
            start, end = quoted
        if any(s <= start < e or s < end <= e for s, e in taken):
            continue                     # already inside a marked quotation
        placed.add(idx)
        taken.append((start, end))
        spans.append([start, end, idx, BARE])

    spans.sort(key=lambda s: s[0])
    return spans, unknown


def main() -> int:
    quran = get_quran()
    data = json.loads(SRC.read_text(encoding="utf-8"))

    # Human corrections come first: everything downstream -- the citation
    # spans, the pre-rendered pages, the corpus the search loads -- is computed
    # from the corrected text, so a correction cannot be half-applied.
    try:
        corrections = Corrections.load(CORRECTIONS)
        log = corrections.apply_to(data["fatwas"], quran)
    except CorrectionError as exc:
        print(f"\ncorrection error:\n  {exc}\n")
        return 1
    if log:
        print(f"applied {corrections.applied} corrections:")
        for line in log[:20]:
            print(line)
        if len(log) > 20:
            print(f"  ... and {len(log) - 20} more")
        print()

    out: dict[str, dict] = {}
    ayat = narrations = en_marked = en_unmarked = touched = 0

    for f in data["fatwas"]:
        table = RefTable()
        blocks: dict[str, dict] = {}
        unknown_total = 0
        override = (lambda q, _fid=f["id"]: corrections.override_for(_fid, q))

        for key, ar_field, en_field in (("q", "qa", "qe"), ("a", "aa", "ae")):
            ar_text = f.get(ar_field) or ""
            if "{" not in ar_text:
                continue
            ar_spans, unknown = scan_arabic(ar_text, quran, table, override)
            en_spans, _ = scan_english(f.get(en_field) or "", table)
            if not ar_spans and not en_spans:
                continue
            block = {}
            if ar_spans:
                block["ar"] = ar_spans
            if en_spans:
                block["en"] = en_spans
            if unknown:
                block["u"] = unknown
            blocks[key] = block
            unknown_total += unknown
            ayat += sum(1 for s in ar_spans if s[2] != NARRATION)
            narrations += sum(1 for s in ar_spans if s[2] == NARRATION)
            marked = {s[2] for s in en_spans if s[2] != NARRATION}
            en_marked += len(marked)
            en_unmarked += max(0, len(table.refs) - len(marked))

        if blocks:
            blocks["refs"] = table.refs
            out[f["id"]] = blocks
            touched += 1

    OUT.write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    # The corpus the site serves: the published one with the corrections in it.
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    SERVED.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    per_volume: dict[int, int] = {}
    for f in data["fatwas"]:
        per_volume[f["v"]] = per_volume.get(f["v"], 0) + 1
    meta = data.get("meta", {})
    STATS.write_text(json.dumps({
        "fatwas": len(data["fatwas"]),
        "translated": meta.get("translated", sum(1 for f in data["fatwas"] if f.get("ae"))),
        "corpusVolumes": CORPUS_VOLUMES,
        "corpusPassages": CORPUS_PASSAGES,
        "volumes": {str(v): n for v, n in sorted(per_volume.items())},
        "ayat": ayat,
        "edition": meta.get("edition", ""),
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    total_en = en_marked + en_unmarked
    print(f"{touched} fatwas carry quotations")
    print(f"  Arabic: {ayat} ayah quotations placed, "
          f"{narrations} narrations marked for lookup")
    print(f"  English: {en_marked} of {total_en} verses placed in the translation "
          f"({en_marked / total_en:.1%}); the rest stay in the margin index")
    print(f"wrote {SERVED} ({SERVED.stat().st_size / 1024 / 1024:.1f} MB, corrections applied)")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    print(f"wrote {STATS} ({STATS.stat().st_size} B) -- "
          f"{len(data['fatwas'])} fatwas across {len(per_volume)} volumes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
