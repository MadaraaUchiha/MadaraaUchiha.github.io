# 📖 Islamic Knowledge Engine

A citation-grounded search and research tool over classical Islamic scholarship,
starting with **Ibn Taymiyyah's _Majmu' al-Fatawa_** (King Fahd Complex edition,
ed. Ibn Qasim, 1416/1995).

> **This is a research/retrieval tool, not a mufti.** It surfaces what Ibn
> Taymiyyah actually wrote, with sources. It does not issue rulings of its own.
> Always verify against the original Arabic.

---

## What works today

- **Corpus**: the **35 volumes of text** in _Majmu' al-Fatawa_ (16,436 passages),
  which is the whole of the work — the King Fahd printing is 37 volumes, but 36
  and 37 are its indexes and contain no fatawa. The source has no pages for
  them, the retrieval index has no passages from them, and the edition's own
  index of treatises never once refers to them.
  sourced as clean machine-readable text from the [OpenITI corpus](https://openiti.org)
 
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

## Source & licensing

Text: OpenITI corpus (openly licensed scholarly editions). The underlying work by
Ibn Taymiyyah (d. 728 AH / 1328 CE) is public domain. Respect OpenITI's license
and cite the edition when redistributing.
