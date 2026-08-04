"""Write one static page per fatwa, plus a sitemap.

The search application is a single page that routes with #f/<id>. A fragment is
never sent to a server and no crawler treats it as a page of its own, so every
one of the extracted fatawa -- the whole substance of the site -- is invisible
to anyone who does not already know the site exists. And a reader arriving from
a search engine would wait on a 30 MB corpus before seeing a word.

So each fatwa also gets a real page: its Arabic and its English in the markup,
its quotations marked and linked exactly as the application marks them, and its
own URL. About 20 KB instead of 9 MB, indexable, and readable with JavaScript
switched off. The application is unchanged; it simply stops being the only way
in.

    .venv\\Scripts\\python scripts\\prerender.py

Set SITE_URL to the domain before publishing -- it is what the canonical and
Open Graph tags point at, and a wrong one is worse than none.
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
from datetime import date
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
DATA = WEB / "data"
OUT = WEB / "f"

# Where the site will live. The deploy workflow passes this in from GitHub's
# own Pages configuration, so it is right for a project site, a user site or a
# custom domain without anyone remembering to edit a constant. Locally it falls
# back to the dev server, which is only ever used for looking at the pages.
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8777").rstrip("/")
CSS_V = "?v=3"
SITE_CSS_V = "?v=5"

AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
BRACED, NARRATION = 0, -1
QUOTE_MARK = re.compile(r"['\"‘’“”]")
SENTENCE = re.compile(r"[^.!?؟؛]+[.!?؟؛]*\s*")

e = html.escape
ar_num = lambda n: str(n).translate(AR_DIGITS)


def cite_en(f) -> str:
    pages = f"p. {f['ps']}" if f["ps"] == f["pe"] else f"pp. {f['ps']}–{f['pe']}"
    return f"Vol. {f['v']} · {pages}"


def cite_ar(f) -> str:
    pages = (f"ص {ar_num(f['ps'])}" if f["ps"] == f["pe"]
             else f"ص {ar_num(f['ps'])}–{ar_num(f['pe'])}")
    return f"المجلد {ar_num(f['v'])} · {pages}"


def balanced(s: str) -> bool:
    return s.count("{") == s.count("}")


def paragraph_ranges(text: str, target: int = 620):
    """The same breaks the reading view makes, as ranges into the original."""
    src = text or ""
    pieces = []
    for m in SENTENCE.finditer(src):
        if not m.group(0):
            continue
        s, end = m.start(), m.end()
        while end - s > target * 2:
            seg = src[s:min(end, s + target)]
            cut = -1
            for ch in ("،", ",", " "):
                i = seg.rfind(ch)
                if i > target * 0.4:
                    cut = s + i + 1
                    break
            if cut < 0 or not balanced(src[s:cut]):
                break
            pieces.append((s, cut))
            s = cut
        pieces.append((s, end))
    if not pieces:
        return [(0, len(src))]
    # Tile the whole string, from 0 to the end, whatever SENTENCE did with it.
    # That pattern wants a non-terminator before any terminator, so a run of
    # terminators standing on its own matches nothing at all -- which is how the
    # stray second ؟ ending five of the edition's questions was being dropped
    # from the page. Anchoring both ends makes losing a character impossible
    # rather than unlikely: the ranges are contiguous by construction, so if
    # they start at 0 and finish at len(src) they cover every character between.
    out, start = [], 0
    for _, pe in pieces:
        if pe - start >= target and balanced(src[start:pe]):
            out.append((start, pe))
            start = pe
    if len(src) > start:
        out.append((start, len(src)))
    return out


def mark_runs(text: str, s: int, en_: int, kind, runs, refs, lang: str) -> str:
    """The body of a quotation not identified as scripture entire, with the run
    inside it that *is* scripture ruled in gold and named."""
    bs, be = s, en_
    if kind == BRACED:
        while bs < be and (text[bs].isspace() or text[bs] == '{'):
            bs += 1
        while be > bs and (text[be - 1].isspace() or text[be - 1] == '}'):
            be -= 1
    out, last = [], bs
    for rs, r_end, r_idx in runs:
        if r_idx >= len(refs) or rs < last or r_end > be:
            continue
        r = refs[r_idx]
        out.append(e(text[last:rs]))
        label = r["ar"] if lang == "ar" else r["en"]
        out.append(f'<a class="ayah" href="{e(r["u"])}" target="_blank"'
                   f' rel="noopener" title="{e(r["en"] + " — " + r["t"])}">'
                   f'{e(text[rs:r_end])}<sup class="qref">{e(label)}</sup></a>')
        last = r_end
    out.append(e(text[last:be]))
    return "".join(out)


def quotation(inner: str, ref, lang: str, quoted_before: bool, quoted_after: bool,
              body_html: str = "") -> str:
    """One quotation, marked as the application marks it."""
    body = body_html or e(inner)
    if ref is not None:
        label = ref["ar"] if lang == "ar" else ref["en"]
        open_m = "﴿" if lang == "ar" else ("" if quoted_before else "“")
        close_m = "﴾" if lang == "ar" else ("" if quoted_after else "”")
        title = e(f"{ref['en']} — {ref['t']}")
        return (f'<a class="ayah" href="{e(ref["u"])}" target="_blank" rel="noopener"'
                f' title="{title}">{open_m}{body}{close_m}'
                f'<sup class="qref">{e(label)}</sup></a>')
    words = [w for w in inner.split() if w]
    n_open = "" if quoted_before else "«"
    n_close = "" if quoted_after else "»"
    if len(words) < 3:
        return f"{n_open}{body}{n_close}"
    label = "حديث؟" if lang == "ar" else "narration"
    title = ("ليست من القرآن. اطلبها في sunnah.com — بحثٌ لا عزو."
             if lang == "ar" else
             "Not Qur’ān. Searches sunnah.com for these words — a search, not a citation.")
    url = "https://sunnah.com/search?q=" + quote(" ".join(words[:12]))
    # A quotation carrying a verse inside it holds a link of its own, and an
    # anchor cannot be nested in an anchor. There the quotation is a span and
    # the lookup moves to its label.
    if body_html:
        lookup = (f'<a class="narration-ref" href="{url}" target="_blank"'
                  f' rel="noopener" title="{e(title)}">{label}</a>')
        return (f'<span class="narration">{n_open}{body}{n_close}'
                f'<sup class="qref">{lookup}</sup></span>')
    return (f'<a class="narration" href="{url}" target="_blank" rel="noopener"'
            f' title="{e(title)}">{n_open}{body}{n_close}'
            f'<sup class="qref">{label}</sup></a>')


def render(text: str, spans, refs, lang: str, offset: int = 0, used=None) -> str:
    """A slice of text with the quotations falling inside it marked."""
    if not spans:
        return e(text)
    out, last = [], 0
    for span in spans:
        s0, e0, ref_idx, kind = span[:4]
        runs = span[4] if len(span) > 4 else None
        s, en_ = s0 - offset, e0 - offset
        if s < last or s < 0 or en_ > len(text):
            continue
        out.append(e(text[last:s]))
        raw = text[s:en_]
        inner = raw.strip()[1:-1].strip() if kind == BRACED else raw
        before = (text[max(0, s - 2):s].strip() or " ")[-1]
        after = (text[en_:en_ + 2].strip() or " ")[0]
        ref = refs[ref_idx] if ref_idx >= 0 and ref_idx < len(refs) else None
        # the runs arrive in whole-passage coordinates, like the span itself,
        # and this call is working on one paragraph of it
        local = [[a - offset, b - offset, i] for a, b, i in (runs or [])]
        marked = (mark_runs(text, s, en_, kind, local, refs, lang)
                  if ref is None and local else "")
        out.append(quotation(inner, ref, lang,
                             bool(QUOTE_MARK.match(before)),
                             bool(QUOTE_MARK.match(after)), marked))
        if used is not None:
            if ref_idx >= 0:
                used.add(ref_idx)
            for r in (runs or []):
                used.add(r[2])
        last = en_
    out.append(e(text[last:]))
    return "".join(out)


def block(text: str, spans, refs, lang: str, kind: str, used) -> str:
    """One block of the passage, paragraph by paragraph."""
    cls = f"read-{'ar' if lang == 'ar' else 'en'} {lang}"
    if kind == "a":
        cls += " answer"
    attrs = ' lang="ar" dir="rtl"' if lang == "ar" else ""
    parts = []
    for s, en_ in paragraph_ranges(text or ""):
        parts.append(f'<p class="{cls}"{attrs}>'
                     f'{render((text or "")[s:en_], spans, refs, lang, s, used)}</p>')
    # Joined with nothing at all: whitespace between the tags would become a
    # text node, and the text of this page must stay character-for-character
    # what the edition prints. Long lines are a fair price for that.
    return "".join(parts)


NAV = """<nav class="nav">
  <a class="nav-brand" href="../index.html">
    <span class="mark" aria-hidden="true">﴿</span>
    <span class="name en">MAJMŪʿ</span>
    <span class="name ar" lang="ar">المجموع</span>
  </a>
  <form class="bar-seek" action="../search.html" method="get" role="search" autocomplete="off">
    <div class="field-wrap">
      <span class="ico" aria-hidden="true">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.3-4.3"></path></svg>
      </span>
      <input class="input" type="search" name="q" spellcheck="false" aria-label="Search the fatāwā" />
    </div>
    <button type="submit" class="btn btn-primary"><span class="en">Search</span><span class="ar" lang="ar">ابحث</span></button>
  </form>
  <div class="langswitch" role="group" aria-label="Language / اللغة">
    <button type="button" data-lang-btn="en" aria-pressed="true">English</button>
    <button type="button" data-lang-btn="ar" lang="ar" aria-pressed="false">العربية</button>
  </div>
  <button type="button" class="btn nightswitch" data-theme-btn aria-label="Night reading / القراءة الليلية">
    <svg class="i-day" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"></path></svg>
    <svg class="i-night" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z"></path></svg>
  </button>
</nav>"""

FOOT = """<hr class="rule" />
  <footer>
    <span class="en">Printed text from <em>Majmūʿ al-Fatāwā</em>, King Fahd Complex edition (1416 AH / 1995 CE), from the OpenITI corpus. The English is a machine translation provided for reading only; where it differs from the Arabic, the Arabic is what the Shaykh wrote. This is a research and retrieval tool: it surfaces what Ibn Taymiyyah wrote, with the source, and issues no rulings of its own.</span>
    <span class="ar" lang="ar">نصٌّ مطبوع من «مجموع الفتاوى»، طبعة مجمع الملك فهد (١٤١٦هـ / ١٩٩٥م)، من ذخيرة OpenITI. والترجمة الإنجليزية آليةٌ للاستئناس فقط، فإن خالفت العربية فالعربية هي ما كتبه الشيخ. وهذه أداة بحثٍ واستخراج، تُظهر ما كتبه ابن تيمية بعزوه، ولا تُفتي من نفسها.</span>
  </footer>"""

SCRIPT = """<script>
(() => {
  const root = document.documentElement, body = document.body;
  const setLang = (lang, persist) => {
    body.dataset.lang = lang;
    root.lang = lang;
    root.dir = lang === 'ar' ? 'rtl' : 'ltr';
    for (const b of document.querySelectorAll('[data-lang-btn]'))
      b.setAttribute('aria-pressed', String(b.dataset.langBtn === lang));
    const i = document.querySelector('input[name="q"]');
    if (i) i.dir = lang === 'ar' ? 'rtl' : 'ltr';
    if (persist) { try { localStorage.setItem('majmu:lang', lang); } catch (e) {} }
  };
  const setTheme = (t, persist) => {
    root.dataset.theme = t;
    document.querySelector('meta[name="theme-color"]')
      .setAttribute('content', t === 'night' ? '#201f1d' : '#f3f2f2');
    if (persist) { try { localStorage.setItem('majmu:theme', t); } catch (e) {} }
  };
  let lang = null, theme = null;
  try { lang = localStorage.getItem('majmu:lang'); theme = localStorage.getItem('majmu:theme'); } catch (e) {}
  setLang(lang === 'ar' ? 'ar' : 'en');
  setTheme(theme === 'night' ? 'night' : 'day');
  for (const b of document.querySelectorAll('[data-lang-btn]'))
    b.addEventListener('click', () => setLang(b.dataset.langBtn, true));
  for (const b of document.querySelectorAll('[data-theme-btn]'))
    b.addEventListener('click', () => setTheme(root.dataset.theme === 'night' ? 'day' : 'night', true));
})();
</script>"""


def snippet(text: str, limit: int = 155) -> str:
    t = re.sub(r"\s+", " ", (text or "")).strip()
    if len(t) <= limit:
        return t
    cut = t.rfind(" ", 0, limit)
    return t[:cut if cut > limit * 0.6 else limit].rstrip() + "…"


def page(f, cites, neighbours) -> str:
    refs = cites.get("refs", []) if cites else []
    used: set[int] = set()
    fid = f["id"]
    heading = f.get("topic") or f.get("cat") or "فتوى"
    title_text = snippet(f.get("qe") or f.get("qa") or heading, 70)
    title = f"{title_text} — Majmūʿ al-Fatāwā {cite_en(f)}"
    desc = snippet(f.get("qe") or f.get("qa") or "")
    url = f"{SITE_URL}/f/{fid}.html"

    def spans(key, lang):
        b = (cites or {}).get(key) or {}
        return b.get("ar" if lang == "ar" else "en")

    body_blocks = []
    for key, ar_field, en_field, label_en, label_ar in (
        ("q", "qa", "qe", "The question", "السؤال"),
        ("a", "aa", "ae", "The answer", "الجواب"),
    ):
        parts = [f'<div class="read-block">',
                 f'<span class="fatwa-label en">{label_en}</span>',
                 f'<span class="fatwa-label ar" lang="ar">{label_ar}</span>',
                 block(f.get(ar_field), spans(key, "ar"), refs, "ar", key, used)]
        if f.get(en_field):
            parts.append(block(f.get(en_field), spans(key, "en"), refs, "en", key, used))
        parts.append("</div>")
        body_blocks.append("".join(parts))

    ayah_links = "".join(
        f'<a href="{e(r["u"])}" target="_blank" rel="noopener" title="{e(r["t"])}">'
        f'<span class="en">{e(r["en"])}</span>'
        f'<span class="ar" lang="ar">{e(r["ar"])}</span></a>'
        for r in refs)
    unknown = sum((cites.get(k) or {}).get("u", 0) for k in ("q", "a")) if cites else 0
    rail_note = ""
    if unknown:
        rail_note = (f'<span class="quiet en">· {unknown} further quotation'
                     f'{"" if unknown == 1 else "s"} not identified as Qur’ān — '
                     f'marked in the text, searchable on sunnah.com.</span>'
                     f'<span class="quiet ar" lang="ar">· و{ar_num(unknown)} من النقول '
                     f'لم تُعرَف قرآناً، موسومةٌ في النص، تُطلب في sunnah.com.</span>')
    rail = ""
    if ayah_links or rail_note:
        tag = ('<span class="tag tag-outline"><span class="en">Qur’ān</span>'
               '<span class="ar" lang="ar">قرآن</span></span>') if ayah_links else ""
        rail = f'<div class="ayahs">{tag}{ayah_links}{rail_note}</div>'

    prev_f, next_f = neighbours
    nearby = []
    if prev_f:
        nearby.append(f'<a class="nearby" href="{prev_f["id"]}.html">'
                      f'<span class="nearby-cite en">← {e(cite_en(prev_f))}</span>'
                      f'<span class="nearby-cite ar" lang="ar">→ {e(cite_ar(prev_f))}</span>'
                      f'<span class="nearby-q" lang="ar" dir="rtl">'
                      f'{e(snippet(prev_f.get("qa"), 88))}</span></a>')
    if next_f:
        nearby.append(f'<a class="nearby" href="{next_f["id"]}.html">'
                      f'<span class="nearby-cite en">{e(cite_en(next_f))} →</span>'
                      f'<span class="nearby-cite ar" lang="ar">{e(cite_ar(next_f))} ←</span>'
                      f'<span class="nearby-q" lang="ar" dir="rtl">'
                      f'{e(snippet(next_f.get("qa"), 88))}</span></a>')
    if nearby:
        rail += ('<div class="rail-block">'
                 '<span class="fatwa-label en">In this volume</span>'
                 '<span class="fatwa-label ar" lang="ar">في هذا المجلد</span>'
                 + "".join(nearby) + "</div>")

    cat = f.get("cat") or ""
    # The section of the edition this sits in -- a kitab, a bab, a sura,
    # sometimes a risala. "Treatise" was wrong for nearly all of it: 482 of
    # these are أبواب and 41 are كتب against a handful of actual rasa'il, so
    # the label claimed a kind of text the field mostly does not hold and a
    # reader was shown "Treatise: سورة التوبة", which a sura is not.
    section = ""
    if cat:
        section = (f'<span class="en">Section: </span>'
                    f'<span class="ar" lang="ar">القسم: </span>'
                    f'<a class="linklike" lang="ar" dir="rtl"'
                    f' href="../search.html?cat={quote(cat)}">{e(cat)}</a>')

    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "ScholarlyArticle",
        "headline": title_text,
        "inLanguage": ["ar", "en"],
        "isPartOf": {"@type": "Book", "name": "Majmūʿ al-Fatāwā",
                     "author": {"@type": "Person", "name": "Ibn Taymiyyah"}},
        "author": {"@type": "Person", "name": "Ibn Taymiyyah"},
        "url": url,
        "description": desc,
    }, ensure_ascii=False)

    return f"""<!doctype html>
<html lang="en" dir="ltr">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}" />
<meta name="theme-color" content="#f3f2f2" />
<link rel="canonical" href="{url}" />
<meta property="og:type" content="article" />
<meta property="og:title" content="{e(title_text)}" />
<meta property="og:description" content="{e(desc)}" />
<meta property="og:url" content="{url}" />
<meta property="og:site_name" content="MAJMŪʿ" />
<link rel="icon" href="../favicon.svg?v=2" type="image/svg+xml" />
<link rel="preload" href="../fonts/lora-latin-400.woff2" as="font" type="font/woff2" crossorigin />
<link rel="preload" href="../fonts/amiri-arabic-400.woff2" as="font" type="font/woff2" crossorigin />
<link rel="stylesheet" href="../ds/fonts.css?v=1" />
<link rel="stylesheet" href="../ds/arabic.css?v=3" />
<script type="speculationrules">
{{"prerender":[{{"where":{{"href_matches":"/f/*"}},"eagerness":"moderate"}}],
  "prefetch":[{{"where":{{"href_matches":"/search.html*"}},"eagerness":"moderate"}}]}}
</script>
<link rel="stylesheet" href="../ds/classical.css{CSS_V}" />
<link rel="stylesheet" href="../ds/site.css{SITE_CSS_V}" />
<script type="application/ld+json">{jsonld}</script>
</head>
<body data-lang="en">
<a class="skip" href="#passage"><span class="en">Skip to the passage</span><span class="ar" lang="ar">تخطَّ إلى النص</span></a>
{NAV}
<div class="wrap">
  <article class="reading" id="passage">
    <div class="reading-bar">
      <a class="btn btn-secondary" href="../search.html?vol={f['v']}">
        <span class="en">Volume {f['v']}</span><span class="ar" lang="ar">المجلد {ar_num(f['v'])}</span></a>
      <span class="spacer"></span>
      <a class="btn btn-ghost" href="../search.html">
        <span class="en">Search the fatāwā</span><span class="ar" lang="ar">ابحث في الفتاوى</span></a>
    </div>
    <div class="reading-head">
      <div class="result-meta">
        <span class="cite en">{e(cite_en(f))}</span>
        <span class="cite ar" lang="ar">{e(cite_ar(f))}</span>
        {section}
      </div>
      <h1 lang="ar" dir="rtl">{e(heading)}</h1>
    </div>
    <div class="reading-body">
      {body_blocks[0]}
      {body_blocks[1]}
      <div class="colophon">
        <span class="mark" aria-hidden="true">﴾ ۞ ﴿</span>
        <span class="en"> Majmūʿ al-Fatāwā · {e(cite_en(f))} · King Fahd Complex edition</span>
        <span class="ar" lang="ar"> مجموع الفتاوى · {e(cite_ar(f))} · طبعة مجمع الملك فهد</span>
      </div>
    </div>
    <aside class="reading-rail">{rail}</aside>
  </article>
  {FOOT}
</div>
{SCRIPT}
</body>
</html>
"""


def main() -> int:
    # The whole corrected corpus, from the build directory rather than web/ --
    # the pages need every word, but the site never serves the file itself.
    data = json.loads((ROOT / "data" / "build" / "fatwas.json").read_text(encoding="utf-8"))
    cites = json.loads((DATA / "citations.json").read_text(encoding="utf-8"))
    fatwas = data["fatwas"]

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    # neighbours: the passage before and after, in the order the edition prints
    by_volume: dict[int, list] = {}
    for f in fatwas:
        by_volume.setdefault(f["v"], []).append(f)
    for v in by_volume:
        by_volume[v].sort(key=lambda x: (x["ps"], x["pe"]))
    position = {}
    for v, items in by_volume.items():
        for i, f in enumerate(items):
            position[f["id"]] = (items[i - 1] if i else None,
                                 items[i + 1] if i + 1 < len(items) else None)

    total_bytes = 0
    for f in fatwas:
        out = page(f, cites.get(f["id"]), position[f["id"]])
        path = OUT / f"{f['id']}.html"
        path.write_text(out, encoding="utf-8")
        total_bytes += len(out.encode("utf-8"))

    today = date.today().isoformat()
    urls = [f"{SITE_URL}/", f"{SITE_URL}/search.html", f"{SITE_URL}/life.html"]
    urls += [f"{SITE_URL}/f/{f['id']}.html" for f in fatwas]
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        priority = "1.0" if u.endswith("/") else "0.7"
        sitemap.append(f"  <url><loc>{u}</loc><lastmod>{today}</lastmod>"
                       f"<priority>{priority}</priority></url>")
    sitemap.append("</urlset>")
    (WEB / "sitemap.xml").write_text("\n".join(sitemap) + "\n", encoding="utf-8")

    # robots.txt carries an absolute sitemap URL, so it is generated here from
    # the same SITE_URL rather than kept as a second place to get it wrong.
    (WEB / "robots.txt").write_text(
        "# MAJMŪʿ — the fatāwā of Ibn Taymiyyah, searchable.\n"
        "# The pages are meant to be found and read. The corpus files behind\n"
        "# them are data, not pages: crawling them costs 30 MB and indexes\n"
        "# nothing readable. /vendor/ is the same: two map libraries and a\n"
        "# world outline that life.html draws its coastline from.\n\n"
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /data/\n"
        "Disallow: /vendor/\n\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n",
        encoding="utf-8")

    print(f"wrote {len(fatwas)} pages to {OUT}")
    print(f"  {total_bytes / 1024 / 1024:.1f} MB total, "
          f"{total_bytes / len(fatwas) / 1024:.0f} KB average per page")
    print(f"wrote {WEB / 'sitemap.xml'} ({len(urls)} urls)")
    print(f"wrote {WEB / 'robots.txt'}")
    print(f"site url: {SITE_URL}")
    if "localhost" in SITE_URL:
        print("\n  NOTE: built against the dev server. The deploy workflow sets")
        print("  SITE_URL from GitHub Pages, so published pages get the real one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
