# Corrections

The English on this site is machine translation and the Qur'anic citations are
matched automatically. Both are usually right. When one is wrong, the fix goes
here — not into the corpus — so that it survives the next time the corpus is
rebuilt.

Anything in this folder is applied **last**, over the machine's output, every
time the site is built. Add a `.json` file, open a pull request, and the fix is
live when it merges.

## The shape of a correction

```json
{
  "itq_00042": {
    "by": "your name",
    "why": "one line on what was wrong",

    "replace": [
      { "field": "ae", "find": "the exact wrong words", "with": "the right words" }
    ],

    "quotations": [
      { "quote": "the quotation exactly as the passage prints it",
        "is": "narration",
        "why": "opens with a Qur'anic phrase but is a hadith" }
    ]
  }
}
```

Use **one file per person or per batch** (`madara.json`, `volume-31.json`) so
two people are never editing the same file. Correcting the same fatwa in two
files is an error — the build says so rather than picking one.

### Fixing a translation

`replace` takes the wrong words and the right ones. `find` must appear **exactly
once** in that field; if it appears twice, include enough surrounding text to
pick out the one you mean.

```json
"replace": [{ "field": "ae", "find": "a medium between us", "with": "an intermediary between us" }]
```

`set` replaces a whole field, for when a rendering is beyond patching:

```json
"set": { "ae": "the entire corrected English answer" }
```

Correctable fields: `qe` and `ae` (the machine translation), `topic` and `cat`
(metadata), `qa` and `aa` (the printed Arabic — **only** for a transcription
error in the source, never to smooth or modernise the text).

### Fixing a citation

`quotations` says what a quoted passage really is. Copy the quotation exactly as
the passage prints it, without the `{ }`.

- `"is": "narration"` — the matcher called it Qur'an and it is not. This happens
  where a hadith opens with a Qur'anic phrase.
- `"is": "22:75"` — it *is* that āyah and the matcher missed it. A range works
  too: `"7:35-36"`.

## Rules the build enforces

A correction that no longer applies is an error, not a shrug. If the corpus is
republished and the text a correction points at has changed, the build stops and
names the file, the fatwa and the text it could not find. The deploy fails and
the live site stays as it was.

That is deliberate. The alternative — skipping quietly — means corrections rot
while everyone assumes the page has been checked, which is worse than no
corrections at all.

So the build refuses when: the fatwa id is unknown; `find` matches zero times or
more than once; a quotation is not in that passage; an āyah reference is
malformed or does not exist; a field is not correctable; or the same fatwa is
corrected in two files.

## Checking your work

```bash
.venv\Scripts\python scripts\build_web_data.py    # applies corrections, or explains why not
.venv\Scripts\python scripts\prerender.py         # rebuilds the pages
```

Then open `web/f/<id>.html` and read the passage you corrected.

`example.json` is a worked example that changes nothing on the page — it asserts
an āyah the matcher already finds, so the mechanism is exercised on every build.
Delete it once there are real corrections.
