"""Human corrections, applied over machine output.

The English is machine translation and the Qur'anic citations are matched
automatically. Both are usually right and sometimes wrong, and the wrong ones
can only be found by a person reading the page. This module is what makes that
reading worth doing: a correction lives in a small file in the repository, is
applied last in the build, and therefore survives every rebuild of the corpus.

Without it, a colleague who fixes a mistranslation loses the fix the next time
the corpus is republished, and there is no point asking anyone to look.

A correction file is JSON, keyed by fatwa id. Any number of files may live in
corrections/; they are merged.

    {
      "itq_00002": {
        "by": "Madara",
        "why": "wasitah rendered as 'medium'; it is an intermediary",
        "replace": [
          {"field": "ae", "find": "a medium between", "with": "an intermediary between"}
        ],
        "quotations": [
          {"quote": "من كان يؤمن بالله واليوم الآخر فليقل خيرا أو ليصمت",
           "is": "narration",
           "why": "opens with six words of 65:2 but is a hadith"}
        ]
      }
    }

  replace     targeted find/with. `find` must occur exactly once in the field.
  set         wholesale replacement of a field. The escape hatch; prefer replace.
  quotations  what a quoted passage really is: "narration", or "S:A" / "S:A-B"
              to assert an ayah the matcher missed or got wrong.

Fields that may be corrected: qe, ae (the machine translation), topic, cat
(metadata), and qa, aa (the printed Arabic -- only for a transcription error in
the source, never to smooth the text).

A correction that no longer applies is an error, not a shrug: if the corpus is
republished and the text a correction targets has changed, the build says so
and stops. Silence there would mean corrections quietly rotting while everyone
assumes the page has been checked.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

CORRECTABLE = {"qe", "ae", "qa", "aa", "topic", "cat"}
ARABIC_FIELDS = {"qa", "aa"}
AYAH_RE = re.compile(r"^\d{1,3}:\d{1,3}(-\d{1,3})?$")


class CorrectionError(Exception):
    pass


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


class Corrections:
    """Every correction in the repository, indexed by the fatwa it applies to."""

    def __init__(self, entries: dict[str, dict], sources: dict[str, str]):
        self.entries = entries
        self.sources = sources          # fatwa id -> file it came from
        self.applied = 0
        self.quotation_overrides: dict[str, dict[str, str]] = {}

    @classmethod
    def load(cls, directory: Path) -> "Corrections":
        entries: dict[str, dict] = {}
        sources: dict[str, str] = {}
        if not directory.exists():
            return cls(entries, sources)
        for path in sorted(directory.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise CorrectionError(f"{path.name}: not valid JSON -- {exc}") from exc
            if not isinstance(data, dict):
                raise CorrectionError(f"{path.name}: expected an object keyed by fatwa id")
            for fid, entry in data.items():
                if fid in entries:
                    raise CorrectionError(
                        f"{path.name}: {fid} is already corrected in {sources[fid]}. "
                        f"Merge the two entries so there is one place to read.")
                entries[fid] = entry
                sources[fid] = path.name
        return cls(entries, sources)

    # ---------------------------------------------------------------- text --
    def apply_to(self, fatwas: list[dict], quran=None) -> list[str]:
        """Rewrite the corpus in place. Returns a line per correction applied."""
        by_id = {f["id"]: f for f in fatwas}
        log: list[str] = []

        for fid, entry in self.entries.items():
            where = self.sources[fid]
            f = by_id.get(fid)
            if f is None:
                raise CorrectionError(
                    f"{where}: {fid} is not in the corpus. Either the id is wrong "
                    f"or the correction outlived the passage it corrected.")

            for item in entry.get("replace", []):
                field, find, with_ = item.get("field"), item.get("find"), item.get("with")
                if field not in CORRECTABLE:
                    raise CorrectionError(
                        f"{where}: {fid} cannot correct {field!r}; "
                        f"correctable fields are {sorted(CORRECTABLE)}")
                if not find or with_ is None:
                    raise CorrectionError(f"{where}: {fid} replace needs 'find' and 'with'")
                text = f.get(field) or ""
                hits = text.count(find)
                if hits == 0:
                    raise CorrectionError(
                        f"{where}: {fid}.{field} no longer contains {find[:60]!r}. "
                        f"The corpus changed under this correction -- re-check the "
                        f"passage and update or remove it.")
                if hits > 1:
                    raise CorrectionError(
                        f"{where}: {fid}.{field} contains {find[:60]!r} {hits} times. "
                        f"Give enough surrounding text to pick out one.")
                f[field] = text.replace(find, with_)
                self.applied += 1
                log.append(f"  {fid}.{field}: {find[:44]!r} -> {with_[:44]!r}  [{where}]")

            for field, value in (entry.get("set") or {}).items():
                if field not in CORRECTABLE:
                    raise CorrectionError(
                        f"{where}: {fid} cannot set {field!r}; "
                        f"correctable fields are {sorted(CORRECTABLE)}")
                if not isinstance(value, str):
                    raise CorrectionError(f"{where}: {fid}.{field} must be set to a string")
                f[field] = value
                self.applied += 1
                log.append(f"  {fid}.{field}: replaced whole field ({len(value)} chars)  [{where}]")

            for item in entry.get("quotations", []):
                quote, is_ = item.get("quote"), item.get("is")
                if not quote or not is_:
                    raise CorrectionError(f"{where}: {fid} quotation needs 'quote' and 'is'")
                if is_ != "narration" and not AYAH_RE.match(is_):
                    raise CorrectionError(
                        f"{where}: {fid} quotation 'is' must be \"narration\" or "
                        f"\"surah:ayah\" (e.g. \"22:75\"), not {is_!r}")
                # Resolve the ayah now, while there is still a file name and a
                # fatwa id to name in the message. Left until the scan, a bad
                # reference surfaces as a bare traceback from somewhere else.
                if is_ != "narration" and quran is not None:
                    try:
                        ayah_reference(quran, is_)
                    except CorrectionError as exc:
                        raise CorrectionError(f"{where}: {fid} quotation -- {exc}") from exc
                key = norm_ws(quote)
                # the quotation has to actually be in the passage, or the
                # correction is describing something that is not there
                haystack = norm_ws((f.get("qa") or "") + " " + (f.get("aa") or ""))
                if key not in haystack:
                    raise CorrectionError(
                        f"{where}: {fid} has no quotation reading {quote[:60]!r}. "
                        f"Copy it exactly as the passage prints it.")
                self.quotation_overrides.setdefault(fid, {})[key] = is_
                self.applied += 1
                log.append(f"  {fid}: quotation -> {is_}  [{where}]")

        return log

    def override_for(self, fid: str, quote: str) -> str | None:
        """"narration", "S:A", or None if this quotation was never corrected."""
        return self.quotation_overrides.get(fid, {}).get(norm_ws(quote))


def ayah_reference(quran, spec: str):
    """Build a citation for an ayah asserted by hand, e.g. "22:75"."""
    surah_s, ayah_s = spec.split(":")
    surah = int(surah_s)
    start_s, _, end_s = ayah_s.partition("-")
    start, end = int(start_s), int(end_s or start_s)
    verses = [a for a in quran.ayat
              if a["surah"] == surah and start <= a["ayah"] <= end]
    if not verses:
        raise CorrectionError(f"{spec} is not an ayah of the Qur'an")
    first = verses[0]
    return {
        "surah": surah,
        "surah_name": first["surah_name"],
        "translit": first["translit"],
        "start": start,
        "end": end,
        "arabic": " ".join(v["ar"] for v in verses),
        "english": " ".join(v["en"] for v in verses),
        "url": f"https://quran.com/{surah}/{start}",
    }
