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

  Before any of that can help, the two spellings have to be brought onto common
  ground, and four places where they were not cost the site real verses:

  | Uthmani | is | was read as |
  |---|---|---|
  | `ٱلنَّبِيِّـۧنَ` `إِبۡرَٰهِـۧمَ` `يُحۡيِۦ` | `النبيين` `إبراهيم` `يحيي` | `النبين` `ابراهم` `يحي` |
  | `هَدَىٰنَا` `ٱلتَّوۡرَىٰةَ` `أَدۡرَىٰكَ` | `هدانا` `التوراة` `أدراك` | `هدينا` `التوريه` `ادريك` |
  | `ٱلصَّلَوٰةَ` `ٱلۡحَيَوٰةِ` `ٱلرِّبَوٰا۟` | `الصلاة` `الحياة` `الربا` | `الصلواه` `الحيواه` `الربواا` |
  | `۞` `۩` and one thin space | nothing | themselves |

  A small ya is the pronoun only in a word-final `هِۦ`; everywhere else it is a
  ya the printed text writes out. A dagger alef on an alef maqsura is a reading
  mark at the end of a word and a written alef as soon as a suffix follows. A
  dagger on a waw is a written alef only in the closed set that ends in a tāʾ
  marbūṭa or al-ribā's silent alef — `ٱلسَّمَٰوَٰت` really is `السماوات`.

  A quotation under the three-word floor is now identified too, if it occurs
  **exactly once** in the whole Qur'an — `{وإياي فارهبون}` is two words, is
  al-Baqarah 2:40, and is nowhere else. Uniqueness is the guarantee the word
  count was standing in for; `{قال الله}` still says nothing.

  Together these took identification from 8,848 to **9,613** quotations. Al
  ʿImrān 3:79 and 3:80 were being called narrations in all twelve places they
  are quoted, because both carry `النبيين` or `ربانيين`.

  Every one of the 9,613 was then checked against an independent copy of the
  text — the complete Uthmani edition from
  [alquran.cloud](https://alquran.cloud/api), fetched once — and **none is the
  wrong verse**: 9,545 appear in the claimed verse word for word, and the other
  68 are the same verse with a word in the other orthography, or quoted without
  its opening word, or with its basmala. Searching that same independent text
  for every span still marked a narration turns up **no verse the matcher is
  missing**.

### Which brace is which, in the translation

The edition marks every quotation in the Arabic, and `scan_arabic` says what
each one is. The translator keeps some of those braces and drops others, but
never reorders them — so the English braces are a *subsequence* of the Arabic
ones, and which is which is settled by aligning the two sequences in order
rather than guessing again from the English.

This matters because the old code did guess, and then asserted the guess.
An English quotation it could not place was marked **narration** — so Ash-Sharḥ
94:7, al-Māʾidah 5:44 and al-Baqarah 2:186 were all shown to the reader as
narrations in the translation while the Arabic beside them carried the right
citation. Failing to place a quotation is not evidence that it is not scripture.

The alignment agrees with 469 of the references the old code was confident
about, and resolves 536 of its false "narration" labels. English placement is
back to 56.2% and is now inherited from the Arabic rather than re-derived.

## Source & licensing

Text: OpenITI corpus (openly licensed scholarly editions). The underlying work by
Ibn Taymiyyah (d. 728 AH / 1328 CE) is public domain. Respect OpenITI's license
and cite the edition when redistributing.
