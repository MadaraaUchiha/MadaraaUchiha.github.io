"""Extract discrete Question&Answer fatwa records from Majmu' al-Fatawa.

Unlike src/parse.py (which chunks the book into fixed-size retrieval passages),
this module segments the text into the *natural* fatwa unit that Ibn Taymiyyah's
compilers used throughout the work:

    وَسُئِلَ ... (the question, sometimes prefixed "قال السائل:")
    فَأَجَابَ ... (the answer, "الحمد لله ...")

Each such pair becomes one Fatwa record carrying its Arabic question, Arabic
answer, and full source metadata (volume, page range, kitab/topic heading).

Run:  python -m src.fatwas
Outputs: data/processed/fatwas.json   (array, ready for the web frontend)
         data/processed/fatwas.jsonl  (one record per line, for pipelines)
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field, asdict

from src import config
from src.arabic import strip_tashkeel
from src.parse import (
    to_logical_lines,
    assign_pages,
    build_paragraphs,
    build_treatise_index,
    Para,
)

# ---------------------------------------------------------------------------
# Marker detection. We strip tashkeel (harakat) first so a single spelling
# matches all the vocalised variants that appear in the King Fahd edition
# (وَسُئِلَ، وسُئل، سُئِلَ ...). Hamza seats are kept, so "فأجاب" still reads "فأجاب".
# ---------------------------------------------------------------------------

# Question openers: "وسئل" / "سئل" optionally followed by honorifics.
Q_START = re.compile(r"^\s*(?:و)?سئل\b")
# Answer openers: "فأجاب" / "وأجاب" / bare "أجاب"; the [جح] class also accepts
# the source typo "فأحاب" (vol 33 p.246 in the Shamela text).
A_START = re.compile(r"^\s*(?:ف|و)?أ[جح]اب\b")
# A bare "الجواب" line that just labels the answer section (drop as a header).
JAWAB_HEADER = re.compile(r"^\s*الجواب\s*[:：]?\s*$")
# "الجواب: <answer text>" — label AND answer content on the same paragraph.
JAWAB_INLINE = re.compile(r"^\s*الجواب\b[\s:：]*\S")
_JAWAB_LABEL_TRIM = re.compile(r"^\s*الجواب\b[\s:：]*")
# A "قال السائل" prefix inside the question body (kept, prefix stripped).
SAIL_PREFIX = re.compile(r"^\s*(?:و)?قال\s+السائل\s*[:：]?\s*")
# New non-Q&A treatise/statement opener — ends the current answer.
TREATISE_START = re.compile(r"^\s*(?:و)?قال\s+شيخ\s+الإسلام\b")

# Opener-label markers that identify the "(و)سئل شيخ الإسلام ... - رحمه الله -:"
# preamble so we can tell a label-colon from a colon inside the question itself.
_LABEL_HINT = re.compile(r"سئل|رحمه\s+الله|قدس\s+الله|رضي\s+الله|الشيخ|شيخ\s+الإسلام")
# Fallback opener trim when the label has no terminating colon (question starts
# with "عن ..."): strip "(و)سئل" plus any label words up to the honorific dash.
_Q_OPENER_NOCOLON = re.compile(r"^\s*(?:و)?سئل\b(?:[^:：\n]*?[-–—]\s*)?")
# Strip the answer-opener label: "فأجاب:", "فأجاب - رحمه الله -:", "أجاب الشيخ...:".
# Honorific/label text is consumed only up to a colon; a content-opener like
# "فأجاب بأن هذا لا يجوز" keeps everything after the verb.
_A_LEAD_TRIM = re.compile(
    r"^\s*(?:ف|و)?أ[جح]اب\b"
    r"(?:\s*[-–—]?\s*(?:رحمه|قدس|رضي|شيخ|الشيخ)[^:：\n]{0,60}[:：]"
    r"|\s*[-–—]*\s*[:：]?)\s*"
)
# Editorial footnote markers from the print edition, e.g. "(*)".
_FOOTNOTE_MARK = re.compile(r"\(\s*\*+\s*\)")


@dataclass
class Fatwa:
    id: str
    volume: int
    page_start: int
    page_end: int
    category: str            # top-level kitab heading (e.g. "كتاب التوحيد")
    topic: str               # deepest heading available
    treatise: str            # risala from the front-matter index, if any
    heading_path: list[str]
    question_ar: str
    answer_ar: str
    question_en: str = ""
    answer_en: str = ""
    q_chars: int = 0
    a_chars: int = 0
    inferred: bool = False   # answer boundary reconstructed (no فأجاب marker in print)


def _norm(text: str) -> str:
    return strip_tashkeel(text).strip()


# Generic structural headings that carry no topical meaning on their own.
_GENERIC_HEADING = re.compile(
    r"^(?:فصل|مسألة|تتمة|فائدة|تنبيه|خاتمة|مقدمة|الجواب|وسئل|سئل|قاعدة|و?قال)\b"
)


def _clean_heading(h: str) -> str:
    return _FOOTNOTE_MARK.sub("", h).strip(" :：،.-–—[]\n")


def _pick_topic(path: list[str]) -> str:
    """Deepest heading that actually names a subject (skip bare 'فصل' etc.)."""
    for h in reversed(path):
        hc = _clean_heading(h)
        if hc and not _GENERIC_HEADING.match(strip_tashkeel(hc)):
            return hc
    return _clean_heading(path[-1]) if path else ""


def _pick_category(path: list[str]) -> str:
    """Top-level 'كتاب/باب ...' heading when present, else the first heading
    that names a real subject (skipping bare 'سئل'/'فصل'/... openers)."""
    for h in path:
        hc = _clean_heading(h)
        if hc.startswith("كتاب") or hc.startswith("باب"):
            return hc
    for h in path:
        hc = _clean_heading(h)
        if hc and not _GENERIC_HEADING.match(strip_tashkeel(hc)):
            return hc
    return ""


def _clean_question(paras: list[str]) -> str:
    joined = "\n".join(paras).strip()
    # Case A: the opener label ends in a colon within the first ~220 chars, and
    # the text before that colon clearly reads as a label ("سئل ... رحمه الله").
    head = joined[:220]
    m = re.search(r"[:：]", head)
    if m and _LABEL_HINT.search(joined[:m.start()]):
        joined = joined[m.end():]
    else:
        # Case B: no label-colon — question begins right after the honorific.
        joined = _Q_OPENER_NOCOLON.sub("", joined, count=1)
    joined = SAIL_PREFIX.sub("", joined, count=1)
    joined = _FOOTNOTE_MARK.sub("", joined)
    return joined.strip(" :،-–—*\n")


def _clean_answer(paras: list[str]) -> str:
    joined = "\n".join(paras).strip()
    joined = _A_LEAD_TRIM.sub("", joined, count=1)
    joined = _FOOTNOTE_MARK.sub("", joined)
    return joined.strip(" :،-–—*\n")


def extract_with_pages(paras: list[Para], treatise_index: dict) -> list[Fatwa]:
    fatwas: list[Fatwa] = []
    counter = 0
    state = "SEEK"
    q_buf: list[str] = []
    a_buf: list[str] = []
    meta: Para | None = None
    page_start = 0
    page_end = 0

    def flush():
        nonlocal counter, q_buf, a_buf, meta, state, page_start, page_end
        inferred = False
        # Salvage: a substantial question with no marked answer is (in every
        # audited case) a fatwa whose answer follows the question with no
        # فأجاب marker in print. Recover it: the paragraph after the opener is
        # the question, the rest is the answer. Short/1-para leftovers (e.g. a
        # quoted hadith "سئل: أي الأعمال أفضل؟") are still discarded.
        if (meta is not None and q_buf and not a_buf
                and len(q_buf) >= 3 and sum(len(x) for x in q_buf) >= 500):
            a_buf = q_buf[2:]
            q_buf = q_buf[:2]
            inferred = True
        if meta is not None and q_buf and a_buf:
            question = _clean_question(q_buf)
            answer = _clean_answer(a_buf)
            if question and answer and len(answer) >= 2:
                path = meta.heading_path or []
                treatise = ""
                for s, e, title in treatise_index.get(meta.volume, []):
                    if s <= page_start <= e:
                        treatise = title
                        break
                fatwas.append(Fatwa(
                    id=f"itq_{counter:05d}",
                    volume=meta.volume,
                    page_start=page_start,
                    page_end=max(page_end, page_start),
                    category=_pick_category(path),
                    topic=_pick_topic(path),
                    treatise=_clean_heading(treatise),
                    heading_path=[_clean_heading(h) for h in path],
                    question_ar=question,
                    answer_ar=answer,
                    q_chars=len(question),
                    a_chars=len(answer),
                    inferred=inferred,
                ))
                counter += 1
        q_buf, a_buf, meta = [], [], None
        state = "SEEK"

    for p in paras:
        norm = _norm(p.text)
        if not norm:
            continue
        is_q = bool(Q_START.match(norm))
        is_a = bool(A_START.match(norm))
        is_treatise = bool(TREATISE_START.match(norm))

        if is_q:
            flush()
            state = "Q"
            meta = p
            q_buf = [p.text]
            a_buf = []
            page_start = p.page
            page_end = p.page
            continue

        if state == "Q":
            if is_treatise:
                # A treatise begins mid-question: close out (salvage if
                # substantial) rather than swallowing the treatise as question.
                flush()
                continue
            page_end = max(page_end, p.page)
            if is_a:
                state = "A"
                a_buf = [p.text]
            elif JAWAB_HEADER.match(norm):
                continue
            elif JAWAB_INLINE.match(norm):
                # "الجواب: <text>" — label and answer share the paragraph.
                state = "A"
                a_buf = [_JAWAB_LABEL_TRIM.sub("", p.text, count=1)]
            else:
                q_buf.append(p.text)
            continue

        if state == "A":
            if is_treatise:
                flush()
            else:
                page_end = max(page_end, p.page)
                a_buf.append(p.text)
            continue

    flush()
    return fatwas


def build_paragraph_stream(path=None) -> tuple[list[Para], dict]:
    path = path or config.RAW_TEXT_FILE
    text = path.read_text(encoding="utf-8")
    body = text.split("#META#Header#End#", 1)[1] if "#META#Header#End#" in text else text
    logical = to_logical_lines(body)
    logical = assign_pages(logical)
    paras = build_paragraphs(logical)
    treatise_index = build_treatise_index(paras)
    return paras, treatise_index


def write_web_bundle(records: list[dict]) -> None:
    """Emit web/data/fatwas.json — the UI subset the static frontend loads.
    Folds in any English translations already produced in fatwas_en.json so the
    English mode is populated as translation progresses (keyed by fatwa id)."""
    web_dir = config.BASE_DIR / "web" / "data"
    web_dir.mkdir(parents=True, exist_ok=True)

    en_cache_path = config.PROCESSED_DIR / "fatwas_en.json"
    en_cache: dict = {}
    if en_cache_path.exists():
        try:
            en_cache = json.loads(en_cache_path.read_text(encoding="utf-8"))
        except Exception:
            en_cache = {}

    ui = []
    n_translated = 0
    for r in records:
        en = en_cache.get(r["id"], {})
        q_en = en.get("question_en", "")
        a_en = en.get("answer_en", "")
        if a_en:
            n_translated += 1
        ui.append({
            "id": r["id"],
            "v": r["volume"],
            "ps": r["page_start"],
            "pe": r["page_end"],
            "cat": r["category"],
            "topic": r["topic"],
            "qa": r["question_ar"],
            "aa": r["answer_ar"],
            "qe": q_en,
            "ae": a_en,
        })

    meta = {
        "author_ar": "شيخ الإسلام ابن تيمية",
        "author_en": "Shaykh al-Islam Ibn Taymiyyah",
        "work_ar": "مجموع الفتاوى",
        "work_en": "Majmuʿ al-Fatawa",
        "edition": config.WORK_EDITION,
        "count": len(ui),
        "translated": n_translated,
    }
    out = web_dir / "fatwas.json"
    out.write_text(json.dumps({"meta": meta, "fatwas": ui}, ensure_ascii=False),
                   encoding="utf-8")
    print(f"Wrote {out}  ({len(ui)} fatwas, {n_translated} with English)")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    config.ensure_dirs()

    paras, treatise_index = build_paragraph_stream()
    fatwas = extract_with_pages(paras, treatise_index)

    # Stats
    by_vol: dict[int, int] = {}
    for f in fatwas:
        by_vol[f.volume] = by_vol.get(f.volume, 0) + 1

    print(f"Total fatwa Q&A pairs extracted: {len(fatwas)}")
    print("Per-volume counts:")
    for v in sorted(by_vol):
        print(f"  vol {v:02d}: {by_vol[v]}")

    with_treatise = sum(1 for f in fatwas if f.treatise)
    print(f"\nLabelled with a treatise/topic: {with_treatise}/{len(fatwas)} "
          f"({with_treatise / max(1, len(fatwas)):.0%})")
    inferred = [f for f in fatwas if f.inferred]
    print(f"Answer boundary inferred (no فأجاب in print): {len(inferred)}"
          + (": " + ", ".join(f"{f.id}(v{f.volume} p{f.page_start})" for f in inferred)
             if inferred else ""))
    avg_q = sum(f.q_chars for f in fatwas) / max(1, len(fatwas))
    avg_a = sum(f.a_chars for f in fatwas) / max(1, len(fatwas))
    print(f"Avg question length: {avg_q:.0f} chars | Avg answer length: {avg_a:.0f} chars")

    out_json = config.PROCESSED_DIR / "fatwas.json"
    out_jsonl = config.PROCESSED_DIR / "fatwas.jsonl"
    records = [asdict(f) for f in fatwas]
    out_json.write_text(json.dumps(records, ensure_ascii=False, indent=None), encoding="utf-8")
    with out_jsonl.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nWrote {out_json}")
    print(f"Wrote {out_jsonl}")

    # Web-optimised bundle (UI fields only) consumed by the static frontend.
    write_web_bundle(records)

    print("\n--- SAMPLE FATWAS ---")
    for f in fatwas[:3]:
        print(f"\n[{f.id}] vol {f.volume} p.{f.page_start}-{f.page_end} | topic: {f.topic or f.treatise or '(none)'}")
        print("Q:", f.question_ar[:200].replace("\n", " "))
        print("A:", f.answer_ar[:200].replace("\n", " "))


if __name__ == "__main__":
    main()
