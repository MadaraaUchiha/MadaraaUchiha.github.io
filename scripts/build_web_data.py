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
# The whole corrected corpus. A build artefact, not a page asset: the search
# page reads the two files below instead, and every full answer already has a
# pre-rendered page, so publishing this too would put 29 MB on the site that
# nothing fetches. It lives outside web/ so it cannot be deployed by accident.
SERVED = ROOT / "data" / "build" / "fatwas.json"
CORE = WEB_DATA / "search-core.json"
REST = WEB_DATA / "search-rest.json"
OUT = WEB_DATA / "citations.json"
STATS = WEB_DATA / "stats.json"
LINES = WEB_DATA / "home-lines.json"

# How much of each answer the first payload carries. Comfortably more than a
# result card shows (460 characters of Arabic, 700 of English), so the page can
# render every result it ranks before the rest of the corpus has arrived.
CORE_AR = 1000
CORE_EN = 1400
# How much of a verse's authoritative English the tooltip carries.
TOOLTIP_CHARS = 130

# What the retrieval index actually holds. The King Fahd edition is 37 volumes,
# but volumes 36 and 37 are its indexes, not fatawa: the OpenITI transcription
# carries volumes 1-35, which is the whole of the text, plus the edition's own
# index of treatises as front matter. Every page tag in the source, every
# passage in data/index, and every extracted fatwa stops at 35 -- so the site
# must say 35, not 37, or it is promising two volumes that contain no answers.
CORPUS_VOLUMES = 35
CORPUS_PASSAGES = 16436
INDEX_VOLUMES = [36, 37]

AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
BRACES = re.compile(r"\{([^{}]+)\}")
EN_WORD = re.compile(r"[a-z0-9]+")

# The landing page drifts real sentences of the text behind its search box.
# Whole sentences only, short enough to read as one line in passing, taken
# evenly across the volumes, and carrying their own quotation marking so a
# Qur'anic verse is ruled in gold as it goes past. Nothing here is written for
# the page: it is the corpus, sampled.
HOME_LINES = 200
LINE_MIN, LINE_MAX = 45, 130
# Arabic sentences end on a full stop, a question mark or an exclamation; the
# transcription uses the Arabic question mark as often as the Latin one.
SENTENCE = re.compile(r"[^.؟?!\n]+[.؟?!]?")
# A line worth drifting is prose. These are the marks of something else: a
# page tag, a heading number, a fragment of the edition's own apparatus.
AR_LETTER = re.compile(r"[ء-ي]")

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


def line_segments(text: str, spans):
    """A sentence cut into [run, kind] pairs: 0 prose, 1 Qur'an, 2 a narration.

    The edition marks every quotation with braces. Those are its markup, not its
    prose, so they are replaced here with the ornate parentheses the rest of the
    site sets scripture in, and the guillemets it sets an unidentified narration
    in -- the same distinction the reading pages draw, drawn once at build time
    so the page has no offsets to do arithmetic on.
    """
    runs, at = [], 0
    for start, end, ref, _kind in spans:
        if start > at:
            runs.append([text[at:start], 0])
        inner = text[start:end].strip()
        if inner.startswith("{") and inner.endswith("}"):
            inner = inner[1:-1].strip()
        runs.append(["﴿" + inner + "﴾", 1] if ref != NARRATION
                    else ["«" + inner + "»", 2])
        at = end
    if at < len(text):
        runs.append([text[at:], 0])

    runs = [[re.sub(r"\s+", " ", r[0]), r[1]] for r in runs]
    # A run of nothing but space between two quotations is the space between
    # them and has to stay; the same run at either end is padding and goes.
    while runs and not runs[0][0].strip():
        runs.pop(0)
    while runs and not runs[-1][0].strip():
        runs.pop()
    runs = [[r[0] if r[0].strip() else " ", r[1]] for r in runs]
    # the transcription sometimes leaves a space before the closing full stop
    if runs and runs[-1][1] == 0:
        runs[-1][0] = re.sub(r"\s+([.؟?!])$", r"\1", runs[-1][0])
    return runs


def home_lines(fatwas, citations):
    """Sentences of the text for the landing page's ground, evenly by volume.

    Preference goes to sentences that carry a quotation, because those are the
    ones that show what this site is for -- but not every one of them, or the
    ground would read as an anthology of verses rather than as his prose.
    """
    by_volume: dict[int, list] = {}
    for f in fatwas:
        text = f.get("aa") or ""
        if not text:
            continue
        spans = ((citations.get(f["id"]) or {}).get("a") or {}).get("ar") or []
        # At most two lines from any one fatwa, and never two of a kind: the
        # first sentence that carries scripture, and the first that is plain
        # prose. Taking only the first sentence of each would collect nothing
        # but the doxology every answer opens on.
        best = {}
        for m in SENTENCE.finditer(text):
            if len(best) == 2:
                break
            s, e = m.start(), m.end()
            body = m.group(0).strip()
            if not (LINE_MIN <= len(body) <= LINE_MAX):
                continue
            # a whole sentence, not a heading or a line of the edition's own
            # front matter: those come without a stop at the end of them
            if body[-1] not in ".؟?!":
                continue
            # letters, overwhelmingly: a run of digits is the apparatus, not prose
            if len(AR_LETTER.findall(body)) < len(body) * 0.55:
                continue
            # a quotation the sentence split cut in half would be rendered with
            # one of its braces showing
            if any(sp[0] < e and sp[1] > s and (sp[0] < s or sp[1] > e) for sp in spans):
                continue
            offset = s + (len(m.group(0)) - len(m.group(0).lstrip()))
            inside = [[sp[0] - offset, sp[1] - offset, sp[2], sp[3]]
                      for sp in spans if sp[0] >= s and sp[1] <= e]
            runs = line_segments(body, inside)
            # every brace in the line has to have been consumed by a span, or
            # the edition's markup shows through on the page
            if any("{" in r[0] or "}" in r[0] for r in runs):
                continue
            has_q = 1 if any(r[1] == 1 for r in runs) else 0
            if has_q in best:
                continue
            best[has_q] = {"v": f["v"], "s": runs, "q": has_q}
        for line in best.values():
            by_volume.setdefault(f["v"], []).append(line)

    # round-robin the volumes, so the ground is the whole work and not whichever
    # volume happens to have the most quotable openings
    picked, order = [], sorted(by_volume)
    for i in range(max((len(v) for v in by_volume.values()), default=0)):
        for v in order:
            if i < len(by_volume[v]):
                picked.append(by_volume[v][i])
        if len(picked) >= HOME_LINES * 3:
            break
    with_verse = [l for l in picked if l["q"]]
    plain = [l for l in picked if not l["q"]]
    # three lines of his prose to two carrying scripture
    want_q = min(len(with_verse), HOME_LINES * 2 // 5)
    out = with_verse[:want_q] + plain[:HOME_LINES - want_q]
    out.sort(key=lambda l: l["v"])
    return out


# An Arabic brace with no verse behind it offers no English to compare against,
# so it scores a flat middling amount: enough to take an English brace that
# matches no verse well, not enough to outbid one that does.
NARR_SIM = 0.35


def align_braces(en_quotes, ar_marks, table):
    """Give each English brace the Arabic brace it is, in order.

    Every English brace takes one Arabic brace; Arabic braces may be skipped,
    because the translator drops some. Maximising the total similarity over the
    whole passage is what keeps a short verse of common words from stealing a
    long quotation: it would have to displace a better-fitting neighbour.
    """
    m, n = len(en_quotes), len(ar_marks)
    if not m:
        return []
    if m > n:                       # more braces than the Arabic has: give up
        return [(s, e, inner, NARRATION) for s, e, inner in en_quotes]

    def sim(inner, mark):
        if mark == NARRATION:
            return NARR_SIM
        auth = {w for w, _, _ in en_words(table.refs[mark]["t"])}
        got = {w for w, _, _ in en_words(inner)}
        if not auth or not got:
            return 0.0
        # How much of the *quotation* the verse accounts for, and not how much
        # of the verse the quotation covers. The Shaykh quotes the clause he is
        # arguing from, not the whole ayah: {Who is it that intercedes with Him
        # except by His permission?} is eleven words of al-Baqarah 2:255, which
        # runs to ninety. Measuring against the whole verse scored that at 0.11
        # and lost it to the flat narration score, so a passage quoted in part
        # was shown to the reader as though it were not scripture at all.
        #
        # This direction cannot be gamed the other way: a short verse cannot
        # claim a long quotation, because the words it fails to account for
        # count against it.
        return len(auth & got) / len(got)

    NEG = float("-inf")
    best = [[NEG] * (n + 1) for _ in range(m + 1)]
    back = [[None] * (n + 1) for _ in range(m + 1)]
    for j in range(n + 1):
        best[0][j] = 0.0
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if best[i][j - 1] > best[i][j]:
                best[i][j] = best[i][j - 1]
                back[i][j] = (0, j - 1)
            cand = best[i - 1][j - 1] + sim(en_quotes[i - 1][2], ar_marks[j - 1])
            if cand > best[i][j]:
                best[i][j] = cand
                back[i][j] = (1, j - 1)
    taken = [NARRATION] * m
    i, j = m, n
    while i > 0 and j > 0 and back[i][j] is not None:
        kind, at = back[i][j]
        if kind:
            taken[i - 1] = ar_marks[at]
            i -= 1
        j = at
    return [(s, e, inner, mark) for (s, e, inner), mark in zip(en_quotes, taken)]


def scan_english(text: str, table: RefTable, ar_marks: list[int]):
    """The same quotations in the translation, where they can be proven."""
    if not text:
        return [], 0
    spans = []
    placed: set[int] = set()
    words = en_words(text)

    # 1. the translation kept the braces.
    #
    # Which brace is which is settled by the Arabic, not guessed at again here.
    # The edition marks every quotation in the Arabic and scan_arabic has already
    # said what each one is; the translator keeps some of those braces and drops
    # others, but never reorders them. So the English braces are a subsequence of
    # the Arabic ones, and the honest question is which Arabic brace each English
    # one is -- answered by aligning the two sequences in order, best total score.
    #
    # Matching each English brace to whichever verse it happened to look most
    # like was how As-Saffat 37:87 came to be printed against Al 'Imran 3:79.
    # Worse, an English brace nobody could place was then asserted to be a
    # narration -- so Ash-Sharh 94:7, Al-Ma'idah 5:44 and Al-Baqarah 2:186 were
    # all shown to the reader as narrations in the translation while the Arabic
    # beside them was correctly cited. Failing to place a quotation is not
    # evidence that it is not scripture.
    unknown = 0
    en_quotes = [(m.start(), m.end(), m.group(1).strip()) for m in BRACES.finditer(text)]
    for s, e, inner, mark in align_braces(en_quotes, ar_marks, table):
        if mark == NARRATION:
            unknown += 1
        else:
            placed.add(mark)
        spans.append([s, e, mark, BRACED])

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
    # Everything this script writes lands here, and on a fresh checkout it does
    # not exist: the corpus arrives in data/corpus/, not in web/data/.
    WEB_DATA.mkdir(parents=True, exist_ok=True)
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
            en_spans, _ = scan_english(f.get(en_field) or "", table,
                                       [s[2] for s in ar_spans])
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

    # The authoritative English of every verse is two thirds of this file, and
    # it is only ever read in a tooltip. The build needs it whole -- it is what
    # the English side is matched against -- but the page does not, so it ships
    # as a preview and quran.com carries the rest. 724 KB -> 257 KB gzipped.
    for record in out.values():
        for ref in record.get("refs", []):
            text = ref.get("t") or ""
            if len(text) > TOOLTIP_CHARS:
                ref["t"] = text[:TOOLTIP_CHARS].rstrip() + "…"

    OUT.write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    # The whole corrected corpus, for the pre-renderer to read. Not published.
    SERVED.parent.mkdir(parents=True, exist_ok=True)
    SERVED.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    # ...and the same corpus split in two, because a reader should not wait on
    # 8 MB to type a word. A result card never shows more than the question and
    # the opening of the answer, and the whole answer now has a page of its own,
    # so the first file carries everything the search page can display and the
    # second carries the tails of the answers. Search works off the first; the
    # second arrives behind it and the query is quietly re-run, so a term buried
    # deep in a long answer is still found -- a moment later, not never.
    core, rest = [], {}
    for f in data["fatwas"]:
        aa, ae = f.get("aa") or "", f.get("ae") or ""
        head = {k: f.get(k) for k in ("id", "v", "ps", "pe", "cat", "topic", "qa", "qe")}
        head["aa"] = aa[:CORE_AR]
        head["ae"] = ae[:CORE_EN]
        if len(aa) > CORE_AR or len(ae) > CORE_EN:
            head["more"] = 1
            rest[f["id"]] = {"aa": aa[CORE_AR:], "ae": ae[CORE_EN:]}
        core.append(head)

    CORE.write_text(json.dumps({"meta": data.get("meta", {}), "fatwas": core},
                               ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8")
    REST.write_text(json.dumps(rest, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8")

    per_volume: dict[int, int] = {}
    for f in data["fatwas"]:
        per_volume[f["v"]] = per_volume.get(f["v"], 0) + 1
    meta = data.get("meta", {})
    STATS.write_text(json.dumps({
        "fatwas": len(data["fatwas"]),
        "translated": meta.get("translated", sum(1 for f in data["fatwas"] if f.get("ae"))),
        "corpusVolumes": CORPUS_VOLUMES,
        "corpusPassages": CORPUS_PASSAGES,
        "indexVolumes": INDEX_VOLUMES,
        "volumes": {str(v): n for v, n in sorted(per_volume.items())},
        "ayat": ayat,
        "edition": meta.get("edition", ""),
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # The sentences that drift behind the landing page's search. Small enough to
    # fetch after first paint; the page ships a handful inline so the ground is
    # never empty while this is in flight, or if it never arrives.
    lines = home_lines(data["fatwas"], out)
    LINES.write_text(json.dumps({"lines": lines}, ensure_ascii=False,
                                separators=(",", ":")), encoding="utf-8")

    total_en = en_marked + en_unmarked
    print(f"{touched} fatwas carry quotations")
    print(f"  Arabic: {ayat} ayah quotations placed, "
          f"{narrations} narrations marked for lookup")
    print(f"  English: {en_marked} of {total_en} verses placed in the translation "
          f"({en_marked / total_en:.1%}); the rest stay in the margin index")
    print(f"wrote {SERVED} ({SERVED.stat().st_size / 1024 / 1024:.1f} MB, corrections applied)")
    print(f"wrote {CORE} ({CORE.stat().st_size / 1024 / 1024:.1f} MB) "
          f"-- what the search page loads first")
    print(f"wrote {REST} ({REST.stat().st_size / 1024 / 1024:.1f} MB) "
          f"-- the tails of the answers, fetched behind it")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    print(f"wrote {STATS} ({STATS.stat().st_size} B) -- "
          f"{len(data['fatwas'])} fatwas across {len(per_volume)} volumes")
    print(f"wrote {LINES} ({LINES.stat().st_size / 1024:.0f} KB) -- "
          f"{len(lines)} sentences from {len({l['v'] for l in lines})} volumes, "
          f"{sum(l['q'] for l in lines)} carrying scripture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
