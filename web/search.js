/* =========================================================================
   MAJMŪʿ — the search application.

   The whole corpus is a static file: this client loads fatwas.json once,
   searches it in the browser, and renders results in the Classical system.
   Qur'anic quotations are not detected here — they are identified offline by
   scripts/build_web_data.py against the full Qur'an and arrive as
   citations.json, so what the page labels as Qur'an really is Qur'an.

   State lives in the URL: ?q= a question, ?vol= a volume read in order,
   ?cat= a treatise, #f/<id> a single answer opened for reading.
   ========================================================================= */
'use strict';

const PAGE = 10;
const SNIPPET = 460;          // characters of the answer shown in a result
// Bump whenever scripts/build_web_data.py is re-run: the sidecars are fetched
// by this script, so without a version in the URL a browser will happily keep
// serving the previous build's spans against the current text.
const DATA_VERSION = '6';

const el = (id) => document.getElementById(id);
const els = {
  body: document.body,
  root: document.documentElement,
  input: el('q'),
  form: document.querySelector('.bar-seek'),
  loadbar: el('loadbar'),
  loadfill: el('loadfill'),
  loadnote: el('loadnote'),
  volHead: el('volHead'),
  volNum: el('volNum'),
  volNumAr: el('volNumAr'),
  qHead: el('qHead'),
  qEcho: el('qEcho'),
  qEchoAr: el('qEchoAr'),
  qLeadEn: el('qLeadEn'),
  qLeadAr: el('qLeadAr'),
  countEn: el('countEn'),
  countAr: el('countAr'),
  filters: el('filters'),
  blank: el('blank'),
  volNote: el('volNote'),
  results: el('results'),
  more: el('more'),
  reading: el('reading'),
  toast: el('toast'),
};

const state = {
  lang: 'en',
  theme: 'day',
  readsize: 0,
  data: [],
  byId: new Map(),
  cites: {},
  meta: null,
  ready: false,
  whole: false,             // true once the tails of the answers have arrived
  mode: 'blank',            // blank | query | vol | cat
  query: '',
  vol: null,
  cat: null,
  narrow: null,             // {type:'vol'|'cat'|'quran', value}
  lastKey: null,            // what was last computed, so a narrowing can expire
  hits: [],                 // [{f, score, pct}]
  shown: 0,
  readingId: null,
  returnFocusId: null,      // the passage to hand focus back to on leaving one
  bags: null,               // word bags + document frequency, built on demand
};

/* ------------------------------------------------------------------ i18n --- */
const toArabic = (n) => String(n).replace(/\d/g, (d) => '٠١٢٣٤٥٦٧٨٩'[d]);
const num = (n) => state.lang === 'ar'
  ? toArabic(n) : Number(n).toLocaleString('en');

// Arabic counts inflect; English does not.
function arPassages(n) {
  if (n === 1) return 'موضعٌ واحد';
  if (n === 2) return 'موضعان';
  if (n >= 3 && n <= 10) return `${toArabic(n)} مواضع`;
  return `${toArabic(n)} موضعاً`;
}
function arVolumes(n) {
  if (n === 1) return 'مجلدٍ واحد';
  if (n === 2) return 'مجلدين';
  if (n >= 3 && n <= 10) return `${toArabic(n)} مجلدات`;
  return `${toArabic(n)} مجلداً`;
}
// The brace-quotations left unlabelled, said the way Arabic says it: the noun,
// the verb and the predicate all follow the number.
function arUnlabelled(n) {
  const tail = ' موسومةٌ في النص، تُطلب في sunnah.com.';
  if (n === 1) return '· ونقلٌ واحد لم يُعرَف قرآناً،' + tail;
  if (n === 2) return '· ونقلان لم يُعرَفا قرآناً،' + tail;
  if (n >= 3 && n <= 10) return `· و${toArabic(n)} نقولٍ لم تُعرَف قرآناً،` + tail;
  return `· و${toArabic(n)} نقلاً لم تُعرَف قرآناً،` + tail;
}

const STR = {
  en: {
    title: (q) => `${q} · MAJMŪʿ`,
    placeholder: 'Ask a question, or name a topic…',
    on: 'Passages on',
    inTreatise: 'In the treatise',
    // The browser searches the words, not the embeddings — the engine's
    // semantic half runs server-side. Say so rather than imply otherwise.
    count: (n, v, shown) => `Ranked by the words they use · ${n.toLocaleString('en')} passage${n === 1 ? '' : 's'} in ${v} volume${v === 1 ? '' : 's'} · showing the closest ${shown.toLocaleString('en')}`,
    countVol: (n) => `${n.toLocaleString('en')} question${n === 1 ? '' : 's'} extracted from this volume, in the order the edition prints them`,
    countCat: (n) => `${n.toLocaleString('en')} passage${n === 1 ? '' : 's'} under this treatise, in the order the edition prints them`,
    none: 'Nothing in the extracted fatāwā answers to those words.',
    noneNote: 'Try fewer words, or the Arabic of the term. This site reaches the questions and answers extracted so far — not yet the whole of the printed work.',
    noneInTreatise: 'Nothing is extracted from this treatise yet.',
    noneInTreatiseNote: 'The treatise is named in the edition’s front matter, but none of its questions and answers have been extracted into this site yet.',
    all: 'All volumes',
    volume: (v) => `Volume ${v}`,
    treatise: 'The treatise this is from',
    quran: 'Quoting the Qur’ān',
    answerLabel: 'The answer, as it begins',
    read: 'Read the whole answer',
    pending: 'The English rendering of this passage is still being prepared. The Arabic, as printed, is below.',
    similar: 'Similar passages',
    more: 'Show more passages',
    quran_: 'Qur’ān',
    unlabelled: (n) => `· ${n} further quotation${n === 1 ? '' : 's'} not identified as Qur’ān — marked in the text, searchable on sunnah.com.`,
    someNarration: '· Also quotes narrations not identified as Qur’ān.',
    back: 'Back to the results',
    copyText: 'Copy the passage',
    copyLink: 'Copy the link',
    copied: 'Copied',
    askSomething: 'Put a question in the box first.',
    question: 'The question',
    answer: 'The answer',
    english: 'In English',
    notFound: 'That passage is not in this edition’s extracted fatāwā.',
    loading: 'Opening the book…',
    loadingPct: (p) => `Opening the book… ${p}%`,
    failed: 'The corpus could not be loaded. Reload the page, or check that data/fatwas.json is being served.',
    similarTo: 'Passages near',
    citeVol: (v, ps, pe) => `Vol. ${v} · ${ps === pe ? 'p. ' + ps : 'pp. ' + ps + '–' + pe}`,
    match: 'Match',
  },
  ar: {
    title: (q) => `${q} · المجموع`,
    placeholder: 'اسأل عن مسألة، أو اذكر باباً…',
    on: 'مواضع في',
    inTreatise: 'من رسالة',
    count: (n, v, shown) => `مرتَّبة بالألفاظ · ${arPassages(n)} في ${arVolumes(v)} · وهذه أقربها ${toArabic(shown)}`,
    countVol: (n) => `${arPassages(n)} مستخرجةٌ من هذا المجلد، على ترتيب الطبعة`,
    countCat: (n) => `${arPassages(n)} تحت هذه الرسالة، على ترتيب الطبعة`,
    none: 'ليس في الفتاوى المستخرجة ما يوافق هذه الألفاظ.',
    noneNote: 'فجرِّب ألفاظاً أقل، أو اطلبه بالعربية. وهذا الموضع لا يبلغ إلا ما استُخرج من المسائل والأجوبة، لا المطبوع كله بعدُ.',
    noneInTreatise: 'لم يُستخرج من هذه الرسالة شيءٌ بعد.',
    noneInTreatiseNote: 'الرسالة مثبتةٌ في فهرس الطبعة، ولكن لم تُستخرج مسائلها وأجوبتها إلى هذا الموضع بعد.',
    all: 'جميع المجلدات',
    volume: (v) => `المجلد ${toArabic(v)}`,
    treatise: 'الرسالة التي منه',
    quran: 'ما فيه قرآن',
    answerLabel: 'أول الجواب',
    read: 'اقرأ الجواب كاملاً',
    pending: 'الترجمة الإنجليزية لهذا الموضع قيد الإعداد.',
    similar: 'مواضع شبيهة',
    more: 'اعرض مواضع أخرى',
    quran_: 'قرآن',
    unlabelled: arUnlabelled,
    someNarration: '· وفيه نقولٌ لم تُعرَف قرآناً.',
    back: 'رجوع إلى النتائج',
    copyText: 'نسخ النص',
    copyLink: 'نسخ الرابط',
    copied: 'تم النسخ',
    askSomething: 'اكتب المسألة في الموضع أولاً.',
    question: 'السؤال',
    answer: 'الجواب',
    english: 'بالإنجليزية',
    notFound: 'ليس هذا الموضع في الفتاوى المستخرجة من هذه الطبعة.',
    loading: 'يُفتح الكتاب…',
    loadingPct: (p) => `يُفتح الكتاب… ${toArabic(p)}٪`,
    failed: 'تعذّر تحميل النصوص. أعد تحميل الصفحة، أو تحقق من أن data/fatwas.json يُخدَم.',
    similarTo: 'مواضع قريبة من',
    citeVol: (v, ps, pe) => `المجلد ${toArabic(v)} · ${ps === pe ? 'ص ' + toArabic(ps) : 'ص ' + toArabic(ps) + '–' + toArabic(pe)}`,
    match: 'القرب',
  },
};
const t = () => STR[state.lang];

/* --------------------------------------------------- Arabic normalization ---
   Combining marks are written as \u escapes on purpose: literal harakat inside
   a character class get visually reordered by bidi editing and silently
   corrupt the ranges. */
const TASHKEEL = /[ؐ-ًؚ-ٰٟۖ-ۭـ]/g;
function normalizeAr(s) {
  return (s || '')
    .replace(TASHKEEL, '')
    .replace(/[آأإٱ]/g, 'ا')   // آ أ إ ٱ -> ا
    .replace(/ى/g, 'ي')                        // ى -> ي
    .replace(/ؤ/g, 'و')                        // ؤ -> و
    .replace(/ئ/g, 'ي')                        // ئ -> ي
    .replace(/ة/g, 'ه')                        // ة -> ه
    .replace(/ء/g, '')                              // ء
    .toLowerCase();
}
const hasArabic = (s) => /[؀-ۿ]/.test(s || '');
const normWs = (s) => (s || '').replace(/\s+/g, ' ').trim();

/* ---------------------------------------------------------- highlighting --- */
const VAR = {
  'ا': '[اأإآٱ]',
  'ي': '[يىئی]',
  'و': '[وؤ]',
  'ه': '[هة]',
};
const TASH = '[\\u0610-\\u061A\\u064B-\\u065F\\u0670\\u06D6-\\u06ED\\u0640]*';
const escapeRe = (c) => c.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/* Function words. Asking "seeking help from the dead" is asking about help and
   the dead, not about "the" -- and marking every "the" also strikes through the
   middle of theft, them and their. These are dropped from the marking and from
   the scoring, but only while the query has something else in it: a search for
   "من" alone still finds and marks "من". The Arabic list is written in the form
   normalizeAr() produces (على -> علي, إلى -> الي). */
const STOP_EN = new Set(['the', 'and', 'for', 'from', 'with', 'that', 'this', 'these', 'those',
  'are', 'was', 'were', 'not', 'but', 'you', 'all', 'any', 'can', 'has', 'had', 'his', 'her',
  'its', 'our', 'out', 'who', 'why', 'how', 'what', 'when', 'where', 'which', 'into', 'upon',
  'than', 'then', 'they', 'them', 'their', 'there', 'have', 'been', 'about', 'over', 'under',
  'also', 'such', 'some', 'more', 'most', 'other', 'only', 'very', 'may', 'shall', 'will',
  'would', 'could', 'should', 'does', 'did', 'said']);
const STOP_AR = new Set(['من', 'في', 'علي', 'عن', 'الي', 'ان', 'ما', 'لا', 'هذا', 'هذه', 'ذلك',
  'التي', 'الذي', 'هو', 'هي', 'قد', 'كان', 'مع', 'او', 'ثم', 'بين', 'لم', 'لن', 'اذا', 'حتي',
  'عند', 'بعد', 'قبل', 'كما', 'لكن', 'وقد', 'وهو', 'وهي', 'ولا', 'فان', 'وان']);
const isStop = (tok) => (hasArabic(tok) ? STOP_AR : STOP_EN).has(tok);

/** A token worth searching for: at least two letters or digits. A single
    character, or a stray piece of punctuation, occurs in nearly every passage
    and would return the corpus dressed up as a result set. */
const isSearchable = (tok) => {
  const letters = tok.replace(/[^\p{L}\p{N}]/gu, '');
  return letters.length >= 2;
};

/** The words a query is actually about: searchable, function words dropped
    unless that leaves nothing, and bounded in number — the cost of a query is
    linear in its terms, and a pasted paragraph must not lock the page. */
function contentTokens(tokens) {
  const usable = [...new Set(tokens.filter(isSearchable))];   // asking twice is asking once
  if (!usable.length) return [];
  const kept = usable.filter((tok) => !isStop(tok));
  return (kept.length ? kept : usable).slice(0, MAX_TERMS);
}

function buildHighlighter(query) {
  if (!query) return null;
  const tokens = contentTokens((hasArabic(query) ? normalizeAr(query) : query.toLowerCase())
    .split(/\s+/).filter((tok) => tok.length >= 2));
  if (!tokens.length) return null;
  const parts = tokens.map((tok) => (hasArabic(tok)
    // Arabic joins its particles to the word, so no word boundary is asserted;
    // Latin gets one, or "dead" lights up inside "deadline".
    ? [...tok].map((c) => (VAR[c] || escapeRe(c))).join(TASH)
    : '\\b' + escapeRe(tok) + '\\b'));
  try { return new RegExp('(' + parts.join('|') + ')', 'gi'); } catch (e) { return null; }
}

function escapeHtml(s) {
  return (s || '').replace(/[&<>"]/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}
/** Mark the query where it falls, without ever marking inside an escape.
    Matching runs on the raw text and each piece is escaped as it is emitted;
    escaping first and marking after would let a query for "amp" split the
    &amp; that escaping had just produced. */
function hi(text, re) {
  if (!re) return escapeHtml(text);
  re.lastIndex = 0;
  let out = '';
  let last = 0;
  let m;
  while ((m = re.exec(text)) !== null) {
    out += escapeHtml(text.slice(last, m.index)) + '<mark>' + escapeHtml(m[0]) + '</mark>';
    last = m.index + m[0].length;
    if (m.index === re.lastIndex) re.lastIndex++;
  }
  return out + escapeHtml(text.slice(last));
}

/* ------------------------------------------------------ Qur'anic quotation ---
   The printed text marks quotations with { }. Those the offline pass matched
   against the Qur'an are set in the ornate brackets and underlined in gold;
   the rest are set in ordinary quotation marks, because they are not known to
   be scripture and must not be dressed as it. */
/* Quotation spans are computed offline (scripts/build_web_data.py) and arrive
   as character offsets into the very strings rendered here, so the page marks
   exactly what the build could prove and never re-guesses in the browser.
   Each span is [start, end, refIndex, kind]; refIndex -1 means the quotation
   was not identified as Qur'an. */
const BRACED = 0;
const NARRATION = -1;
const QUOTE_MARK = /['"‘’“”]/;

const refsOf = (id) => (state.cites[id] && state.cites[id].refs) || [];
/** Does this passage quote the Qur'an at all? (One question, one place to
    change it — the shape of citations.json is the build script's business.) */
const quotesQuran = (id) => refsOf(id).length > 0;
function spansOf(id, block, lang) {
  const c = state.cites[id];
  return (c && c[block] && c[block][lang]) || null;
}

/** One quotation, marked so its beginning and its end are unmistakable, and
    carrying where it is from. Qur'an is set in the ornate brackets in Arabic
    and in quotation marks in English, underlined in gold, named by sūrah and
    āyah, and linked to that āyah. A narration the build could not identify as
    Qur'an is set apart differently and links to a *search*, not a citation:
    without a hadith corpus this page can point you to where to look it up,
    and must not pretend to more. */
function quotation(inner, refIdx, refs, re, lang, quotedBefore, quotedAfter) {
  const body = hi(inner, re);
  if (refIdx >= 0 && refs[refIdx]) {
    const r = refs[refIdx];
    const label = lang === 'ar' ? r.ar : r.en;
    // Where the translator already set the verse in quotation marks, theirs
    // stand: adding a second pair would print 'And the one... as '"And the
    // one... The gold rule and the reference still mark it either way.
    const open = lang === 'ar' ? '﴿' : (quotedBefore ? '' : '“');
    const close = lang === 'ar' ? '﴾' : (quotedAfter ? '' : '”');
    return `<a class="ayah" href="${r.u}" target="_blank" rel="noopener"` +
      ` title="${escapeHtml(r.en + ' — ' + r.t)}">${open}${body}${close}` +
      `<sup class="qref">${escapeHtml(label)}</sup></a>`;
  }
  // A phrase of two words is not worth sending anyone to search for; set it
  // off as a quotation and leave it at that.
  const all = inner.split(/\s+/).filter(Boolean);
  const nOpen = quotedBefore ? '' : '«';
  const nClose = quotedAfter ? '' : '»';
  if (all.length < 3) return `${nOpen}${body}${nClose}`;
  const words = all.slice(0, 12).join(' ');
  const label = lang === 'ar' ? 'حديث؟' : 'narration';
  const title = lang === 'ar'
    ? 'ليست من القرآن. اطلبها في sunnah.com — بحثٌ لا عزو.'
    : 'Not Qur’ān. Searches sunnah.com for these words — a search, not a citation.';
  return `<a class="narration" href="https://sunnah.com/search?q=${encodeURIComponent(words)}"` +
    ` target="_blank" rel="noopener" title="${escapeHtml(title)}">${nOpen}${body}${nClose}` +
    `<sup class="qref">${label}</sup></a>`;
}

/** Text with its quotations marked. `offset` lets a paragraph or an excerpt be
    rendered with spans that were measured against the whole string. */
function renderQuoted(text, spans, refs, re, lang, offset, used, limit) {
  if (!spans || !spans.length) return hi(text, re);
  const base = offset || 0;
  const stop = limit === undefined ? text.length : limit;
  const out = [];
  let last = 0;
  for (const [s0, e0, refIdx, kind] of spans) {
    const s = s0 - base;
    const e = e0 - base;
    if (s < last || s < 0 || e > stop) continue;          // outside this slice
    out.push(hi(text.slice(last, s), re));
    const raw = text.slice(s, e);
    const inner = kind === BRACED ? raw.replace(/^\s*\{|\}\s*$/g, '').trim() : raw;
    const before = text.slice(Math.max(0, s - 2), s).trim().slice(-1);
    const after = text.slice(e, e + 2).trim().slice(0, 1);
    out.push(quotation(inner, refIdx, refs, re, lang,
      QUOTE_MARK.test(before), QUOTE_MARK.test(after)));
    if (used) used.add(refIdx);
    last = e;
  }
  out.push(hi(text.slice(last), re));
  return out.join('');
}

/** Cut to a word boundary without leaving a brace-quotation hanging open. */
function excerpt(text, limit) {
  if (!text) return '';
  if (text.length <= limit) return text;
  let cut = text.lastIndexOf(' ', limit);
  if (cut < limit * 0.6) cut = limit;
  let s = text.slice(0, cut);
  const opens = (s.match(/\{/g) || []).length;
  const closes = (s.match(/\}/g) || []).length;
  if (opens > closes) s = s.slice(0, s.lastIndexOf('{'));
  return s.trimEnd() + ' …';
}

/* ------------------------------------------------------------ data loading -- */
async function load() {
  showLoading(t().loading, 0);
  try {
    const [fatwas, cites] = await Promise.all([
      fetchWithProgress(`data/search-core.json?v=${DATA_VERSION}`),
      fetch(`data/citations.json?v=${DATA_VERSION}`)
        .then((r) => (r.ok ? r.json() : {})).catch(() => ({})),
    ]);
    state.meta = fatwas.meta;
    state.data = fatwas.fatwas;
    state.cites = cites;
    for (const f of state.data) {
      state.byId.set(f.id, f);
      indexFatwa(f);
    }
    state.ready = true;
    hideLoading();
    apply();
    loadRest();                 // the tails of the answers, behind the page
  } catch (e) {
    console.error(e);
    hideLoading();
    els.loadnote.hidden = false;
    els.loadnote.textContent = t().failed;
  }
}

/** The normalised forms searching works on. Rebuilt when an answer grows. */
function indexFatwa(f) {
  f._hi = normalizeAr((f.topic || '') + ' ' + (f.cat || ''));
  f._q = normalizeAr(f.qa || '') + ' ' + (f.qe || '').toLowerCase();
  f._a = normalizeAr(f.aa || '') + ' ' + (f.ae || '').toLowerCase();
}

/** The rest of the answers, fetched once the page is already usable.
    Nothing waits on this: search works the moment the first file lands, and
    when this one arrives the passages grow to their full length and the
    question on screen is quietly asked again, so a term buried on the tenth
    page of an answer is found a second later rather than not at all. */
async function loadRest() {
  try {
    const res = await fetch(`data/search-rest.json?v=${DATA_VERSION}`);
    if (!res.ok) return;
    const rest = await res.json();
    let grown = 0;
    for (const id in rest) {
      const f = state.byId.get(id);
      if (!f) continue;
      const tail = rest[id];
      if (tail.aa) f.aa += tail.aa;
      if (tail.ae) f.ae += tail.ae;
      delete f.more;
      indexFatwa(f);
      grown++;
    }
    state.whole = true;
    state.bags = null;                       // neighbours were built on stubs
    if (!grown || !state.ready) return;
    if (state.readingId) {
      // An answer opened before its tail arrived was showing its opening only.
      renderReading(state.readingId);
    } else if (state.mode === 'query') {
      const shown = state.shown;             // keep the reader where they are
      compute();
      renderHead();
      renderList(false);
      while (state.shown < shown && els.more.querySelector('.btn')) renderList(true);
    }
  } catch (e) {
    // The page keeps working on the opening of each answer; that is the point
    // of splitting them. Say nothing and leave the reader alone.
  }
}

async function fetchWithProgress(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(url + ' -> ' + res.status);
  const total = +res.headers.get('Content-Length') || 0;
  if (!res.body || !total) return res.json();
  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  const parts = [];
  let received = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    received += value.length;
    parts.push(decoder.decode(value, { stream: true }));
    const pct = Math.min(99, Math.round((received / total) * 100));
    showLoading(t().loadingPct(pct), pct);
  }
  parts.push(decoder.decode());
  return JSON.parse(parts.join(''));
}

function showLoading(note, pct) {
  els.loadbar.hidden = false;
  els.loadfill.style.width = pct + '%';
  els.loadnote.hidden = false;
  els.loadnote.textContent = note;
}
function hideLoading() {
  els.loadbar.hidden = true;
  els.loadnote.hidden = true;
}

/* ------------------------------------------------------------------ search --
   Ranking has to answer "is this passage about the question", not "does this
   passage contain the words somewhere". Three things decide it:

     where   — a term in the heading or the question weighs far more than the
               same term buried in the answer;
     how far — a passage is about a subject when the terms sit close together,
               so the tightest window containing them carries real weight;
     how long— an answer of forty thousand characters contains almost any
               common word by accident, so every field is normalised by its
               length.

   The score is then divided by the query's own weight, which makes it
   comparable across queries and lets the match figure mean something on its
   own rather than "whatever ranked first today". */

// Median field lengths in this corpus, in characters (heading 21, question
// 403, answer 1776 — the answers' mean is 13,744, which is exactly why they
// need normalising).
const K_LEN = { hi: 24, q: 420, a: 2000 };
const WEIGHT = { hi: 3.0, q: 2.0, a: 0.7 };
const PROX_WEIGHT = 2.2;
const PHRASE_WEIGHT = 1.2;
// The match figure saturates rather than dividing by a "perfect" score: a
// strong passage lands in the high eighties, a passing mention in the teens,
// and nothing is ever declared a flawless answer to the question.
const PCT_SCALE = 2.2;
// Every candidate is scored: a capped pass would have to report a capped
// total, and a count this page cannot stand behind is worse than a slow one.
// The cost is bounded on the other axis instead -- by MAX_TERMS below -- so
// the worst case stays in the low hundreds of milliseconds on a submit.
const MAX_TERMS = 12;

/* A small hand-kept lexicon of the terms this corpus turns on, in both
   directions. Two things make it necessary. The translations are literal, so
   an English question asked as "help from the dead" meets an answer that says
   "seeks aid from the buried one". And the Arabic is searched alongside the
   English, so an English term that knows its Arabic reaches the 37 volumes
   rather than only the translated questions.

   This is a glossary, not a thesaurus: every pair is a term of art in these
   fatāwā. Nothing here guesses at meaning — an unlisted word is searched as
   written. Arabic is written plainly and normalised on load. */
const LEXICON = {
  help: ['istighathah', 'الاستغاثة', 'يستغيث'],
  aid: ['istighathah', 'الاستغاثة', 'يستغيث'],
  dead: ['deceased', 'الموتى', 'الميت'],
  grave: ['graves', 'tomb', 'القبور'],
  intermediary: ['wasitah', 'واسطة', 'الوسائط'],
  tawassul: ['التوسل', 'وسيلة'],
  intercession: ['shafaah', 'الشفاعة'],
  divorce: ['repudiation', 'الطلاق'],
  anger: ['angry', 'الغضب'],
  prayer: ['salah', 'الصلاة'],
  congregation: ['congregational', 'الجماعة'],
  fasting: ['ramadan', 'الصيام', 'الصوم'],
  zakat: ['alms', 'الزكاة'],
  usury: ['riba', 'الربا'],
  innovation: ['bidah', 'البدعة'],
  oath: ['اليمين', 'النذر'],
  inheritance: ['الميراث', 'الفرائض'],
  endowment: ['waqf', 'الوقف'],
  ablution: ['wudu', 'الوضوء'],
  purity: ['الطهارة'],
  pilgrimage: ['hajj', 'الحج'],
  marriage: ['nikah', 'النكاح'],
  saints: ['awliya', 'الأولياء'],
  attributes: ['sifat', 'الصفات'],
};

/** The forms a query word may take in the text: itself, plus anything the
    glossary knows it by. */
function expand(term) {
  const out = [term];
  const listed = LEXICON[term] || LEXICON[term.replace(/(ing|ed|es|s)$/, '')];
  if (listed) {
    for (const alt of listed) {
      const v = hasArabic(alt) ? normalizeAr(alt) : alt.toLowerCase();
      if (v && !out.includes(v)) out.push(v);
    }
  }
  return out;
}

/** Arabic glues its particles to the word, so a term matches anywhere inside a
    word. Latin gets a word boundary and a short suffix, so "seeking" finds
    "seek" and "seeks" but "dead" never finds "death". */
function variantSource(term) {
  if (hasArabic(term)) return escapeRe(term);
  const stem = term.replace(/(ing|ed|es|s)$/, '');
  const base = stem.length >= 4 ? stem : term;
  return '\\b' + escapeRe(base) + '\\w{0,4}\\b';
}

function termPattern(variants) {
  return new RegExp(variants.map(variantSource).join('|'), 'g');
}

const ALT_WEIGHT = 0.6;    // the glossary's word, not the reader's: worth less

function matchPositions(text, re) {
  re.lastIndex = 0;
  const list = [];
  let m;
  while ((m = re.exec(text)) !== null) {
    list.push(m.index);
    if (m.index === re.lastIndex) re.lastIndex++;
    if (list.length >= 120) break;
  }
  return list;
}

/** Where each slot falls in a field. The word actually typed is looked for
    first; only if it is absent does the glossary's alternative stand in, and
    then it counts for less. */
function fieldHits(text, patterns) {
  const pos = [];
  const weight = [];
  for (const p of patterns) {
    let list = matchPositions(text, p.base);
    let w = 1;
    if (!list.length && p.alt) {
      list = matchPositions(text, p.alt);
      w = ALT_WEIGHT;
    }
    pos.push(list);
    weight.push(list.length ? w : 0);
  }
  return { pos, weight };
}

/** The shortest stretch of text containing every term that occurs here. */
function minWindow(pos) {
  const need = pos.reduce((n, l) => n + (l.length ? 1 : 0), 0);
  if (need <= 1) return null;
  const items = [];
  pos.forEach((list, i) => { for (const p of list) items.push([p, i]); });
  items.sort((a, b) => a[0] - b[0]);
  const count = new Map();
  let have = 0;
  let best = Infinity;
  let l = 0;
  for (let r = 0; r < items.length; r++) {
    const term = items[r][1];
    count.set(term, (count.get(term) || 0) + 1);
    if (count.get(term) === 1) have++;
    while (have === need) {
      best = Math.min(best, items[r][0] - items[l][0]);
      const left = items[l][1];
      count.set(left, count.get(left) - 1);
      if (count.get(left) === 0) have--;
      l++;
    }
  }
  return best === Infinity ? null : best;
}

/** How tightly the terms sit together, 0 (scattered) to 1 (side by side),
    scaled by how much of the query is here at all. A single-word query has
    nothing to be scattered, so its presence is its proximity. */
function proximity(pos, termLen, nTerms) {
  const present = pos.reduce((n, l) => n + (l.length ? 1 : 0), 0);
  if (!present) return 0;
  if (nTerms === 1) return 1;
  const coverage = present / nTerms;
  const span = minWindow(pos);
  if (span === null) return 0.12 * coverage;  // only one of several terms here
  const tight = termLen + 4;                  // adjacent words, near enough
  return Math.min(1, tight / Math.max(span, tight)) * coverage;
}

function search(query) {
  const raw = query.trim();
  if (!raw) return [];
  const norm = hasArabic(raw) ? normalizeAr(raw) : raw.toLowerCase();
  const terms = contentTokens(norm.split(/\s+/).filter(Boolean));
  if (!terms.length) return [];

  const N = state.data.length;
  const inDoc = (f, v) => f._hi.includes(v) || f._q.includes(v) || f._a.includes(v);

  // Each query word becomes a slot: the word, plus whatever the glossary knows
  // it by. But a stand-in that is far commoner than the word actually typed
  // would drown it — "means" for tawassul turns up in half the book — so every
  // alternative is counted first and dropped if it is too broad to be evidence.
  const slots = terms.map((term) => {
    const variants = expand(term);
    if (variants.length === 1) return variants;
    const seen = variants.map((v) => {
      let n = 0;
      for (const f of state.data) if (inDoc(f, v)) n++;
      return n;
    });
    const baseDf = seen[0];
    const ceiling = Math.max(baseDf * 4, N * 0.02);
    return variants.filter((v, i) =>
      i === 0 || (seen[i] > 0 && seen[i] <= Math.max(ceiling, N * 0.08)));
  });

  // Pass one, over the strings only: which passages are worth looking at, and
  // how common each term is (a term in half the corpus tells us little).
  const df = terms.map(() => 0);
  const candidates = [];
  for (const f of state.data) {
    let hits = 0;
    for (let i = 0; i < slots.length; i++) {
      const found = slots[i].some((v) => inDoc(f, v));
      if (found) { df[i]++; hits++; }
    }
    // Short queries must match in full; longer ones may miss one word and
    // still be the passage that answers them.
    const needed = terms.length <= 2 ? terms.length : Math.ceil(terms.length * 0.7);
    if (hits >= needed) candidates.push({ f, hits });
  }
  if (!candidates.length) return [];

  const idf = terms.map((_, i) =>
    Math.log(1 + (N - df[i] + 0.5) / (df[i] + 0.5)));
  const Q = idf.reduce((a, b) => a + b, 0) || 1;
  const termLen = terms.reduce((a, b) => a + b.length + 1, 0);
  const patterns = slots.map((variants) => ({
    base: termPattern([variants[0]]),
    alt: variants.length > 1 ? termPattern(variants.slice(1)) : null,
  }));
  const phrase = terms.length > 1 ? new RegExp(terms.map((t) => (hasArabic(t)
    ? escapeRe(t) : '\\b' + escapeRe(t) + '\\w{0,4}')).join('[\\s\\u060C,;:]+'), 'i') : null;

  // Pass two, in detail, on every candidate — so the count is the real count
  // and the last passage is as reachable as the first.
  const scored = [];
  for (const { f } of candidates) {
    let raw2 = 0;
    let bestProx = 0;
    let subject = 0;                 // weight of the query found in heading or question
    const parts = {};
    for (const field of ['hi', 'q', 'a']) {
      const text = field === 'hi' ? f._hi : (field === 'q' ? f._q : f._a);
      if (!text) continue;
      const { pos, weight } = fieldHits(text, patterns);
      let mass = 0;
      for (let i = 0; i < terms.length; i++) mass += idf[i] * weight[i];
      if (!mass) continue;
      // Length normalisation: the longer the field, the less an isolated
      // occurrence in it means.
      const norm2 = 1 / (1 + Math.log(1 + text.length / K_LEN[field]));
      raw2 += WEIGHT[field] * mass * norm2;
      if (field !== 'a') subject = Math.max(subject, mass / Q);
      // Proximity inside the answer is also normalised by its length: in forty
      // thousand characters, three ordinary words fall near each other by
      // chance, and that is not evidence of anything.
      const p = proximity(pos, termLen, terms.length) * (field === 'a' ? 0.55 * norm2 : 1);
      if (p > bestProx) bestProx = p;
      parts[field] = { mass: +(mass / Q).toFixed(2), norm: +norm2.toFixed(3), prox: +p.toFixed(3) };
    }
    raw2 += PROX_WEIGHT * bestProx * Q;
    const hasPhrase = phrase &&
      (phrase.test(f._hi) || phrase.test(f._q) || phrase.test(f._a));
    if (hasPhrase) raw2 += PHRASE_WEIGHT * Q;
    // Being about the question is what separates an answer to it from a
    // passage that merely uses its words in passing.
    const aboutness = 0.4 + 0.6 * subject;
    const score = (raw2 / Q) * aboutness;
    scored.push({
      f,
      score,
      parts: { ...parts, subject: +subject.toFixed(2), phrase: !!hasPhrase, raw: +(raw2 / Q).toFixed(2) },
      // An absolute reading, not a rank: a weak passage says so, and nothing
      // is called a perfect match merely for coming first.
      pct: Math.max(1, Math.round(100 * (1 - Math.exp(-score / PCT_SCALE)))),
    });
  }
  scored.sort((a, b) => b.score - a.score || a.f.v - b.f.v || a.f.ps - b.f.ps);
  return scored;
}

/** A bag of whole words per passage -- its heading, its question and the
    opening of its answer, where the subject is actually named. Whole words
    matter: substring matching finds waqf inside every word that merely
    contains those letters. Built once, on the first request for neighbours. */
function bags() {
  if (state.bags) return state.bags;
  const df = new Map();
  const map = new Map();
  for (const f of state.data) {
    const text = (f.topic || '') + ' ' + (f.cat || '') + ' ' +
      (f.qa || '') + ' ' + (f.aa || '').slice(0, 1500);
    const set = new Set(normalizeAr(text).split(/\s+/).filter((w) => w.length > 2));
    map.set(f.id, set);
    for (const w of set) df.set(w, (df.get(w) || 0) + 1);
  }
  state.bags = { map, df };
  return state.bags;
}

/** Passages near this one, by the weight of the words they share: every shared
    word counts for how rare it is across the corpus, and the total is damped
    by how much the candidate says, so a long passage cannot win on breadth
    alone. Lexical, like the rest of this client -- the engine's semantic
    neighbours are computed from embeddings server-side. */
function similar(f, limit = 6) {
  const { map, df } = bags();
  const n = state.data.length;
  const seed = map.get(f.id);
  if (!seed || !seed.size) return [];

  // A word carried by more than a fifth of the corpus says nothing about topic.
  const weight = new Map();
  for (const w of seed) {
    const d = df.get(w) || 1;
    if (d > n * 0.2) continue;
    weight.set(w, Math.log(n / d));
  }
  if (!weight.size) return [];

  const scored = [];
  for (const g of state.data) {
    if (g.id === f.id) continue;
    const bag = map.get(g.id);
    let score = 0;
    for (const [w, iw] of weight) if (bag.has(w)) score += iw;
    if (score <= 0) continue;
    score /= Math.sqrt(bag.size);
    if (g.cat && g.cat === f.cat) score *= 1.35;   // the same treatise in the edition's own arrangement
    scored.push({ f: g, score });
  }
  scored.sort((a, b) => b.score - a.score || a.f.v - b.f.v || a.f.ps - b.f.ps);
  const top = scored.length ? scored[0].score : 1;
  for (const s of scored) s.pct = Math.max(8, Math.round((s.score / top) * 100));
  return scored.slice(0, limit);
}

/* ------------------------------------------------------------------- state -- */
function readUrl() {
  const p = new URLSearchParams(location.search);
  const q = (p.get('q') || '').trim();
  const vol = p.get('vol');
  const cat = (p.get('cat') || '').trim();
  state.query = q;
  state.vol = vol && /^([1-9]|[12]\d|3[0-7])$/.test(vol) ? +vol : null;
  state.cat = cat;
  state.mode = q ? 'query' : (state.vol ? 'vol' : (cat ? 'cat' : 'blank'));
  const m = location.hash.match(/^#f\/([A-Za-z0-9_]+)$/);
  state.readingId = m ? m[1] : null;
}

const storedLang = () => {
  try { return localStorage.getItem('majmu:lang'); } catch (e) { return null; }
};

function go(params, replace) {
  const p = new URLSearchParams();
  if (params.q) p.set('q', params.q);
  if (params.vol) p.set('vol', params.vol);
  if (params.cat) p.set('cat', params.cat);
  const url = location.pathname + (p.toString() ? '?' + p : '');
  history[replace ? 'replaceState' : 'pushState'](null, '', url);
  state.narrow = null;
  state.returnFocusId = null;   // a new search is not a return to an old one
  // An Arabic question opens the Arabic page, exactly as it does when the page
  // is loaded with one -- otherwise asking in Arabic answers in English, and
  // the words asked for cannot be marked in the passage. An explicit choice
  // from the switch still wins.
  if (params.q && hasArabic(params.q) && state.lang !== 'ar' && !storedLang()) {
    setLang('ar');            // re-renders through apply()
  } else {
    apply();
  }
  window.scrollTo({ top: 0 });
}

function compute() {
  // A narrowing belongs to the search it was made in. Back, forward and every
  // other route here changes the search without going through go(), so the
  // pills are cleared whenever what is being looked at actually changes.
  const key = `${state.mode}|${state.query}|${state.vol}|${state.cat}`;
  if (key !== state.lastKey) {
    state.narrow = null;
    state.lastKey = key;
  }
  if (state.mode === 'query') {
    state.hits = search(state.query);
  } else if (state.mode === 'vol') {
    state.hits = state.data.filter((f) => f.v === state.vol)
      .sort((a, b) => a.ps - b.ps).map((f) => ({ f, score: 0, pct: 0 }));
  } else if (state.mode === 'cat') {
    state.hits = state.data.filter((f) => f.cat === state.cat)
      .sort((a, b) => a.v - b.v || a.ps - b.ps).map((f) => ({ f, score: 0, pct: 0 }));
  } else {
    state.hits = [];
  }
  state.shown = 0;
}

function narrowed() {
  const n = state.narrow;
  if (!n) return state.hits;
  if (n.type === 'vol') return state.hits.filter((h) => h.f.v === n.value);
  if (n.type === 'cat') return state.hits.filter((h) => h.f.cat === n.value);
  if (n.type === 'quran') return state.hits.filter((h) => quotesQuran(h.f.id));
  return state.hits;
}

/* ---------------------------------------------------------------- rendering -- */
function citation(f) {
  return `<span class="cite en">${STR.en.citeVol(f.v, f.ps, f.pe)}</span>` +
         `<span class="cite ar" lang="ar">${STR.ar.citeVol(f.v, f.ps, f.pe)}</span>`;
}

/** The treatise a passage sits in. Openable only when the edition's front
    matter actually named one; a bare heading is set as type, not as a link. */
function treatiseLabel(f) {
  const name = f.cat || f.topic || '';
  if (!name) return '';
  const lead = `<span class="en">Treatise: </span><span class="ar" lang="ar">الرسالة: </span>`;
  return lead + (f.cat
    ? `<button type="button" class="linklike" data-cat="${escapeHtml(f.cat)}" lang="ar" dir="rtl">${escapeHtml(f.cat)}</button>`
    : `<span class="linklike" lang="ar" dir="rtl" style="cursor: default">${escapeHtml(name)}</span>`);
}

/** The margin index of what a passage quotes. On a result it lists the verses
    standing in the words on screen; on an opened answer it lists every verse
    the passage cites — including any the translator paraphrased, which is why
    they are named here even when they could not be underlined in the prose. */
function ayahChips(f, used, listAll) {
  const L = t();
  const refs = refsOf(f.id);
  const c = state.cites[f.id];
  const unknown = c ? (((c.q && c.q.u) || 0) + ((c.a && c.a.u) || 0)) : 0;
  const idx = listAll
    ? refs.map((_, i) => i)
    : [...used].filter((i) => i >= 0).sort((a, b) => a - b);
  const hasNarration = listAll ? unknown > 0 : used.has(NARRATION);
  if (!idx.length && !hasNarration) return '';

  const links = idx.map((i) => {
    const r = refs[i];
    return `<a href="${r.u}" target="_blank" rel="noopener" title="${escapeHtml(r.t)}">` +
      `<span class="en">${escapeHtml(r.en)}</span>` +
      `<span class="ar" lang="ar">${escapeHtml(r.ar)}</span></a>`;
  }).join('');
  const tag = idx.length
    ? `<span class="tag tag-outline"><span class="en">${STR.en.quran_}</span>` +
      `<span class="ar" lang="ar">${STR.ar.quran_}</span></span>`
    : '';
  const note = hasNarration
    ? `<span class="quiet en">${listAll ? STR.en.unlabelled(unknown) : STR.en.someNarration}</span>` +
      `<span class="quiet ar" lang="ar">${listAll ? STR.ar.unlabelled(unknown) : STR.ar.someNarration}</span>`
    : '';
  return `<div class="ayahs">${tag}${links}${note}</div>`;
}

function resultNode(hit, re) {
  const f = hit.f;
  const art = document.createElement('article');
  art.className = 'result';
  art.dataset.id = f.id;

  const qa = excerpt(f.qa || '', 700);
  const aa = excerpt(f.aa || '', SNIPPET);
  const matchHtml = state.mode === 'query'
    ? `<span class="match">
         <span class="en">${STR.en.match}</span><span class="ar" lang="ar">${STR.ar.match}</span>
         <span class="match-bar" aria-hidden="true"><i style="width: ${hit.pct}%"></i></span>
         <span>${hit.pct}</span></span>`
    : '';

  // The passage keeps a reading measure; everything about it — where it is
  // printed, how well it answers, what it quotes, what you can do with it —
  // stands in the margin beside it, which is what the space to the side is for.
  const used = new Set();
  const body = passage(f, re, qa, aa, used);
  art.innerHTML =
    `<div class="result-main">${body}</div>
     <aside class="result-rail">
       <div class="result-meta">${citation(f)}${treatiseLabel(f)}${matchHtml}</div>
       ${ayahChips(f, used, false)}
       <div class="actions">
         <button type="button" class="btn btn-primary" data-read>
           <span class="en">${STR.en.read}</span><span class="ar" lang="ar">${STR.ar.read}</span></button>
         <button type="button" class="btn btn-ghost" data-similar>
           <span class="en">${STR.en.similar}</span><span class="ar" lang="ar">${STR.ar.similar}</span></button>
       </div>
     </aside>`;
  return art;
}

/** The question and the opening of the answer, in the page's language and in
    that language only -- the switch in the bar is what changes it. English
    falls back to the Arabic, with a note, for anything not yet translated. */
/** How much of an excerpt is real text rather than the trailing ellipsis —
    a quotation must not be drawn as running into the "…". */
const contentLen = (s) => (s.endsWith(' …') ? s.length - 2 : s.length);

function passage(f, re, qa, aa, used) {
  const L = t();
  const refs = refsOf(f.id);
  if (state.lang === 'en' && f.qe && f.ae) {
    const qe = excerpt(f.qe, 700);
    const ae = excerpt(f.ae, SNIPPET + 240);
    return `<p class="q-en">${renderQuoted(qe, spansOf(f.id, 'q', 'en'), refs, re, 'en', 0, used, contentLen(qe))}</p>
      <span class="a-label">${L.answerLabel}</span>
      <p class="a-en">${renderQuoted(ae, spansOf(f.id, 'a', 'en'), refs, re, 'en', 0, used, contentLen(ae))}</p>`;
  }
  const pending = state.lang === 'en'
    ? `<p class="pending">${L.pending}</p>` : '';
  return `${pending}
    <p class="q-ar" lang="ar" dir="rtl">${renderQuoted(qa, spansOf(f.id, 'q', 'ar'), refs, re, 'ar', 0, used, contentLen(qa))}</p>
    <span class="a-label">${L.answerLabel}</span>
    <p class="a-ar" lang="ar" dir="rtl">${renderQuoted(aa, spansOf(f.id, 'a', 'ar'), refs, re, 'ar', 0, used, contentLen(aa))}</p>`;
}

function renderList(append) {
  const list = narrowed();
  const re = state.mode === 'query' ? buildHighlighter(state.query) : null;
  if (!append) {
    els.results.innerHTML = '';
    state.shown = 0;
  }

  if (!list.length) {
    els.more.innerHTML = '';
    // Nothing found means different things in different modes, and the words
    // for a failed search are wrong for a volume nobody searched: a reader
    // walking volume 36 was told that nothing "answers to those words" when
    // they had typed none. In that mode the note above already says exactly
    // what is going on, so this says nothing at all.
    if (state.mode === 'vol') {
      els.results.innerHTML = '';
      return;
    }
    const heading = state.mode === 'cat' ? 'noneInTreatise' : 'none';
    const note = state.mode === 'cat' ? 'noneInTreatiseNote' : 'noneNote';
    els.results.innerHTML =
      `<div class="blank" style="padding-top: var(--leading)">
         <h1 class="en">${STR.en[heading]}</h1><h1 class="ar" lang="ar">${STR.ar[heading]}</h1>
         <p class="en">${STR.en[note]}</p><p class="ar" lang="ar">${STR.ar[note]}</p>
       </div>`;
    return;
  }

  const slice = list.slice(state.shown, state.shown + PAGE);
  const frag = document.createDocumentFragment();
  for (const hit of slice) frag.appendChild(resultNode(hit, re));
  els.results.appendChild(frag);
  state.shown += slice.length;

  els.more.innerHTML = '';
  if (state.shown < list.length) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'btn btn-secondary';
    b.innerHTML = `<span class="en">${STR.en.more}</span><span class="ar" lang="ar">${STR.ar.more}</span>`;
    b.addEventListener('click', () => renderList(true));
    els.more.appendChild(b);
  }
}

function renderFilters() {
  const wrap = els.filters;
  for (const old of [...wrap.querySelectorAll('.pill')]) old.remove();
  if (state.mode !== 'query' || state.hits.length < 2) { wrap.hidden = true; return; }

  const pills = [];
  const add = (label, labelAr, active, onClick, lang) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'pill';
    b.setAttribute('aria-pressed', String(active));
    if (lang === 'ar') { b.lang = 'ar'; b.dir = 'rtl'; b.textContent = labelAr; } else {
      b.innerHTML = `<span class="en">${escapeHtml(label)}</span>` +
                    `<span class="ar" lang="ar">${escapeHtml(labelAr)}</span>`;
    }
    b.addEventListener('click', onClick);
    pills.push(b);
  };

  const n = state.narrow;
  add(STR.en.all, STR.ar.all, !n, () => { state.narrow = null; renderFilters(); renderList(false); });

  const byVol = new Map();
  for (const h of state.hits) byVol.set(h.f.v, (byVol.get(h.f.v) || 0) + 1);
  const topVols = [...byVol.entries()].sort((a, b) => b[1] - a[1] || a[0] - b[0]).slice(0, 3);
  for (const [v, count] of topVols) {
    add(`${STR.en.volume(v)} (${count})`, `${STR.ar.volume(v)} (${toArabic(count)})`,
      !!n && n.type === 'vol' && n.value === v,
      () => { state.narrow = { type: 'vol', value: v }; renderFilters(); renderList(false); });
  }

  const byCat = new Map();
  for (const h of state.hits) if (h.f.cat) byCat.set(h.f.cat, (byCat.get(h.f.cat) || 0) + 1);
  const topCat = [...byCat.entries()].sort((a, b) => b[1] - a[1])[0];
  if (topCat && topCat[1] > 1) {
    add(STR.en.treatise, STR.ar.treatise,
      !!n && n.type === 'cat' && n.value === topCat[0],
      () => { state.narrow = { type: 'cat', value: topCat[0] }; renderFilters(); renderList(false); });
    pills[pills.length - 1].title = topCat[0];
  }

  // Everything extracted so far carries an English rendering, so "with English"
  // would narrow to everything. This narrows to what quotes scripture instead.
  const withQuran = state.hits.filter((h) => quotesQuran(h.f.id)).length;
  if (withQuran && withQuran < state.hits.length) {
    add(`${STR.en.quran} (${withQuran})`, `${STR.ar.quran} (${toArabic(withQuran)})`,
      !!n && n.type === 'quran',
      () => { state.narrow = { type: 'quran' }; renderFilters(); renderList(false); });
  }

  wrap.hidden = false;
  for (const p of pills) wrap.appendChild(p);
}

function renderHead() {
  const list = narrowed();
  els.volHead.hidden = state.mode !== 'vol';
  els.qHead.hidden = !(state.mode === 'query' || state.mode === 'cat');
  els.blank.hidden = state.mode !== 'blank';
  els.volNote.hidden = true;

  if (state.mode === 'vol') {
    els.volNum.textContent = state.vol;
    els.volNumAr.textContent = toArabic(state.vol);
    els.body.dataset.mode = 'vol';
    document.title = `${STR.en.volume(state.vol)} · MAJMŪʿ`;
    const heads = els.volHead.querySelectorAll('.count');
    heads[0].textContent = state.hits.length
      ? STR.en.countVol(state.hits.length)
      : 'Opened at the first page, in the order the edition prints it.';
    heads[1].textContent = state.hits.length
      ? STR.ar.countVol(state.hits.length)
      : 'مفتوحٌ من أول صفحةٍ فيه، على ترتيب الطبعة.';
    if (!state.hits.length) {
      els.volNote.hidden = false;
      // 36 and 37 are the edition's indexes; anything else is text not yet
      // extracted. Two different facts, two different notes.
      const indexVolumes = (state.stats && state.stats.indexVolumes) || [36, 37];
      els.volNote.dataset.kind = indexVolumes.includes(state.vol) ? 'index' : 'pending';
      for (const v of els.volNote.querySelectorAll('.v')) {
        v.textContent = v.lang === 'ar' ? toArabic(state.vol) : state.vol;
      }
    }
    return;
  }

  els.body.dataset.mode = '';
  if (state.mode === 'query') {
    const ar = hasArabic(state.query);
    els.qLeadEn.textContent = STR.en.on;
    els.qLeadAr.textContent = STR.ar.on;
    els.qEcho.textContent = state.query;
    els.qEchoAr.textContent = state.query;
    els.qEcho.lang = ar ? 'ar' : 'en';
    els.qEchoAr.lang = ar ? 'ar' : 'en';
    document.title = STR[state.lang].title(state.query);
    const vols = new Set(list.map((h) => h.f.v)).size;
    const shown = Math.min(PAGE, list.length);
    els.countEn.textContent = list.length ? STR.en.count(list.length, vols, shown) : '';
    els.countAr.textContent = list.length ? STR.ar.count(list.length, vols, shown) : '';
  } else if (state.mode === 'cat') {
    els.qLeadEn.textContent = STR.en.inTreatise;
    els.qLeadAr.textContent = STR.ar.inTreatise;
    els.qEcho.textContent = state.cat;
    els.qEchoAr.textContent = state.cat;
    els.qEcho.lang = 'ar';
    els.qEchoAr.lang = 'ar';
    document.title = `${state.cat} · MAJMŪʿ`;
    els.countEn.textContent = STR.en.countCat(list.length);
    els.countAr.textContent = STR.ar.countCat(list.length);
  }
  renderFilters();
}

/* ------------------------------------------------------------- reading view -- */
function renderReading(id) {
  const f = state.byId.get(id);
  const r = els.reading;
  r.hidden = false;
  els.results.hidden = true;
  els.more.hidden = true;
  els.qHead.hidden = true;
  els.volHead.hidden = true;
  els.blank.hidden = true;
  els.volNote.hidden = true;

  if (!f) {
    r.innerHTML = `<div class="blank"><h1 class="en">${STR.en.notFound}</h1>` +
      `<h1 class="ar" lang="ar">${STR.ar.notFound}</h1></div>`;
    return;
  }
  document.title = `${STR[state.lang].citeVol(f.v, f.ps, f.pe)} · MAJMŪʿ`;
  const used = new Set();

  r.innerHTML =
    `<div class="reading-bar">
       <button type="button" class="btn btn-secondary" data-back>
         <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 6l-6 6 6 6"></path></svg>
         <span class="en">${STR.en.back}</span><span class="ar" lang="ar">${STR.ar.back}</span></button>
       <a class="btn btn-secondary" href="f/${f.id}.html">
         <span class="en">Permanent page</span><span class="ar" lang="ar">الصفحة الثابتة</span></a>
       <span class="spacer"></span>
       <span class="sizer" role="group" aria-label="Text size / حجم الخط">
         <button type="button" data-size="-1" aria-label="Smaller">أ&minus;</button>
         <button type="button" data-size="1" aria-label="Larger">أ+</button>
       </span>
       <button type="button" class="btn btn-secondary" data-copy-text>
         <span class="en">${STR.en.copyText}</span><span class="ar" lang="ar">${STR.ar.copyText}</span></button>
       <button type="button" class="btn btn-secondary" data-copy-link>
         <span class="en">${STR.en.copyLink}</span><span class="ar" lang="ar">${STR.ar.copyLink}</span></button>
     </div>
     <div class="reading-head">
       <div class="result-meta">${citation(f)}${treatiseLabel(f)}</div>
       <h1 lang="ar" dir="rtl">${escapeHtml(f.topic || f.cat || 'فتوى')}</h1>
     </div>
     <div class="reading-body">
       <div class="read-block">
         <span class="fatwa-label">${STR[state.lang].question}</span>
         ${reading(f, 'q', used)}
       </div>
       <div class="read-block">
         <span class="fatwa-label">${STR[state.lang].answer}</span>
         ${reading(f, 'a', used)}
       </div>
       <div class="colophon">
         <span class="mark" aria-hidden="true">﴾ ۞ ﴿</span>
         <span class="en"> Majmūʿ al-Fatāwā · ${STR.en.citeVol(f.v, f.ps, f.pe)} · King Fahd Complex edition</span>
         <span class="ar" lang="ar"> مجموع الفتاوى · ${STR.ar.citeVol(f.v, f.ps, f.pe)} · طبعة مجمع الملك فهد</span>
       </div>
     </div>
     <aside class="reading-rail">
       ${ayahChips(f, used, true)}
     </aside>`;

  // The verses this answer cites, and the passages nearest it, stand in the
  // margin — an apparatus beside the text, not an appendix after it.
  const near = similar(f, 5);
  if (near.length) {
    const box = document.createElement('div');
    box.className = 'rail-block';
    box.innerHTML = `<span class="fatwa-label">${STR[state.lang].similarTo}` +
      `${state.lang === 'en' ? ' this question' : ' هذه المسألة'}</span>` +
      near.map((hit) => nearbyRow(hit.f, true)).join('');
    r.querySelector('.reading-rail').appendChild(box);
  }
  window.scrollTo({ top: 0 });
  // The passage that was clicked has just been replaced by the one being
  // read: move the reading position with it, or a keyboard reader is dropped
  // back at the top of the document with no idea what opened.
  r.focus({ preventScroll: true });
}

/** A neighbouring passage: its citation and its question, both in the page's
    language, falling back to the Arabic where nothing is translated yet. */
function nearbyRow(g, compact) {
  const L = STR[state.lang];
  const en = state.lang === 'en' && g.qe;
  const q = en ? g.qe : g.qa;
  return `<a class="nearby" href="#f/${g.id}">` +
    `<span class="nearby-cite">${L.citeVol(g.v, g.ps, g.pe)}</span>` +
    `<span class="nearby-q"${en ? '' : ' lang="ar" dir="rtl"'}>` +
    `${escapeHtml(excerpt(q || '', compact ? 88 : 130))}</span></a>`;
}

/** The printed text runs unbroken for pages at a time -- the edition sets it
    as one block. Read on a screen that is a wall. Break it at sentence ends
    into paragraphs of a readable size, never inside a brace-quotation, so
    scripture is never split across a paragraph break. */
/** The same breaks, but as ranges into the original string — the quotation
    spans are measured against that string, so a paragraph has to know where
    it starts. */
function paragraphRanges(text, target = 620) {
  const src = text || '';
  const balanced = (s, e) => {
    const seg = src.slice(s, e);
    return (seg.match(/\{/g) || []).length === (seg.match(/\}/g) || []).length;
  };
  const pieces = [];
  const re = /[^.!?؟؛]+[.!?؟؛]*\s*/g;
  let m;
  while ((m = re.exec(src)) !== null) {
    if (!m[0]) { re.lastIndex++; continue; }
    let s = m.index;
    const end = m.index + m[0].length;
    while (end - s > target * 2) {
      const windowEnd = Math.min(end, s + target);
      const seg = src.slice(s, windowEnd);
      let cut = -1;
      for (const ch of ['،', ',', ' ']) {
        const i = seg.lastIndexOf(ch);
        if (i > target * 0.4) { cut = s + i + 1; break; }
      }
      if (cut < 0 || !balanced(s, cut)) break;
      pieces.push([s, cut]);
      s = cut;
    }
    pieces.push([s, end]);
  }
  if (!pieces.length) return [[0, src.length]];

  const out = [];
  let start = pieces[0][0];
  let end = start;
  for (const [, pe] of pieces) {
    end = pe;
    if (end - start >= target && balanced(start, end)) {
      out.push([start, end]);
      start = end;
    }
  }
  if (end > start) out.push([start, end]);
  return out;
}


/** One block of the opened answer, in the page's language only, broken into
    paragraphs, with every quotation in it marked where it actually falls. */
function reading(f, block, used) {
  const answer = block === 'a' ? ' answer' : '';
  const refs = refsOf(f.id);
  const useEn = state.lang === 'en' && f.qe && f.ae;
  const lang = useEn ? 'en' : 'ar';
  const text = (block === 'q' ? (useEn ? f.qe : f.qa) : (useEn ? f.ae : f.aa)) || '';
  const spans = spansOf(f.id, block, lang);
  const cls = useEn ? 'read-en' : 'read-ar';
  const attrs = useEn ? '' : ' lang="ar" dir="rtl"';
  const pending = state.lang === 'en' && !useEn && block === 'q'
    ? `<p class="pending">${STR.en.pending}</p>` : '';
  return pending + paragraphRanges(text)
    .map(([s, e]) => `<p class="${cls}${answer}"${attrs}>` +
      `${renderQuoted(text.slice(s, e), spans, refs, null, lang, s, used)}</p>`)
    .join('');
}

function plainText(f) {
  const L = t();
  const en = state.lang === 'en' && f.ae;
  const q = en ? f.qe : f.qa;
  const a = en ? f.ae : f.aa;
  return `${L.question}:\n${q}\n\n${L.answer}:\n${a}\n\n` +
    `${state.lang === 'ar' ? 'مجموع الفتاوى' : 'Majmūʿ al-Fatāwā'} — ${L.citeVol(f.v, f.ps, f.pe)}`;
}

/* ------------------------------------------------------------------- apply --- */
function apply() {
  const wasReading = state.readingId;
  readUrl();
  els.input.value = state.query;
  if (!state.ready) return;

  compute();
  if (state.readingId) {
    renderReading(state.readingId);
    return;
  }
  // Coming back out of a passage: put the reader back where they left off.
  // Held in state, not a local, because leaving a passage fires both popstate
  // and hashchange — the second render would otherwise throw away the element
  // the first one had just focused.
  if (wasReading && !state.readingId) state.returnFocusId = wasReading;
  els.reading.hidden = true;
  els.reading.innerHTML = '';
  els.results.hidden = false;
  els.more.hidden = false;
  renderHead();
  if (state.mode === 'blank') {
    els.results.innerHTML = '';
    els.more.innerHTML = '';
    document.title = 'Search · MAJMŪʿ';
  } else {
    renderList(false);
  }
  if (state.returnFocusId) {
    // Deferred by a turn: leaving a passage fires popstate and hashchange, and
    // focusing during the first would only be undone by the second re-render.
    const wanted = state.returnFocusId;
    state.returnFocusId = null;
    setTimeout(() => {
      const back = els.results.querySelector(`.result[data-id="${wanted}"] [data-read]`);
      if (back) back.focus({ preventScroll: true });
    }, 0);
  }
}

/* ------------------------------------------------------------ language, ground */
function setLang(lang, persist) {
  state.lang = lang;
  els.body.dataset.lang = lang;
  els.root.lang = lang;
  els.root.dir = lang === 'ar' ? 'rtl' : 'ltr';
  els.input.placeholder = t().placeholder;
  els.input.dir = lang === 'ar' ? 'rtl' : 'ltr';
  for (const b of document.querySelectorAll('[data-lang-btn]')) {
    b.setAttribute('aria-pressed', String(b.dataset.langBtn === lang));
  }
  // Only a click is a preference. Writing on load would make "never chose"
  // indistinguishable from "chose English", and an Arabic question would then
  // keep opening the English page.
  if (persist) { try { localStorage.setItem('majmu:lang', lang); } catch (e) {} }
  if (state.ready) apply();
}

function setTheme(theme, persist) {
  state.theme = theme;
  els.root.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]')
    .setAttribute('content', theme === 'night' ? '#201f1d' : '#f3f2f2');
  if (persist) { try { localStorage.setItem('majmu:theme', theme); } catch (e) {} }
}

function setReadsize(px) {
  state.readsize = Math.max(-3, Math.min(9, px));
  els.root.style.setProperty('--readsize', state.readsize + 'px');
  try { localStorage.setItem('majmu:readsize', String(state.readsize)); } catch (e) {}
}

let toastTimer;
function toast(msg) {
  els.toast.textContent = msg;
  els.toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => els.toast.classList.remove('show'), 1700);
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch (e) {
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
  }
  toast(t().copied);
}

/* ------------------------------------------------------------------ wiring --- */
els.form.addEventListener('submit', (e) => {
  e.preventDefault();
  const q = els.input.value.trim();
  // Submitting nothing used to do nothing at all, with no word as to why.
  if (!q) { els.input.focus(); toast(t().askSomething); return; }
  go({ q });
});

for (const b of document.querySelectorAll('[data-lang-btn]')) {
  b.addEventListener('click', () => setLang(b.dataset.langBtn, true));
}
for (const b of document.querySelectorAll('[data-theme-btn]')) {
  b.addEventListener('click', () => setTheme(state.theme === 'night' ? 'day' : 'night', true));
}
for (const c of document.querySelectorAll('#blank .chip')) {
  c.addEventListener('click', () => go({ q: c.textContent.trim() }));
}

// One delegated listener for everything the results and the reading view carry.
document.addEventListener('click', (e) => {
  const target = (sel) => e.target.closest(sel);

  const cat = target('[data-cat]');
  if (cat) {
    if (cat.dataset.cat) go({ cat: cat.dataset.cat });
    return;
  }
  const read = target('[data-read]');
  if (read) {
    location.hash = '#f/' + read.closest('.result').dataset.id;
    return;
  }
  const sim = target('[data-similar]');
  if (sim) {
    const art = sim.closest('.result');
    const f = state.byId.get(art.dataset.id);
    const near = similar(f, 5);
    art.querySelectorAll('.nearby-block').forEach((n) => n.remove());
    if (!near.length) return;
    const box = document.createElement('div');
    box.className = 'nearby-block';
    box.innerHTML =
      `<span class="a-label">${STR[state.lang].similarTo}` +
      `${state.lang === 'en' ? ' this question' : ' هذه المسألة'}</span>` +
      near.map((hit) => nearbyRow(hit.f)).join('');
    art.querySelector('.result-main').appendChild(box);
    return;
  }
  if (target('[data-back]')) {
    if (history.length > 1) history.back();
    else { location.hash = ''; apply(); }
    return;
  }
  const size = target('[data-size]');
  if (size) { setReadsize(state.readsize + (+size.dataset.size)); return; }
  if (target('[data-copy-text]')) {
    const f = state.byId.get(state.readingId);
    if (f) copy(plainText(f));
    return;
  }
  if (target('[data-copy-link]')) {
    // Share the indexable page, not the fragment: #f/<id> is invisible to
    // every crawler and to anyone the link is forwarded to without JavaScript.
    copy(state.readingId
      ? new URL(`f/${state.readingId}.html`, location.href).href
      : location.href);
  }
});

window.addEventListener('popstate', apply);
window.addEventListener('hashchange', apply);
document.addEventListener('keydown', (e) => {
  if (e.key === '/' && document.activeElement !== els.input) {
    e.preventDefault();
    els.input.focus();
    els.input.select();
  }
  if (e.key === 'Escape' && state.readingId) {
    if (history.length > 1) history.back(); else { location.hash = ''; apply(); }
  }
});

/* -------------------------------------------------------------------- init --- */
(() => {
  const lang = storedLang();
  let theme = null;
  let size = null;
  try {
    theme = localStorage.getItem('majmu:theme');
    size = localStorage.getItem('majmu:readsize');
  } catch (e) { /* private mode: the defaults stand */ }

  // A question typed in Arabic opens the Arabic page: the passages coming back
  // are Arabic either way, so the page meets them in their own language.
  const q = new URLSearchParams(location.search).get('q');
  setLang(lang === 'ar' || (q && hasArabic(q)) ? 'ar' : 'en');
  setTheme(theme === 'night' ? 'night' : 'day');
  setReadsize(parseInt(size || '0', 10) || 0);
  readUrl();
  els.input.value = state.query;
  els.blank.hidden = state.mode !== 'blank';
  load();
})();

// Debug handle for tuning the ranking; harmless in production.
window.__majmu = { state, search, similar };
