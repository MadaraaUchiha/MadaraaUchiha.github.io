# 📖 Islamic Knowledge Engine

A citation-grounded search and research tool over classical Islamic scholarship,
starting with **Ibn Taymiyyah's _Majmu' al-Fatawa_** (King Fahd Complex edition,
ed. Ibn Qasim, 1416/1995).

It lets you ask a question in **English or Arabic** and get the most relevant
passages from the original Arabic text, plus an optional AI answer that may
**only** quote from those passages — with exact volume/page citations and
on-demand scholar-grade translation.

> **This is a research/retrieval tool, not a mufti.** It surfaces what Ibn
> Taymiyyah actually wrote, with sources. It does not issue rulings of its own.
> Always verify against the original Arabic.

---

## What works today

- **Corpus**: all **37 volumes** of _Majmu' al-Fatawa_ (16,436 passages),
  sourced as clean machine-readable text from the [OpenITI corpus](https://openiti.org)
  (no OCR needed — see "Design decisions"). Embedding the whole book takes ~3
  minutes on an RTX 3060 Ti.
- **Hybrid retrieval**: dense semantic search (BGE-M3, multilingual) + BM25
  lexical search, fused with Reciprocal Rank Fusion. Arabic and English queries
  both hit the Arabic text (cross-lingual embeddings).
- **Citations + treatise labels**: every result shows the exact volume/page and,
  where available, which risāla/treatise it comes from (parsed from the
  front-matter index).
- **Qur'an citation recognition** (`src/quran.py`): every `{...}` quotation is
  matched against the full Qur'an, identified to the exact Sūrah:āyah, shown with
  its authoritative English translation, and linked to quran.com. Quotations that
  aren't Qur'an (e.g. hadith) are left unlabelled rather than guessed.

  The Qur'an file is Uthmani; Ibn Taymiyyah's text is imlā'ī, and they spell the
  same words differently. Matching reads the text three ways, each blind to one
  more difference and no others: as written, then ignoring where words were
  split (Uthmani joins `يَٰبَنِيٓ`, the printed text writes `يا بني`), then
  ignoring the alefs the two disagree about in *both* directions (`مَلَـٰٓئِكَة`
  wants one written, `أُو۟لَٰٓئِكَ` does not). Together these took identification
  from 14,531 to 19,552 āyāt across the corpus, **+35%**.

  Guarding the other way matters more: a quotation is only named after a verse
  if the matched run covers ≥80% of it. Many hadith open with a Qur'anic phrase
  and continue in the Prophet's own words — "من كان يؤمن بالله واليوم الآخر
  فليقل خيرا أو ليصمت" begins with six words of al-Talaq 65:2 and is not that
  verse. `scripts/` has no test runner, but `test_quran.py` covers the happy
  path and the fixtures in the build were checked against ten well-known
  narrations, none of which may resolve to scripture.
- **Fluent English translation** (`src/translate.py`): a per-passage toggle (on
  results *and* similar passages) translates the whole passage with a **free
  LLM** (Google Gemini 2.5 Flash by default — free key, no credit card). It reads
  naturally because it translates with context, keeps technical terms, and drops
  in the **authoritative English of any Qur'an verses** so scripture is exact.
  Cached so each passage is translated once. Falls back to a local NLLB model
  (rough "gist") if no key is set, so the app always works offline.
- **Find similar passages** (`Retriever.similar`): jump from any result to its
  closest neighbours anywhere in the 37 volumes, by meaning.
- **UI**: a static bilingual site in `web/` (the "Classical" design system), a
  Streamlit reader (`app.py`), and a CLI.

### Enable fluent translation (free)
Get a free Gemini key (no card) at <https://aistudio.google.com/apikey>, copy
`.env.example` to `.env`, and set `GEMINI_API_KEY=...`. Verify with
`python scripts/test_translate_llm.py`. Alternatives (also free): set
`IKE_TRANSLATE_PROVIDER=groq` (+`GROQ_API_KEY`) or `openrouter` (+`OPENROUTER_API_KEY`).

A separate dormant Claude/Ollama layer (`src/rag.py`, `src/llm.py`) exists for
future source-grounded *answers* and is off unless you add `ANTHROPIC_API_KEY`.

---

## Setup

Already done if Claude set this up for you. From scratch:

```powershell
# 1. Create venv and install deps (built/tested on Python 3.14)
py -3.14 -m venv .venv
# GPU (NVIDIA): CUDA build of torch. CPU-only: skip this line (requirements.txt pulls CPU torch).
.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\python -m pip install -r requirements.txt

# 2. Download the source text (one file) into data/raw/  -- see scripts/ or OpenITI

# 3. Build the index for volume 1
.venv\Scripts\python -m src.parse      # raw text -> passages.jsonl
.venv\Scripts\python -m src.index      # passages -> embeddings + BM25
```

### Enable AI answers / translation (optional)

Copy `.env.example` to `.env` and either:
- **Claude (recommended):** set `ANTHROPIC_API_KEY=...`
- **Fully local (zero cloud):** install [Ollama](https://ollama.com), `ollama pull
  qwen2.5:7b-instruct`, and set `IKE_LLM_PROVIDER=ollama` in `.env`.

---

## Usage

```powershell
# The static site (landing + search), no server-side code
.venv\Scripts\python -m http.server 8777 --directory web

# Streamlit reader (hybrid retrieval, on-demand translation)
.venv\Scripts\streamlit run app.py

# CLI — AI answer (needs a key)
.venv\Scripts\python scripts\ask.py "Is it permissible to seek help from the dead?"

# CLI — pure search (no key needed)
.venv\Scripts\python scripts\ask.py --search "الاستغاثة بغير الله"
```

To index a different volume, set `IKE_TARGET_VOLUME` (or `config.TARGET_VOLUME`),
then re-run `src.parse` and `src.index`. Set it to `None` for the whole book.

---

## The static site (`web/`)

A two-page site that needs no backend: it loads the extracted fatāwā as JSON and
searches them in the browser. Bilingual throughout (English / العربية, LTR and
RTL), with a night ground.

```
web/
  index.html        the landing page
  search.html       the search application (shell + page CSS)
  search.js         search, filters, reading view, neighbours
  ds/classical.css  the Classical design system, vendored from the design
                    handoff — do not hand-edit, re-vendor instead
  data/fatwas.json      the extracted questions and answers (~30 MB)
  data/citations.json   Qur'an citations, precomputed  ┐ both written by
  data/stats.json       the counts the landing prints  ┘ build_web_data.py
  _legacy/          the previous single-page app, kept until the new site sticks
```

Every visual token (colour, type, spacing, radius, shadow) comes from
`ds/classical.css`; the pages add only layout, the 28px reading rhythm, the
Arabic face and their own states. State lives in the URL — `?q=` a question,
`?vol=` a volume read in page order, `?cat=` a treatise, `#f/<id>` one answer
opened for reading — so every view is linkable and the back button works.

Only one language is on screen at a time; the switch in the bar is what changes
it. A passage reads at a fixed measure with its citation, match, Qur'anic
references and actions set in the margin beside it, and answers that run for
pages are broken into paragraphs at sentence ends (never through a quotation).

### Where a quotation begins and ends

Every quotation is marked in whichever language is on screen, so it is clear
where the Shaykh stops speaking and the thing he is quoting starts:

| | Arabic | English | Links to |
|---|---|---|---|
| **Qur'an** | `﴿ … ﴾` ruled in gold, `الأعراف ٣٥` after it | `“ … ”` ruled in gold, `Al-A'raf 7:35` after it | quran.com, at that āyah |
| **Narration** | `« … »` on a broken rule, marked `حديث؟` | `« … »` on a broken rule, marked `narration` | a sunnah.com **search** |

The two are deliberately unalike: one is identified, the other is not. Without
a hadith corpus to match against, this build can only say "these are quoted
words, here is where to look them up" — the narration link is a search, never a
citation, and the tooltip says so in both languages. Identifying narrations to
collection and number is the [roadmap](#roadmap) item that would change that.

The spans are computed offline by `build_web_data.py` and shipped as character
offsets, so the page marks exactly what the build could prove and never guesses
in the browser. On the English side only two signals are trusted: the
translation kept the `{ }`, or a run of the authoritative translation occurs
**exactly once** in it (then grown outward while it still runs word for word).
That places about 57% of verses in the English prose; a verse the translator
paraphrased is left unmarked there rather than underlined at a guess, and still
appears by name in the margin index. The Arabic, which carries the edition's
own `{ }`, is marked in full.

### How the browser ranks (`search.js`)

The engine's semantic half needs embeddings and runs server-side, so this
client ranks lexically — but not by counting words, which would let a
40,000-character answer match anything. Four things decide a passage's place:

| | |
|---|---|
| **where** | a term in the heading or question weighs far more than one buried in the answer |
| **how near** | the tightest window containing the terms carries real weight — scattered words are not a subject |
| **how long** | every field is normalised by its length, and proximity inside an answer is normalised again |
| **aboutness** | a passage matching nothing in its heading or question is capped: it uses the words, it does not answer them |

The match figure is absolute, not a ranking: it saturates, so a strong passage
lands in the high eighties, a passing mention in the teens, and nothing is ever
called a perfect answer. A short glossary (`LEXICON`) carries the terms of art
in both directions — `help` also finds `الاستغاثة` — so an English question
reaches the Arabic. Any glossary word that turns out to be much commoner than
the word actually typed is dropped for that query, and a glossary hit always
counts for less than the reader's own word.

Rebuild the site's data and pages after re-extracting or re-translating:

```powershell
.venv\Scripts\python scripts\build_web_data.py   # corrections + citations + stats
.venv\Scripts\python scripts\prerender.py        # 1,675 pages + sitemap + robots.txt
```

### Corrections

The English is machine translation and the citations are matched automatically,
so both are sometimes wrong. Corrections live in `corrections/*.json` and are
applied **over** the machine's output on every build, which is what makes them
survive a rebuild of the corpus — see [corrections/README.md](corrections/README.md).

The corpus itself is never written to: `data/corpus/fatwas.json` is the
published input, and `web/data/fatwas.json` is that input with the corrections
in it. A correction that no longer applies fails the build rather than being
skipped, so the live site keeps its last good state instead of quietly losing
someone's fix.

Serve `web/` as static files. In production, send long cache headers for
`data/*.json` — `fatwas.json` is ~30 MB and is otherwise refetched per visit.
`search.js` and `ds/classical.css` are referenced with a `?v=` query; bump it
when either changes, or browsers will keep running the previous copy.

The superseded single-page app lives in `_legacy_web/` at the project root —
outside the served directory on purpose, so it cannot be reached by URL.

---

## Architecture

```
raw OpenITI text ─► parse.py ─► passages.jsonl
                                    │
                     ┌──────────────┴──────────────┐
                 index.py                       index.py
              (BGE-M3 dense)                  (BM25 lexical)
                     │                              │
                     └──────────► retrieve.py ◄─────┘   (RRF fusion)
                                       │
                          ┌────────────┴───────────┐
                       rag.py                  translate.py
                 (grounded answer)         (scholar-grade EN)
                          │                        │
                          └────────► app.py / ask.py
                                 (LLM provider: Claude | Ollama)
```

---

## Design decisions (what was cut from the original brief, and why)

The original brief was a 12-phase moonshot. Here is the honest triage:

| Brief phase | Status | Note |
|---|---|---|
| OCR @ 99.9% | **Cut** | Unnecessary — _Majmu' al-Fatawa_ already exists as clean machine-readable text (OpenITI/Shamela). OCR is kept only as a future module for scan-only books. |
| Translate the whole corpus up front | **Reshaped** | Translate **on demand** per retrieved passage, cached. Bulk-translating 20k pages is huge cost for text almost no one reads. |
| 4 separate search "layers" | **Unified** | Keyword + semantic + concept + position behaviors all fall out of one hybrid (BM25 + dense) engine. |
| Knowledge graph | **Deferred** | Real value, but only after retrieval is solid. v2. |
| Quran/Hadith integration | **Planned** | Will use existing quran.com / sunnah.com APIs rather than rebuilding. |
| "99.9% accuracy" guarantees | **Replaced** | Not a guaranteeable metric. Instead: always show the original Arabic so claims are verifiable, plus an honest retrieval-match score. |
| 100,000 books | **North star** | The pipeline is built so adding a book is repeatable; it is not a near-term deliverable. |

## Roadmap

- [x] Index all 37 volumes of _Majmu' al-Fatawa_.
- [x] Label passages with their containing treatise (front-matter index).
- [x] Qur'an citation recognition → surah:ayah + English + quran.com link.
- [x] On-demand local English translation (NLLB).
- [ ] **Hadith linking**: identify the brace-quotes that aren't Qur'an against a
  hadith corpus (sunnah.com), with collection + grading.
- [ ] **Cross-encoder re-ranking** (bge-reranker-v2-m3) for sharper top results.
- [ ] **More books** (Ibn al-Qayyim, al-Nawawi, ...) for comparative research.
- [ ] **Knowledge graph** over scholars / concepts / citations.
- [ ] (optional) Turn on LLM answers/scholarly translation by adding an API key.

---

## Source & licensing

Text: OpenITI corpus (openly licensed scholarly editions). The underlying work by
Ibn Taymiyyah (d. 728 AH / 1328 CE) is public domain. Respect OpenITI's license
and cite the edition when redistributing.
