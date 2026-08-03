"""Qur'an citation recognition.

Ibn Taymiyyah's text marks Qur'anic quotations with { }. This module identifies
the exact Surah and ayah(s) for each quotation by matching its normalized Arabic
against the full Qur'an, and returns the verse reference, the canonical Arabic,
an authoritative English translation, and a quran.com link.

Pure local string matching — instant, offline, no AI.
"""
from __future__ import annotations

import bisect
import json
import re
from dataclasses import dataclass
from functools import lru_cache

from src import config
from src.arabic import normalize_for_search

QURAN_FILE = config.RAW_DIR / "quran_en.json"
BRACES = re.compile(r"\{([^{}]+)\}")
MIN_WORDS = 3          # don't try to identify quotes shorter than this
MIN_CHARS = 12         # nor ones with too few letters to be sure of
FRAG_WORDS = 6         # a leading run may stand for the whole quotation...
FRAG_MIN_SHARE = 0.8   # ...only if it accounts for most of it. Plenty of hadith
#                        open with a Qur'anic phrase and carry on in the
#                        Prophet's own words -- "من كان يؤمن بالله واليوم
#                        الآخر فليقل خيرا أو ليصمت" opens with six words of
#                        al-Talaq 65:2 and is not that verse. Matching the
#                        longest prefix and insisting it cover most of the
#                        quotation keeps the narration a narration.

# The Qur'an file is Uthmani; Ibn Taymiyyah's text is imla'i. Uthmani writes
# some alifs as a superscript mark (mala'ikah as مَلَـٰٓئِكَة, not ملائكة) and the
# same for waw/ya, and normalize_for_search strips combining marks -- so the two
# spellings normalize to different strings and the quote is never found. Promote
# those marks to full letters on both sides first. Local to Qur'an matching:
# the BM25 index built on normalize_for_search is untouched.
_UTHMANI_LETTERS = str.maketrans({
    "ٰ": "ا",   # superscript alef: stands in for an alef the printed text writes
    "ۥ": "",    # small waw: lengthens the pronoun in هُۥ, which is plain ه here
    # ۞ and ۩ are the reciter's furniture, a rub-el-hizb marker and a place of
    # prostration. They sit at the edge of a verse and appear nowhere in the
    # printed fatawa, so a quotation running across a verse join trips on them.
    "۞": "",
    "۩": "",
    # one thin space, mid-verse in 2:72: typography inside a single word
    # (فَٱدَّٰرَ ٰتُمۡ), not a word break. It comes out.
    " ": "",
})

# Written with explicit code points: every one of these is invisible or
# combining, and a literal here is a character nobody can review.
#   064B-065F vowels, sukun, shadda, maddah, hamza above/below, subscript alef
#   0640      tatweel, which the Uthmani stretches a letter with
#   0670      the dagger alef
#   06D6-06DC 06DF-06E4 06E7-06ED  the reciter's pause and small-letter marks
_MARK = "\u064b-\u065f\u0640\u0670\u06d6-\u06dc\u06df-\u06e4\u06e7-\u06ed"
# The same, less the dagger alef: the two rules below look either side of a
# dagger, so their own classes must not swallow it.
_VOWEL = "\u064b-\u065f\u0640"

# An alef maqsura carrying a dagger alef is a long a. Standing at the end of a
# word the printed text writes it as an alef maqsura too --
#     ٱتَّقَىٰ    is اتقى
# -- but the moment a suffix follows, imla'i writes the alef out in full:
#     هَدَىٰنَا   is هدانا,   not هدينا
#     ٱلتَّوۡرَىٰةَ is التوراة, not التوريه
#     أَدۡرَىٰكَ   is أدراك,   not ادريك
# Dropping the dagger in both cases, as this did, put a ya where the printed
# text has an alef in 338 places, and no amount of matching afterwards recovers
# a letter that is simply the wrong one.
_MAQSURA_SUFFIXED = re.compile(
    rf"\u0649([{_VOWEL}]*)\u0670([{_VOWEL}]*)(?=[^\s{_MARK}])")

# The same trick with a waw. Uthmani writes the long a of a small closed set of
# words with a waw carrying a dagger --
#     ٱلصَّلَوٰة  is الصلاة, not الصلواه
#     ٱلےحَيَوٰة  is الحياة, not الحيواه
#     ٱلزَّكَوٰة  is الزكاة, not الزكواه
#     ٱلرِّبَوٰا  is الربا,  not الربواا
# It is emphatically NOT the general rule for a waw carrying a dagger:
# ٱلسَّمَٰوَٰت really is السماوات and وَٰحِدَة really is واحدة, both of
# which fold correctly already. What marks the set is what follows: a ta
# marbuta, or the silent alef of al-riba. 182 places.
_WAW_FOR_ALEF = re.compile(
    rf"و[{_VOWEL}]*ٰ[{_VOWEL}]*(?:ا|(?=ة))")

# What is left is the word-final case, and the same mark sitting on a full alef,
# where it really is only a reading mark on the letter it is on. Everywhere else
# a dagger stands in for an alef the Uthmani spelling leaves out, and
# _UTHMANI_LETTERS promotes it.
_DAGGER_ON_ALEF = re.compile(rf"([\u0627\u0649])([{_VOWEL}]*)\u0670")

# The small ya is two different things, and telling them apart is worth a letter
# on every verse that carries one.
#
#   هِۦ at the end of a word is the pronoun, lengthened for recitation. The
#   printed text writes it plain -- بِهِۦ is به -- so it comes out.
#
#   Anywhere else it stands in for a ya the printed text writes in full, and
#   dropping it costs the match a letter it will never get back:
#     ٱلنَّبِيِّـۧنَ  is النبيين, not النبين
#     إِبۡرَٰهِـۧمَ   is إبراهيم,  not ابراهم
#     يُحۡيِۦ        is يحيي,    not يحي
#     إِۦلَٰفِهِمۡ    is إيلافهم,  not الافهم
#   which is why Al 'Imran 3:79 and 3:80 -- both of them carrying النبيين or
#   ربانيين -- were read as narrations everywhere they are quoted.
#
# U+06E7 is the same mark in the small-high form; it never falls at the end of a
# word in this text, and always stands for a written ya.
_PRONOUN_YEH = re.compile(rf"(ه[{_VOWEL}]*)ۦ(?=[{_MARK}]*(?:\s|$))")
_SMALL_YEH = re.compile("[ۦۧ]")


def _fold(text: str) -> str:
    text = _MAQSURA_SUFFIXED.sub(r"ا\1\2", text)
    text = _WAW_FOR_ALEF.sub("ا", text)
    text = _DAGGER_ON_ALEF.sub(r"\1\2", text)
    text = _PRONOUN_YEH.sub(r"\1", text)
    text = _SMALL_YEH.sub("ي", text)
    return normalize_for_search(text.translate(_UTHMANI_LETTERS))


def _despace(text: str) -> str:
    return text.replace(" ", "")


def _skeleton(text: str) -> str:
    """Letters only, with the alefs dropped and the spaces closed up.

    Whether a long a is written as a letter is the single thing the two
    orthographies keep disagreeing about, and it disagrees in both directions:
    the Uthmani مَلَـٰٓئِكَة wants an alef the printed text writes, while its
    أُو۟لَٰٓئِكَ wants one the printed text does not. Removing alefs from both
    sides settles every such case at once. It costs a little discrimination,
    which is why this is the last resort and why a match still has to be the
    whole quotation, in order, in a corpus of a third of a million letters.
    """
    return _despace(text).replace("ا", "")


# Both spellings: the Uthmani writes the Merciful with a dagger alef and the
# printed fatawa write it out, so the two fold differently.
_BASMALA = tuple(_fold(s) for s in (
    "بسم الله الرحمن الرحيم",
    "بِسۡمِ ٱللَّهِ ٱلرَّحۡمَٰنِ ٱلرَّحِيمِ",
))


@dataclass
class QuranMatch:
    quote: str
    found: bool
    surah: int = 0
    surah_name_ar: str = ""
    surah_translit: str = ""
    ayah_start: int = 0
    ayah_end: int = 0
    arabic: str = ""
    english: str = ""
    url: str = ""

    @property
    def ref(self) -> str:
        a = f"{self.ayah_start}" if self.ayah_start == self.ayah_end \
            else f"{self.ayah_start}-{self.ayah_end}"
        return f"{self.surah}:{a}"


class QuranIndex:
    def __init__(self):
        data = json.loads(QURAN_FILE.read_text(encoding="utf-8"))
        self.ayat: list[dict] = []
        buf: list[str] = []
        self.starts: list[int] = []
        cursor = 0
        for s in data:
            for v in s["verses"]:
                self.ayat.append({
                    "surah": s["id"], "surah_name": s["name"],
                    "translit": s["transliteration"], "ayah": v["id"],
                    "ar": v["text"], "en": v.get("translation", ""),
                })
                norm = _fold(v["text"])
                if buf:
                    buf.append(" ")
                    cursor += 1
                self.starts.append(cursor)
                buf.append(norm)
                cursor += len(norm)
        self.joined = "".join(buf)

        # A second index with the spaces taken out. The Uthmani text joins some
        # words the printed fatawa separate (يَٰبَنِيٓ against يا بني), so a
        # quotation can be word-for-word right and still never align. Matching
        # without spaces is blind to exactly that difference and to nothing
        # else -- the letters must still agree, in order.
        self.joined_ns = _despace(self.joined)
        self.joined_sk = _skeleton(self.joined)
        self.starts_ns: list[int] = []
        self.starts_sk: list[int] = []
        run_ns = run_sk = 0
        for i, start in enumerate(self.starts):
            end = self.starts[i + 1] if i + 1 < len(self.starts) else len(self.joined)
            piece = self.joined[start:end]
            self.starts_ns.append(run_ns)
            self.starts_sk.append(run_sk)
            run_ns += len(_despace(piece))
            run_sk += len(_skeleton(piece))

    def _ayah_at(self, pos: int) -> int:
        return max(0, bisect.bisect_right(self.starts, pos) - 1)

    def _ayah_at_ns(self, pos: int) -> int:
        return max(0, bisect.bisect_right(self.starts_ns, pos) - 1)

    def _ayah_at_sk(self, pos: int) -> int:
        return max(0, bisect.bisect_right(self.starts_sk, pos) - 1)

    def _lookup(self, qnorm: str):
        """Where this quotation sits in the Qur'an, if it sits there at all.

        Three readings of the same text, each blind to one more difference
        between how the Qur'an is printed and how the fatawa quote it: as
        written, then ignoring where words were split, then ignoring the alefs
        the two orthographies disagree about. The quotation itself is tried
        before its opening fragment at every stage, so the exact reading always
        wins over the loose one.
        """
        words = qnorm.split()
        # Under the word floor, a quotation may still be identified -- but only
        # if it occurs exactly once in the whole Qur'an. Two words are usually
        # too little to be sure of, which is what the floor is for; but
        # {وإياي فارهبون} is two words, is al-Baqarah 2:40, and is nowhere else,
        # and refusing to say so served nobody. Uniqueness is the guarantee the
        # word count was standing in for.
        unique_only = len(words) < MIN_WORDS

        # The quotation itself, then its longest prefixes -- but only those long
        # enough to still be most of it.
        probes = [qnorm]
        # A verse quoted with the basmala in front of it. The basmala is only
        # numbered as an ayah in al-Fatiha, so everywhere else it pushes the
        # verse under the coverage floor and the whole quotation reads as a
        # narration -- which is what became of {بسم الله الرحمن الرحيم إنا
        # أعطيناك الكوثر}. Tried after the quotation itself, so it can only
        # ever add a match, never move one.
        for b in _BASMALA:
            if qnorm.startswith(b) and len(qnorm) > len(b) + MIN_CHARS:
                probes.append(qnorm[len(b):].strip())
                break
        floor = FRAG_MIN_SHARE * len(qnorm)
        for k in range(len(words) - 1, FRAG_WORDS - 1, -1):
            prefix = " ".join(words[:k])
            if len(prefix) < floor:
                break
            probes.append(prefix)

        for prep, hay, at in (
            (lambda s: s, self.joined, self._ayah_at),
            (_despace, self.joined_ns, self._ayah_at_ns),
            (_skeleton, self.joined_sk, self._ayah_at_sk),
        ):
            for probe in probes:
                needle = prep(probe)
                if len(needle) < MIN_CHARS:
                    continue
                pos = hay.find(needle)
                if pos < 0:
                    continue
                if unique_only and hay.find(needle, pos + 1) >= 0:
                    continue            # short and ambiguous: say nothing
                return at(pos), at(pos + len(needle) - 1)
        return None

    def identify(self, text: str) -> list[QuranMatch]:
        out: list[QuranMatch] = []
        seen: set = set()
        for m in BRACES.finditer(text):
            quote = m.group(1).strip()
            res = self._lookup(_fold(quote))
            if not res:
                key = ("?", quote[:30])
                if key not in seen:
                    seen.add(key)
                    out.append(QuranMatch(quote=quote, found=False))
                continue
            i0, i1 = res
            a0, a1 = self.ayat[i0], self.ayat[i1]
            if a0["surah"] != a1["surah"]:    # don't span across surahs
                i1, a1 = i0, a0
            key = (a0["surah"], a0["ayah"], a1["ayah"])
            if key in seen:
                continue
            seen.add(key)
            out.append(QuranMatch(
                quote=quote, found=True, surah=a0["surah"],
                surah_name_ar=a0["surah_name"], surah_translit=a0["translit"],
                ayah_start=a0["ayah"], ayah_end=a1["ayah"],
                arabic=" ".join(self.ayat[j]["ar"] for j in range(i0, i1 + 1)),
                english=" ".join(self.ayat[j]["en"] for j in range(i0, i1 + 1)),
                url=f"https://quran.com/{a0['surah']}/{a0['ayah']}",
            ))
        return out


@lru_cache(maxsize=1)
def get_quran() -> QuranIndex:
    return QuranIndex()
