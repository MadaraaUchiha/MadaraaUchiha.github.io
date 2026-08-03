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

  A **fourth reading** then gives up three more distinctions, each a place where
  the two orthographies simply disagree and neither is wrong — and each enough
  on its own to make a verse quoted word for word read as a narration:

  | | Uthmani | printed | verse it cost |
  |---|---|---|---|
  | the hamza seat | `وَإِيتَآئِ` | `وإيتاء` | al-Naḥl 16:90 |
  | the open tāʾ | `نِعۡمَتَ` | `نعمة` | Fāṭir 35:3 |
  | the doubled letter | `ٱلَّيۡلَ` | `الليل` | al-Anbiyāʾ 21:33 |

  It is the loosest reading and the last one tried, so an exact match always
  wins ahead of it. What keeps it honest is that the whole quotation must still
  appear, in order, in a third of a million letters.

  Together these took identification from 8,848 to **10,043** quotations. Al
  ʿImrān 3:79 and 3:80 were being called narrations in all twelve places they
  are quoted, because both carry `النبيين` or `ربانيين`.

  Every one of the 10,043 was then checked against an independent copy of the
  text — the complete Uthmani edition from
  [alquran.cloud](https://alquran.cloud/api), fetched once — and **none is the
  wrong verse**: 10,039 appear in the claimed verse word for word and the other
  four are the same verse with a word spelled the other way.

  As a second audit, every quotation the Shaykh introduces with `قال تعالى` or
  its like — 10,503 of them — was checked for how much of it is verbatim
  Qur'an. The ones still called a narration while reading mostly as scripture
  fell from 232 to **19**, and at least three of those nineteen are correctly
  narrations: `{من كان يؤمن بالله واليوم الآخر فليقل خيرا أو ليصمت}` opens with
  six words of al-Ṭalāq 65:2 and is a hadith, which is what the coverage guard
  is for.

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
about, and resolves its false "narration" labels. English placement is now
inherited from the Arabic rather than re-derived, and only **7%** of braced
English quotations are still called narrations, down from most of them.

Similarity is measured as how much of the **quotation** the verse accounts for,
not how much of the verse the quotation covers. The Shaykh quotes the clause he
is arguing from, not the whole āyah: `{Who is it that intercedes with Him except
by His permission?}` is eleven words of al-Baqarah 2:255, which runs to ninety.
Measuring against the whole verse scored that at 0.11, lost it to the flat
narration score, and printed a verse quoted in part as though it were not
scripture at all. That direction cannot be gamed the other way — a short verse
cannot claim a long quotation, because the words it fails to account for count
against it.

## Source & licensing

Text: OpenITI corpus (openly licensed scholarly editions). The underlying work by
Ibn Taymiyyah (d. 728 AH / 1328 CE) is public domain. Respect OpenITI's license
and cite the edition when redistributing.
