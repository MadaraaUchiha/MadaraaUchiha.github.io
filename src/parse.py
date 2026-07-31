"""Parse OpenITI mARkdown -> structured passages with volume/page/heading metadata.

OpenITI mARkdown conventions handled here:
  * Header block ends at the line `#META#Header#End#`.
  * `# ...`   begins a logical line (paragraph).
  * `~~...`   continues the previous logical line (word-wrap).
  * `### |..` is a structural heading; the number of `|` is the nesting level.
  * `PageVxxPyyy` marks the END of printed volume xx, page yyy. All text up to
    and including the line bearing the tag belongs to that page.

Run:  python -m src.parse
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field, asdict

from src import config
from src.arabic import PAGE_TAG, strip_markers

HEAD_RE = re.compile(r"^###\s*(\|*)\s*(.*)$")
BRACKETS = re.compile(r"^\[(.*)\]$")
# Front-matter index entries, e.g. "- الإيمان الكبير 7 / 5 - 460"
INDEX_ENTRY = re.compile(r"^[-–]?\s*(.+?)\s+(\d{1,2})\s*/\s*(\d{1,3})\s*[-–]\s*(\d{1,4})\s*$")
# Multi-volume entries (no page range), e.g. "تفسير ... 13 / 14 / 15 / 16 / 17"
MULTI_VOL = re.compile(r"^[-–]?\s*(.+?)\s+(\d{1,2}(?:\s*/\s*\d{1,2}){2,})\s*$")


@dataclass
class LogicalLine:
    kind: str          # "para" | "head"
    raw: str           # text with page tags still embedded
    level: int = 1     # heading level (heads only)
    text: str = ""     # text with page tags removed
    vol: int = 0
    page: int = 0


@dataclass
class Passage:
    id: str
    volume: int
    page_start: int
    page_end: int
    heading_path: list[str]
    text_ar: str
    treatise: str = ""
    char_len: int = 0
    work: str = config.WORK_TITLE
    author: str = config.WORK_AUTHOR
    edition: str = config.WORK_EDITION


# ---------------------------------------------------------------------------
# Stage 1: raw lines -> logical lines (joining ~~ continuations)
# ---------------------------------------------------------------------------
def to_logical_lines(body: str) -> list[LogicalLine]:
    lines: list[LogicalLine] = []
    cur: LogicalLine | None = None
    for raw in body.splitlines():
        if not raw.strip():
            cur = None
            continue
        if raw.startswith("~~"):
            if cur is not None:
                cur.raw += " " + raw[2:].strip()
            continue
        if raw.startswith("###"):
            m = HEAD_RE.match(raw)
            level = max(1, len(m.group(1))) if m and m.group(1) else 1
            cur = LogicalLine(kind="head", raw=raw, level=level)
            lines.append(cur)
        elif raw.startswith("#"):
            cur = LogicalLine(kind="para", raw=raw[1:].strip())
            lines.append(cur)
        else:
            # stray line — treat as continuation if we have an open line
            if cur is not None:
                cur.raw += " " + raw.strip()
    return lines


# ---------------------------------------------------------------------------
# Stage 2: assign volume/page using "tag marks end of page" semantics
# ---------------------------------------------------------------------------
def assign_pages(lines: list[LogicalLine]) -> list[LogicalLine]:
    out: list[LogicalLine] = []
    run: list[LogicalLine] = []
    last_v, last_p = 0, 0
    for ll in lines:
        tags = PAGE_TAG.findall(ll.raw)
        ll.text = strip_markers(ll.raw)
        ll.text = re.sub(r"\s+", " ", ll.text).strip()
        if ll.text:
            run.append(ll)
        if tags:
            v, p = int(tags[-1][0]), int(tags[-1][1])
            last_v, last_p = v, p
            for r in run:
                r.vol, r.page = v, p
                out.append(r)
            run = []
    for r in run:                       # trailing text after the last tag
        r.vol, r.page = last_v, last_p
        out.append(r)
    return out


def clean_heading(text: str) -> str:
    text = text.strip()
    m = BRACKETS.match(text)
    if m:
        text = m.group(1).strip()
    return text


# ---------------------------------------------------------------------------
# Stage 3: logical lines -> paragraph records carrying a heading path
# ---------------------------------------------------------------------------
@dataclass
class Para:
    volume: int
    page: int
    heading_path: list[str]
    text: str


def build_paragraphs(lines: list[LogicalLine]) -> list[Para]:
    paras: list[Para] = []
    stack: dict[int, str] = {}
    for ll in lines:
        if ll.kind == "head":
            m = HEAD_RE.match(ll.text)
            title = clean_heading(m.group(2)) if m else clean_heading(ll.text)
            if not title:
                continue
            stack[ll.level] = title
            for deeper in [k for k in stack if k > ll.level]:
                del stack[deeper]
        else:
            path = [stack[k] for k in sorted(stack)]
            paras.append(Para(ll.vol, ll.page, path, ll.text))
    return paras


# ---------------------------------------------------------------------------
# Treatise index: map (volume, page) -> the risala/book it belongs to,
# using the table of contents in the front matter (volume 0).
# ---------------------------------------------------------------------------
def build_treatise_index(paras: list[Para]) -> dict[int, list[tuple[int, int, str]]]:
    by_vol: dict[int, list[tuple[int, int, str]]] = {}
    for p in paras:
        if p.volume != 0:
            continue
        m = INDEX_ENTRY.match(p.text)
        if m:
            title, vol, start, end = m.group(1).strip(), int(m.group(2)), int(m.group(3)), int(m.group(4))
            if end >= start and len(title) >= 3:
                by_vol.setdefault(vol, []).append((start, end, title))
            continue
        mv = MULTI_VOL.match(p.text)
        if mv:
            title = mv.group(1).strip()
            vols = [int(x) for x in re.findall(r"\d{1,2}", mv.group(2))]
            if len(title) >= 3 and all(1 <= v <= 40 for v in vols):
                for v in vols:                        # whole-volume coverage
                    by_vol.setdefault(v, []).append((1, 99999, title))
    # Narrowest (most specific) treatise first, so it wins over whole-volume ones.
    for v in by_vol:
        by_vol[v].sort(key=lambda r: r[1] - r[0])
    return by_vol


def assign_treatises(passages: list[Passage], index: dict[int, list[tuple[int, int, str]]]) -> None:
    for p in passages:
        for start, end, title in index.get(p.volume, []):
            if start <= p.page_start <= end:
                p.treatise = title
                break


# ---------------------------------------------------------------------------
# Stage 4: chunk paragraphs into retrieval passages
# ---------------------------------------------------------------------------
_SENT_SPLIT = re.compile(r"(?<=[\.؟!])\s+")


def split_long(text: str) -> list[str]:
    parts, buf = [], ""
    for sent in _SENT_SPLIT.split(text):
        if buf and len(buf) + len(sent) > config.CHUNK_TARGET_CHARS:
            parts.append(buf.strip())
            buf = sent
        else:
            buf = (buf + " " + sent).strip()
        while len(buf) > config.CHUNK_MAX_CHARS:          # hard fallback
            parts.append(buf[:config.CHUNK_MAX_CHARS])
            buf = buf[config.CHUNK_MAX_CHARS:]
    if buf.strip():
        parts.append(buf.strip())
    return parts


def chunk(paras: list[Para]) -> list[Passage]:
    passages: list[Passage] = []
    counter = 0

    buf: list[Para] = []
    buf_chars = 0

    def flush():
        nonlocal buf, buf_chars, counter
        if not buf:
            return
        text = "\n".join(p.text for p in buf).strip()
        if not text:
            buf, buf_chars = [], 0
            return
        vol = buf[0].volume
        p_start = min(p.page for p in buf)
        p_end = max(p.page for p in buf)
        pid = f"v{vol:02d}_p{p_start:03d}_{counter:05d}"
        passages.append(Passage(
            id=pid, volume=vol, page_start=p_start, page_end=p_end,
            heading_path=buf[0].heading_path, text_ar=text, char_len=len(text),
        ))
        counter += 1
        buf, buf_chars = [], 0

    cur_head: list[str] | None = None
    for p in paras:
        if cur_head is not None and p.heading_path != cur_head:
            flush()
        cur_head = p.heading_path

        if len(p.text) > config.CHUNK_MAX_CHARS:
            flush()
            for piece in split_long(p.text):
                counter_piece = Para(p.volume, p.page, p.heading_path, piece)
                buf = [counter_piece]
                buf_chars = len(piece)
                flush()
            continue

        if buf_chars + len(p.text) > config.CHUNK_TARGET_CHARS and buf_chars >= config.CHUNK_MIN_CHARS:
            flush()
        buf.append(p)
        buf_chars += len(p.text)
    flush()
    return passages


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def parse_file(path=None) -> list[Passage]:
    path = path or config.RAW_TEXT_FILE
    text = path.read_text(encoding="utf-8")
    if "#META#Header#End#" in text:
        body = text.split("#META#Header#End#", 1)[1]
    else:
        body = text
    logical = to_logical_lines(body)
    logical = assign_pages(logical)
    paras = build_paragraphs(logical)
    treatise_index = build_treatise_index(paras)
    passages = chunk(paras)
    assign_treatises(passages, treatise_index)
    return passages


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    config.ensure_dirs()
    passages = parse_file()

    # Per-volume stats
    by_vol: dict[int, int] = {}
    for p in passages:
        by_vol[p.volume] = by_vol.get(p.volume, 0) + 1
    print(f"Total passages parsed: {len(passages)}")
    print("Passages per volume (first 10):")
    for v in sorted(by_vol)[:10]:
        print(f"  vol {v:02d}: {by_vol[v]} passages")

    if config.TARGET_VOLUME is not None:
        passages = [p for p in passages if p.volume == config.TARGET_VOLUME]
        print(f"\nFiltered to volume {config.TARGET_VOLUME}: {len(passages)} passages")

    with config.PASSAGES_FILE.open("w", encoding="utf-8") as f:
        for p in passages:
            f.write(json.dumps(asdict(p), ensure_ascii=False) + "\n")
    print(f"Wrote {config.PASSAGES_FILE}")

    with_treatise = sum(1 for p in passages if p.treatise)
    print(f"Passages labelled with a treatise: {with_treatise}/{len(passages)} "
          f"({with_treatise / max(1, len(passages)):.0%})")

    # Sample for eyeballing
    print("\n--- SAMPLE PASSAGES ---")
    for p in passages[:3]:
        print(f"[{p.id}] vol {p.volume} p.{p.page_start}-{p.page_end} | "
              f"treatise: {p.treatise or '(none)'}")
        print(p.text_ar[:300].replace("\n", " "))
        print()


if __name__ == "__main__":
    main()
