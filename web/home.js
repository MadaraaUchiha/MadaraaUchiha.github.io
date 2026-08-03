/* MAJMŪʿ — the landing page.
 *
 * The bilingual switch, the topic chips, the volume lattice and the figures
 * were an inline script on index.html; they are here so the page can be cached
 * and so the ground below has somewhere to live.
 *
 * The ground is the point: real sentences of the text drifting up behind the
 * search. Nothing here is written for the page. Every line is a whole sentence
 * from Majmūʿ al-Fatāwā, cut and marked by scripts/build_web_data.py, and a
 * Qur'ānic quotation inside one is ruled in gold exactly as it is on the
 * reading pages -- an unidentified narration gets the broken rule the site
 * uses when it can say "these are quoted words" and no more.
 */
(() => {
  'use strict';

  const body = document.body;
  const REDUCE = window.matchMedia('(prefers-reduced-motion: reduce)');
  const toArabic = (n) => String(n).replace(/\d/g, (d) => '٠١٢٣٤٥٦٧٨٩'[d]);

  /* ── the bilingual switch ─────────────────────────────────────────────── */

  const PLACEHOLDER = {
    en: 'Ask a question, or name a topic…',
    ar: 'اسأل عن مسألة، أو اذكر باباً…'
  };
  const setLang = (lang, persist) => {
    body.dataset.lang = lang;
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
    for (const b of document.querySelectorAll('[data-lang-btn]')) {
      b.setAttribute('aria-pressed', String(b.dataset.langBtn === lang));
    }
    for (const i of document.querySelectorAll('input[name="q"]')) {
      i.placeholder = PLACEHOLDER[lang];
      i.lang = lang;
      i.dir = lang === 'ar' ? 'rtl' : 'ltr';
    }
    // Only a click is a preference: writing on load would make "never chose"
    // indistinguishable from "chose English", and the search page reads this
    // same key to decide whether an Arabic question opens the Arabic page.
    if (persist) { try { localStorage.setItem('majmu:lang', lang); } catch (e) {} }
  };
  for (const b of document.querySelectorAll('[data-lang-btn]')) {
    b.addEventListener('click', () => setLang(b.dataset.langBtn, true));
  }
  let saved = null;
  try { saved = localStorage.getItem('majmu:lang'); } catch (e) {}
  setLang(saved === 'ar' ? 'ar' : 'en');

  /* ── one screen, exactly ─────────────────────────────────────────────── */

  /* The beacon is the viewport less the masthead. The masthead's height is not
     a constant -- it moves with the font, the language and the viewport -- so
     it is measured rather than guessed at, and measured again on a resize. */
  const nav = document.querySelector('.nav');
  const measureNav = () => {
    if (!nav) return;
    document.documentElement.style.setProperty(
      '--navh', Math.round(nav.getBoundingClientRect().height) + 'px');
  };
  measureNav();
  window.addEventListener('resize', measureNav);
  // the masthead sets in Cormorant; its height settles when the face lands
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(measureNav);

  /* ── the search: the page's one action ───────────────────────────────── */

  // The nav used to carry a Search button that did nothing but focus this
  // field. The nav is static, so it never outlives the hero it sits above --
  // the button only ever existed a few hundred pixels from the field itself,
  // with both on screen at once. Two ways to reach one thing, in view of each
  // other, is one too many; the field is the page's one action.
  const firstField = document.querySelector('#seek input[name="q"]');
  for (const c of document.querySelectorAll('.chip')) {
    c.addEventListener('click', () => {
      firstField.value = c.textContent.trim();
      firstField.dir = c.lang === 'ar' ? 'rtl' : 'ltr';
      firstField.focus();
    });
  }

  /* ── the volume lattice, and the figures ──────────────────────────────── */

  // Thirty-five, not the thirty-seven of the spine: 36 and 37 are the edition's
  // indexes and hold no fatāwā, and a tile leading to an empty volume is a
  // promise broken.
  const VOLUMES = 35;
  const grid = document.getElementById('volGrid');
  const drawLattice = (volumes) => {
    grid.innerHTML = '';
    const frag = document.createDocumentFragment();
    const tiles = [];
    for (const v of volumes) {
      const a = document.createElement('a');
      a.className = 'vol';
      a.href = 'search.html?vol=' + v;
      a.innerHTML = `<span class="en">${v}</span><span class="ar" lang="ar">${toArabic(v)}</span>`;
      tiles.push(a);
      frag.appendChild(a);
    }
    grid.appendChild(frag);
    return tiles;
  };
  // Drawn once from the served count so the page is never blank, then redrawn
  // from what the data actually holds. Hard-coding the number is how this page
  // came to offer volumes 36 and 37, which are the edition's indexes and hold
  // no fatāwā: a door with nothing behind it.
  drawLattice(Array.from({ length: VOLUMES }, (_, i) => i + 1));

  const group = (n, lang) => lang === 'ar' ? toArabic(n) : Number(n).toLocaleString('en');

  /* The figures arrive at their value rather than appearing at it, once, when
     the row is first scrolled to. Asked for stillness, they are simply there. */
  const countUp = (el, value) => {
    const lang = el.lang === 'ar' ? 'ar' : 'en';
    const land = () => { el.textContent = group(value, lang); };
    if (REDUCE.matches) { land(); return; }
    const t0 = performance.now(), dur = 1100;
    let raf = 0;
    const tick = () => {
      const u = Math.min(1, (performance.now() - t0) / dur);
      const e = 1 - Math.pow(1 - u, 3);
      el.textContent = group(Math.round(value * e), lang);
      if (u < 1) raf = requestAnimationFrame(tick); else land();
    };
    raf = requestAnimationFrame(tick);
    /* A frame callback is not a promise: a backgrounded tab, or a page the
       browser has stopped painting, never runs one. The figure is the point
       and the animation is not, so it lands on a timer regardless. */
    setTimeout(() => { cancelAnimationFrame(raf); land(); }, dur + 900);
  };

  /* Revalidated, not versioned. These files are rewritten by every build, and a
     hand-kept ?v= cannot track that -- miss a bump and the page goes on
     printing a number the data no longer says, out of the reader's own cache.
     'no-cache' still uses the cached bytes when they are current; it just
     always asks first, which for 444 bytes is a 304 and nothing else. */
  fetch('data/stats.json', { cache: 'no-cache' })
    .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .then((s) => {
      const pending = [];
      for (const el of document.querySelectorAll('[data-stat]')) {
        const value = s[el.dataset.stat];
        if (typeof value !== 'number') continue;
        // "1,675" leads with a one, which needs the deeper optical inset; any
        // other figure does not.
        el.classList.toggle('lead-one', el.lang !== 'ar' && String(value)[0] === '1');
        pending.push([el, value]);
      }
      const stats = document.querySelector('.stats');
      const write = () => { for (const [el, value] of pending) el.textContent = group(value, el.lang === 'ar' ? 'ar' : 'en'); };
      /* A figure counts up only if the reader has not already seen it sitting
         there: arriving at a number, then having it drop to nought and climb
         back, is a glitch and not an effect. Until the row is reached, the
         served figures in the markup stand -- as they do when this fetch
         fails altogether. */
      if (!stats || !pending.length || !('IntersectionObserver' in window) || REDUCE.matches) {
        write();
        return;
      }
      let landed = false;
      const io = new IntersectionObserver((entries) => {
        const hit = entries.find((e) => e.isIntersecting);
        if (!hit || landed) return;
        landed = true;
        io.disconnect();
        // already on screen when the data landed: no animation, just the truth
        if (hit.intersectionRatio > 0.9) { write(); return; }
        for (const [el, value] of pending) countUp(el, value);
      }, { threshold: [0, 0.95] });
      io.observe(stats);
      /* An observer is delivered on the rendering steps, which a page the
         browser is not painting never takes. These figures are the page's
         facts, not an effect, so they stop waiting on it after a few seconds
         and simply say what the data says. */
      setTimeout(() => {
        if (landed) return;
        landed = true;
        io.disconnect();
        write();
      }, 4000);

      // The volumes the corpus actually holds, in order — so a volume added
      // later appears on its own, and one that holds nothing is never offered.
      const vols = s.volumes || {};
      const present = Object.keys(vols).map(Number).filter((v) => vols[v] > 0)
        .sort((a, b) => a - b);
      if (present.length) {
        const tiles = drawLattice(present);
        present.forEach((v, i) => {
          const n = vols[v];
          tiles[i].title = `${Number(n).toLocaleString('en')} fatwas · ${toArabic(n)} فتوى`;
        });
        grid.setAttribute('aria-label',
          `Volumes ${present[0]} to ${present[present.length - 1]}`);
      }
    })
    .catch(() => { /* the served figures stand */ });

  /* ── the ground: his sentences, rising ───────────────────────────────── */

  /* Enough of the corpus to fill the air before data/home-lines.json lands, and
     to keep filling it if that file never does. Verbatim, with their volume. */
  const SERVED = [
    { v: 1, s: [['قال الله تعالى: ', 0], ['﴿وإن استنصروكم في الدين فعليكم النصر﴾', 1], [' والنصر المطلق هو خلق ما به يغلب العدو ولا يقدر عليه إلا الله.', 0]] },
    { v: 1, s: [['قال تعالى: ', 0], ['﴿الله يصطفي من الملائكة رسلا ومن الناس﴾', 1], [' ومن أنكر هذه الوسائط فهو كافر بإجماع أهل الملل.', 0]] },
    { v: 1, s: [['الحمد لله رب العالمين، إن أراد بذلك أنه لا بد من واسطة تبلغنا أمر الله: فهذا حق.', 0]] },
    { v: 1, s: [['بل هذا مما يعلم بالاضطرار من دين الإسلام؛ أنه لا يجوز إطلاقه.', 0]] },
    { v: 1, s: [['ثم اتفق أهل السنة والجماعة أنه يشفع في أهل الكبائر وأنه لا يخلد في النار من أهل التوحيد أحد.', 0]] },
    { v: 2, s: [['فقالوا له: ', 0], ['«فاقض ما أنت قاض إنما تقضي هذه الحياة الدنيا»', 2], [' والدولة لك فصح قول فرعون: ', 0], ['﴿أنا ربكم الأعلى﴾', 1], [' وإن كان عين الحق.', 0]] },
    { v: 2, s: [['وهو ', 0], ['﴿الذي خلق السماوات والأرض وجعل الظلمات والنور ثم الذين كفروا بربهم يعدلون﴾', 1], ['.', 0]] },
    { v: 2, s: [['قال: اترك نفسك وتعال - أي اترك اتباع هواك والاعتماد على نفسك - فيكون عملك لله واستعانتك بالله كما قال تعالى: ', 0], ['﴿فاعبده وتوكل عليه﴾', 1], ['.', 0]] },
    { v: 2, s: [['قال: ومن أسمائه الحسنى العلي؛ على من وما ثم إلا هو؛ وعن ماذا وما هو إلا هو.', 0]] },
    { v: 2, s: [['تشتمل على أصلين باطلين مخالفين لدين المسلمين واليهود والنصارى مع مخالفتهما للمنقول والمعقول.', 0]] },
    { v: 4, s: [['ولما سئل " مالك بن أنس " - رحمه الله تعالى - فقيل له: يا أبا عبد الله ', 0], ['﴿الرحمن على العرش استوى﴾', 1], [' كيف استوى؟', 0]] },
    { v: 4, s: [['وقوله: ', 0], ['﴿تعرج الملائكة والروح إليه﴾', 1], [' وقوله: ', 0], ['﴿تنزل الملائكة والروح فيها بإذن ربهم﴾', 1], ['.', 0]] },
    { v: 4, s: [['على قولين: فقيل: فيهم رسل لقوله تعالى ', 0], ['﴿يا معشر الجن والإنس ألم يأتكم رسل منكم﴾', 1], ['.', 0]] },
    { v: 5, s: [['وقال أبو ذر: لقد توفي رسول الله صلى الله عليه وسلم وما طائر يقلب جناحيه في السماء إلا ذكر لنا منه علما.', 0]] },
    { v: 5, s: [['والمقصود: أنه تعالى وصف نفسه بالمعية وبالقرب.', 0]] },
    { v: 5, s: [['وروى عبد الله بن أحمد وغيره بأسانيد صحاح عن ابن المبارك أنه قيل له: بم نعرف ربنا؟', 0]] },
    { v: 6, s: [['هو القائم بنفسه أو الموجود أو غير ذلك من المقالات وطعنوا في أدلة نفاة الجسم بكلام طويل لا يتسع له الجواب هنا.', 0]] },
    { v: 6, s: [['الحمد لله، الجواب عن هذا السؤال مبني على " مقدمتين ".', 0]] }
  ];

  const sky = document.querySelector('[data-rising]');
  if (!sky) return;

  /* A phone gets fewer lines, smaller, and hung closer to the right edge: a
     sentence is wider than the screen there, and starting it further in would
     clip away most of it for no gain. */
  const narrow = window.innerWidth < 760;
  const lanes = narrow ? 8 : 16;
  const SIZE = narrow ? [12, 20] : [15, 29];
  const INSET = narrow ? [0.5, 26] : [1, 62];
  const rand = (a, b) => a + Math.random() * (b - a);
  let pool = SERVED.slice();
  let cursor = Math.floor(Math.random() * pool.length);

  /* Never the same sentence twice in the air at once, and never the same one
     twice running in a lane: walk the pool rather than sampling it. */
  const nextLine = () => pool[(cursor++) % pool.length];

  const dress = (node) => {
    const line = nextLine();
    node.textContent = '';
    for (const [run, kind] of line.s) {
      if (kind === 0) { node.appendChild(document.createTextNode(run)); continue; }
      const s = document.createElement('span');
      // the same two marks the reading pages use: gold rule for scripture,
      // a broken one for words quoted but not identified
      s.className = kind === 1 ? 'ayah' : 'narr';
      s.textContent = run;
      node.appendChild(s);
    }
    node.style.setProperty('--x', rand(INSET[0], INSET[1]).toFixed(2) + '%');
    node.style.setProperty('--op', rand(0.055, 0.135).toFixed(3));
    node.style.setProperty('--drift', rand(-34, 34).toFixed(0) + 'px');
    node.style.fontSize = rand(SIZE[0], SIZE[1]).toFixed(1) + 'px';
  };

  const frag = document.createDocumentFragment();
  const rows = [];
  for (let i = 0; i < lanes; i++) {
    const n = document.createElement('div');
    n.className = 'rise';
    n.lang = 'ar';
    n.dir = 'rtl';
    dress(n);
    rows.push(n);
    frag.appendChild(n);
  }
  sky.appendChild(frag);

  if (REDUCE.matches) {
    /* Asked to stop, it stops: the sentences are simply there, at rest, spread
       down the ground. The page still says what it is made of. */
    rows.forEach((n, i) => {
      n.classList.add('rise--still');
      n.style.top = (4 + i * (92 / lanes)).toFixed(1) + '%';
    });
  } else {
    rows.forEach((n) => {
      const dur = rand(34, 68);
      n.style.setProperty('--dur', dur.toFixed(1) + 's');
      // a negative delay starts each lane part-way up, so the ground is full
      // from the first frame instead of filling for the first minute
      n.style.setProperty('--delay', (-rand(0, dur)).toFixed(1) + 's');
      n.addEventListener('animationiteration', () => dress(n));
    });
    // nothing drifts while it cannot be seen
    if ('IntersectionObserver' in window) {
      const io = new IntersectionObserver(([e]) => {
        sky.classList.toggle('is-out', !e.isIntersecting);
      }, { threshold: 0 });
      io.observe(sky);
    }
  }

  /* The whole corpus's worth, fetched behind first paint. Two hundred sentences
     across all thirty-five volumes; until it lands the served ten are flying. */
  fetch('data/home-lines.json', { cache: 'no-cache' })
    .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .then((d) => {
      if (!Array.isArray(d.lines) || !d.lines.length) return;
      const lines = d.lines.slice();
      for (let i = lines.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [lines[i], lines[j]] = [lines[j], lines[i]];
      }
      pool = lines;
      cursor = 0;
      // the lines already in the air keep their sentence and finish their climb
    })
    .catch(() => { /* the served sentences stand */ });
})();
