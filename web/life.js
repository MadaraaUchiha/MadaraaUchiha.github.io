/* The Life of Ibn Taymiyyah — the station road.
 *
 * Ported from the Claude Design handoff ("Interactive life of the Shaykh").
 * The design ran inside that tool's React host, and a good deal of its script
 * existed only to survive it: a stage-assertion pass after every render, a
 * bounded schedule of re-assertions, and a check for an animation timeline that
 * never starts. None of that applies to a plain page that owns its own DOM, so
 * none of it is here. Everything the reader can see is.
 *
 * Two things the design does not have, both marked below: it honours
 * prefers-reduced-motion, and the world outline is fetched from this origin
 * rather than from a CDN.
 */
(() => {
  'use strict';

  const REDUCE = window.matchMedia('(prefers-reduced-motion: reduce)');

  const GT_LIGHT = '#7d5411'; /* --color-accent-700, the ramp step the design system names for text on a light ground */
  const GT_DARK = '#e1ad66';  /* --color-accent-400, the step it names for a dark ground */

  /* The six grounds. A station names one and the whole page crossfades to it. */
  const MOODS = {
    paper: { ground: '#f3f2f2', ink: '#201f1d', muted: '#605d5d', rule: 'rgba(32,31,29,.16)', land: '#e6e1dc', coast: 'rgba(32,31,29,.22)', mat: 'rgba(243,242,242,.9)', goldtext: GT_LIGHT },
    warm:  { ground: '#f6efe4', ink: '#201f1d', muted: '#6b5f4c', rule: 'rgba(58,39,13,.16)', land: '#eee4d2', coast: 'rgba(58,39,13,.2)',  mat: 'rgba(246,239,228,.9)', goldtext: GT_LIGHT },
    ash:   { ground: '#d9d5d2', ink: '#2d2b2b', muted: '#5d5959', rule: 'rgba(45,43,43,.24)', land: '#cfc9c4', coast: 'rgba(45,43,43,.3)',  mat: 'rgba(217,213,210,.9)', goldtext: '#6b4710' },
    ink:   { ground: '#14120e', ink: '#eae7e7', muted: '#9b9797', rule: 'rgba(234,231,231,.16)', land: '#211d16', coast: 'rgba(234,231,231,.18)', mat: 'rgba(20,18,14,.86)', goldtext: GT_DARK },
    gold:  { ground: '#fff3e4', ink: '#3a270d', muted: '#7d5411', rule: 'rgba(58,39,13,.2)',  land: '#f7e4c8', coast: 'rgba(58,39,13,.24)', mat: 'rgba(255,243,228,.9)', goldtext: GT_LIGHT },
    dawn:  { ground: '#f8f4f4', ink: '#201f1d', muted: '#605d5d', rule: 'rgba(32,31,29,.14)', land: '#efe9e2', coast: 'rgba(32,31,29,.18)', mat: 'rgba(248,244,244,.9)', goldtext: GT_LIGHT }
  };

  const CITIES = {
    harran:     { n: 'Ḥarrān',     ar: 'حرّان',       c: [39.03, 36.86] },
    damascus:   { n: 'Damascus',   ar: 'دمشق',        c: [36.30, 33.51] },
    aleppo:     { n: 'Aleppo',     ar: 'حلب',         c: [37.16, 36.20] },
    hama:       { n: 'Ḥamā',       ar: 'حماة',        c: [36.75, 35.13], o: [11, -6] },
    hims:       { n: 'Ḥimṣ',       ar: 'حمص',         c: [36.72, 34.73], o: [11, 16] },
    acre:       { n: 'ʿAkkā',      ar: 'عكّا',        c: [35.07, 32.93], o: [-11, -2, 'end'] },
    jerusalem:  { n: 'Jerusalem',  ar: 'القدس',       c: [35.23, 31.78], o: [11, 14] },
    kasrawan:   { n: 'Kasrawān',   ar: 'كسروان',      c: [35.65, 33.98], o: [-11, -4, 'end'] },
    shaqhab:    { n: 'Shaqḥab',    ar: 'شقحب',        c: [36.24, 33.36], o: [11, 24] },
    cairo:      { n: 'Cairo',      ar: 'القاهرة',     c: [31.24, 30.04] },
    alexandria: { n: 'Alexandria', ar: 'الإسكندرية',  c: [29.92, 31.20] },
    baghdad:    { n: 'Baghdad',    ar: 'بغداد',       c: [44.36, 33.31] },
    tabriz:     { n: 'Tabrīz',     ar: 'تبريز',       c: [46.29, 38.08] },
    mecca:      { n: 'Makka',      ar: 'مكة',         c: [39.83, 21.42] },
    medina:     { n: 'Madīna',     ar: 'المدينة',     c: [39.61, 24.47] },
    basra:      { n: 'Baṣra',      ar: 'البصرة',      c: [47.81, 30.51] },
    karak:      { n: 'al-Karak',   ar: 'الكرك',       c: [35.70, 31.18] },
    mardin:     { n: 'Mārdīn',     ar: 'ماردين',      c: [40.74, 37.31] }
  };

  /* kind drives the stroke, so the map reads without colour: what he chose is
     drawn solid, what was done to him is broken. */
  const KINDS = {
    flight:  { dash: '7 5',  w: 1.6, label: 'Flight' },
    war:     { dash: '',     w: 2.2, label: 'Campaign' },
    hajj:    { dash: '',     w: 1.7, label: 'Pilgrimage' },
    mission: { dash: '2 4',  w: 1.6, label: 'Sent to plead' },
    exile:   { dash: '12 6', w: 1.6, label: 'Banished' },
    ret:     { dash: '',     w: 1.3, label: 'Return' }
  };

  const ROUTES = {
    'harran-damascus': { a: 'harran', b: 'damascus', bend: -0.18, order: 1, year: 667, kind: 'flight', st: 3,
      label: 'The flight · 667', note: 'The family runs from the Mongol advance and does not stop for four hundred miles. He is six years old, and he will never see Ḥarrān again.' },
    'damascus-acre': { a: 'damascus', b: 'acre', bend: 0.28, order: 2, year: 690, kind: 'war', st: 14,
      label: 'ʿAkkā · 690', note: 'Scholars of every school go out to the siege of the last crusader city on the coast. Those who were there said he showed a bravery they could not properly describe.' },
    'damascus-medina': { a: 'damascus', b: 'medina', bend: 0.16, order: 3, year: 692, kind: 'hajj', st: 15,
      label: 'The ḥajj road · 692', note: 'The Syrian caravan, some forty days south through Bosrā, Maʿān and Tabūk. The one journey in his life that nobody forced on him.' },
    'medina-mecca': { a: 'medina', b: 'mecca', bend: 0.14, order: 4, year: 692, kind: 'hajj', st: 15,
      label: 'Madīna to Makka · 692', note: 'Iḥrām at the mīqāt, then ṭawāf, saʿy and ʿArafa. Thirty six years later he would swear by this ground when he spoke of his own teacher.' },
    'damascus-kasrawan': { a: 'damascus', b: 'kasrawan', bend: -0.4, order: 5, year: 699, kind: 'war', st: 19,
      label: 'Kasrawān · 699 and 704', note: 'Twice up into the mountains behind Beirut with the Mamlūk column. In the same year he walks out to sit in front of Ghāzān.' },
    'damascus-cairo-1': { a: 'damascus', b: 'cairo', bend: 0.2, order: 6, year: 700, kind: 'mission', st: 20,
      label: 'To move the sultan · 700', note: 'The people of Shām send him to Cairo. When al-Nāṣir Muḥammad hesitates he tells him that Syria will find another sultan who can defend it.' },
    'damascus-shaqhab': { a: 'damascus', b: 'shaqhab', bend: 0.5, order: 7, year: 702, kind: 'war', st: 20,
      label: 'Shaqḥab · 702', note: 'Ramaḍān, south of Damascus. He gives the army the fatwā to break the fast and eats along the ranks so the soldiers will see him do it.' },
    'damascus-cairo-2': { a: 'damascus', b: 'cairo', bend: -0.24, order: 8, year: 705, kind: 'exile', st: 21,
      label: 'Banished · 705', note: 'Cleared by three councils and sent away all the same. In Damascus he was too loved to touch. In Cairo he was a stranger, and his enemies knew it.' },
    'cairo-alexandria': { a: 'cairo', b: 'alexandria', bend: -0.5, order: 9, year: 708, kind: 'exile', st: 24,
      label: 'To the tower · 708', note: 'Seven months shut in a tower of the sultan’s palace by the sea. He comes out of it with his refutation of the logicians.' },
    'alexandria-cairo': { a: 'alexandria', b: 'cairo', bend: 0.5, order: 10, year: 709, kind: 'ret', st: 25,
      label: 'Recalled · 709', note: 'Al-Nāṣir Muḥammad takes back the throne and sends for him, then asks him for a fatwā to kill the men who slandered him. He forgives them instead.' },
    'cairo-damascus': { a: 'cairo', b: 'damascus', bend: 0.34, order: 11, year: 712, kind: 'ret', st: 26,
      label: 'Home · 712', note: 'Home with the army after seven years and a few days. In these years he begins teaching a young man the world would come to know as Ibn Qayyim al-Jawziyya.' }
  };

  const SVGNS = 'http://www.w3.org/2000/svg';
  const svgEl = (t, a) => {
    const n = document.createElementNS(SVGNS, t);
    for (const k in a) n.setAttribute(k, a[k]);
    return n;
  };
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  };

  class Road {
    constructor(root) {
      this.root = root;
      this.chapters = Array.from(root.querySelectorAll('[data-ch]'));
      this.knotWrap = root.querySelector('[data-knots]');
      this.track = root.querySelector('[data-track]');
      this.mapLayer = root.querySelector('[data-maplayer]');
      this.mapSvg = root.querySelector('[data-mapsvg]');
      this.yearBox = root.querySelector('[data-threadyear]');
      this.yAH = root.querySelector('[data-yah]');
      this.yCE = root.querySelector('[data-yce]');
      this.counter = root.querySelector('[data-counter]');
      this.mwBox = root.querySelector('[data-meanwhilebox]');
      this.mwText = root.querySelector('[data-meanwhiletext]');
      this.themeMeta = document.querySelector('meta[name="theme-color"]');
      /* everything outside a lens, made unreachable while one is open */
      this.behind = Array.from(root.querySelectorAll('.top, .deck, .mw, .thread, .arrow'));
      this.i = -1;
      this.lens = null;
      this.buildThread();
      this.buildIndex();
      this.bind();
      this.initMap();
      this.go(0, true);
    }

    /* ---------- navigation ---------- */

    /* A station sits on the thread partly where its year falls and partly where
       it falls in the telling: two thirds the calendar, one third the order, so
       that a cluster of years in one decade does not pile into one knot. */
    pos(i) {
      const ys = this.chapters.map((s) => +s.dataset.y);
      const lo = 653, hi = 731;
      const t = (ys[i] - lo) / (hi - lo);
      const e = i / Math.max(1, this.chapters.length - 1);
      return (0.68 * t + 0.32 * e) * 100;
    }

    posYear(y) {
      const ys = this.chapters.map((s) => +s.dataset.y);
      if (y <= ys[0]) return this.pos(0);
      for (let i = 0; i < ys.length - 1; i++) {
        if (y >= ys[i] && y <= ys[i + 1]) {
          const span = ys[i + 1] - ys[i];
          const f = span === 0 ? 0 : (y - ys[i]) / span;
          return this.pos(i) + (this.pos(i + 1) - this.pos(i)) * f;
        }
      }
      return this.pos(ys.length - 1);
    }

    buildThread() {
      const frag = document.createDocumentFragment();
      this.knots = this.chapters.map((s, i) => {
        const b = el('button', 'knot');
        b.type = 'button';
        b.dataset.i = i;
        b.setAttribute('aria-label', s.dataset.screenLabel || ('Station ' + i));
        b.appendChild(el('span'));
        b.style.left = this.pos(i) + '%';
        frag.appendChild(b);
        return b;
      });
      this.knotWrap.appendChild(frag);
      this.buildCaptivity();
    }

    /* the hatched bars over the thread: the years he spent behind a wall */
    buildCaptivity() {
      const box = this.root.querySelector('[data-captivity]');
      if (!box) return;
      const spans = [
        [705.6, 707.1, 'The citadel of Cairo, eighteen months'],
        [708.2, 708.9, 'The tower at Alexandria, seven months'],
        [720.1, 720.6, 'The citadel of Damascus, five months'],
        [726.2, 728.0, 'The citadel of Damascus, two years, and death']
      ];
      spans.forEach(([a, b, label]) => {
        const x1 = this.posYear(a), x2 = this.posYear(b);
        const d = el('div');
        d.title = label;
        d.style.left = x1 + '%';
        d.style.width = Math.max(0.5, x2 - x1) + '%';
        box.appendChild(d);
      });
    }

    buildIndex() {
      const grid = this.root.querySelector('[data-indexgrid]');
      if (!grid) return;
      const tail = grid.querySelector('[data-indextail]');
      this.chapters.forEach((s, i) => {
        const label = (s.dataset.screenLabel || '').replace(/^\d+\s*/, '');
        const b = el('button', 'idx-cell');
        b.type = 'button';
        b.dataset.jump = i;
        b.appendChild(el('span', 'idx-y', String(i).padStart(2, '0') + ' · ' + s.dataset.y + ' AH'));
        b.appendChild(el('span', 'idx-t', label));
        grid.insertBefore(b, tail);
      });
      this.fitIndexTail();
    }

    /* The index auto-fills its columns, so thirty-three stations leave a ragged
       last row at most widths -- and the grid draws its hairlines by showing its
       own background through 1px gaps, which turns that gap into a grey slab.
       The closing tile takes exactly the columns left over, or a full row when
       none are, so the lattice always ends square. */
    fitIndexTail() {
      const grid = this.root.querySelector('[data-indexgrid]');
      const tail = grid && grid.querySelector('[data-indextail]');
      if (!tail) return;
      const tracks = getComputedStyle(grid).gridTemplateColumns;
      const cols = tracks && tracks !== 'none' ? tracks.split(' ').filter(Boolean).length : 0;
      if (!cols) return;
      const over = this.chapters.length % cols;
      tail.style.gridColumn = 'span ' + (over === 0 ? cols : cols - over);
    }

    bind() {
      this.root.addEventListener('mouseover', (e) => {
        const t = e.target.closest && e.target.closest('[data-atlasitem],[data-route]');
        if (!t || !this.lens || this.lens.dataset.lens !== 'atlas') return;
        clearTimeout(this._playT);
        this.atlasShow(t.dataset.atlasitem || t.dataset.route);
      });

      this.root.addEventListener('click', (e) => {
        const t = e.target.closest('[data-next],[data-prev],[data-i],[data-jump],[data-lensbtn],[data-lensclose],[data-book],[data-atlasitem],[data-atlasplay],[data-atlasall],[data-route]');
        if (!t) return;
        if (t.hasAttribute('data-book')) { this.showBook(t); return; }
        if (t.dataset.atlasitem) { clearTimeout(this._playT); this.atlasShow(t.dataset.atlasitem); return; }
        if (t.dataset.route) { clearTimeout(this._playT); this.atlasShow(t.dataset.route); return; }
        if (t.hasAttribute('data-atlasplay')) { this.atlasPlay(); return; }
        if (t.hasAttribute('data-atlasall')) { clearTimeout(this._playT); this.atlasShow(null); return; }
        if (t.hasAttribute('data-next')) this.go(this.i + 1);
        else if (t.hasAttribute('data-prev')) this.go(this.i - 1);
        else if (t.dataset.jump !== undefined) { this.closeLens(); this.go(+t.dataset.jump); }
        else if (t.dataset.i !== undefined) this.go(+t.dataset.i);
        else if (t.dataset.lensbtn) this.openLens(t.dataset.lensbtn);
        else if (t.hasAttribute('data-lensclose')) this.closeLens();
      });

      window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') { this.closeLens(); return; }
        if (this.lens) return;
        /* a station can scroll, and space is how you scroll it: only take the
           key when the press did not land inside a text field or a control */
        const tag = (e.target.tagName || '').toLowerCase();
        if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
        if (e.key === 'ArrowRight' || e.key === 'PageDown') { e.preventDefault(); this.go(this.i + 1); }
        else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); this.go(this.i - 1); }
        else if (e.key === 'Home') { e.preventDefault(); this.go(0); }
        else if (e.key === 'End') { e.preventDefault(); this.go(this.chapters.length - 1); }
      });

      const scrub = (clientX) => {
        const r = this.track.getBoundingClientRect();
        const p = ((clientX - r.left) / r.width) * 100;
        let best = 0, bd = Infinity;
        this.chapters.forEach((_, i) => {
          const d = Math.abs(this.pos(i) - p);
          if (d < bd) { bd = d; best = i; }
        });
        this.go(best);
      };
      const bar = this.root.querySelector('[data-thread]');
      bar.addEventListener('pointerdown', (e) => {
        if (e.target.closest('[data-i]')) return;
        /* Only the track band is a control. The captivity bars sit just above it
           and the legends below it are static type; neither should scrub. */
        const tr = this.track.getBoundingClientRect();
        if (e.clientY < tr.top - 20 || e.clientY > tr.bottom + 18) return;
        this.dragging = true;
        bar.setPointerCapture(e.pointerId);
        scrub(e.clientX);
      });
      bar.addEventListener('pointermove', (e) => { if (this.dragging) scrub(e.clientX); });
      bar.addEventListener('pointerup', () => { this.dragging = false; });
      bar.addEventListener('pointercancel', () => { this.dragging = false; });

      let t = null;
      window.addEventListener('resize', () => {
        clearTimeout(t);
        t = setTimeout(() => {
          this.drawMap();
          this.applyMapView(this.chapters[this.i], true);
          /* both of these are drawn against measured pixels, so a resize
             leaves them pointing at where things used to be */
          if (this.lens && this.lens.dataset.lens === 'atlas') this.renderAtlas(this.lens);
          if (this.lens && this.lens.dataset.lens === 'isnad') this.renderIsnad(this.lens);
          /* a new width is a new column count, and a new remainder to close */
          this.fitIndexTail();
        }, 160);
      });
    }

    go(n, instant) {
      const N = this.chapters.length;
      if (REDUCE.matches) instant = true;
      n = Math.max(0, Math.min(N - 1, n));
      if (n === this.i) return;
      const prev = this.chapters[this.i];
      const cur = this.chapters[n];
      const fwd = n > this.i;
      this.i = n;

      if (prev) {
        prev.style.opacity = '0';
        prev.style.pointerEvents = 'none';
        prev.style.transform = 'translateY(' + (fwd ? -18 : 18) + 'px)';
        /* it stays rendered, but not hittable, until its own fade is done. The
           timer is kept per section: a shared handle would let fast navigation
           cancel the pending hide of all but the most recent, and strand
           sections on screen. */
        clearTimeout(prev.__hideT);
        prev.__hideT = setTimeout(() => {
          if (this.chapters[this.i] !== prev) prev.style.visibility = 'hidden';
        }, instant ? 0 : 1000);
      }
      clearTimeout(cur.__hideT);
      cur.style.visibility = 'visible';
      cur.style.transition = 'none';
      cur.style.transform = 'translateY(' + (instant ? 0 : (fwd ? 18 : -18)) + 'px)';
      cur.getBoundingClientRect();
      cur.style.transition = instant ? 'none' : 'opacity 1000ms ease, transform 1000ms cubic-bezier(.2,.7,.2,1)';
      cur.style.opacity = '1';
      cur.style.pointerEvents = 'auto';
      cur.style.transform = 'none';

      this.applyMood(MOODS[cur.dataset.mood] || MOODS.paper);
      this.applyMapView(cur, instant);
      this.updateThread();
      this.updateMeanwhile(cur);
      if (cur.dataset.onEnter === 'crowd') this.crowd(cur);
    }

    applyMood(m) {
      const s = this.root.style;
      s.setProperty('--ground', m.ground);
      s.setProperty('--ink', m.ink);
      s.setProperty('--muted', m.muted);
      s.setProperty('--rule', m.rule);
      s.setProperty('--land', m.land);
      s.setProperty('--coast', m.coast);
      s.setProperty('--mat', m.mat);
      s.setProperty('--goldtext', m.goldtext);
      /* the browser chrome travels with the ground, as it does on the other
         pages of this site */
      if (this.themeMeta) this.themeMeta.setAttribute('content', m.ground);
    }

    updateThread() {
      const p = this.pos(this.i);
      this.yearBox.style.left = p + '%';
      const y = +this.chapters[this.i].dataset.y;
      this.yAH.textContent = y;
      this.yCE.textContent = Math.round(y - (y / 33.7) + 622) + ' CE';
      this.counter.textContent = 'Station ' + String(this.i).padStart(2, '0') +
        ' of ' + String(this.chapters.length - 1).padStart(2, '0');
      /* At either end the arrow is not merely faded: inert takes it out of the
         tab order too, so a keyboard does not land on a button it cannot see. */
      const atStart = this.i === 0, atEnd = this.i === this.chapters.length - 1;
      this.root.querySelectorAll('[data-prev]').forEach((b) => {
        b.style.opacity = atStart ? '0' : '';
        b.inert = atStart;
      });
      this.root.querySelectorAll('[data-next]').forEach((b) => {
        if (b.closest('[data-ch]')) return; /* the overture's own Begin button is not the arrow */
        b.style.opacity = atEnd ? '0' : '';
        b.inert = atEnd;
      });
      this.knots.forEach((b, i) => {
        b.setAttribute('aria-current', i === this.i ? 'true' : 'false');
        b.classList.toggle('past', i < this.i);
      });
    }

    updateMeanwhile(cur) {
      const t = cur.dataset.meanwhile;
      this.mwBox.style.opacity = t ? '1' : '0';
      if (t) this.mwText.textContent = t;
    }

    /* ---------- the map ---------- */

    async initMap() {
      if (!(window.d3 && window.d3.geoMercator && window.topojson)) return;
      try {
        /* Vendored, not fetched from a CDN: see scripts/fetch_map.py. */
        const r = await fetch('vendor/world-110m.json');
        if (!r.ok) throw new Error('world atlas ' + r.status);
        const topo = await r.json();
        this.land = topojson.merge(topo, topo.objects.countries.geometries);
        this.borders = topojson.mesh(topo, topo.objects.countries, (a, b) => a !== b);
        this.drawMap();
        if (this.i >= 0) this.applyMapView(this.chapters[this.i], true);
        if (this.lens && this.lens.dataset.lens === 'atlas') this.renderAtlas(this.lens);
      } catch (err) {
        /* the road still reads without its ground: every station is type */
        console.warn('map', err);
      }
    }

    drawMap() {
      if (!this.land || !this.mapSvg) return;
      const r = this.mapSvg.getBoundingClientRect();
      const w = Math.max(320, r.width), h = Math.max(240, r.height);
      const proj = d3.geoMercator().fitExtent([[40, 40], [w - 40, h - 40]],
        { type: 'MultiPoint', coordinates: [[27, 20.5], [49, 39.5]] });
      this.proj = proj;
      const path = d3.geoPath(proj);
      const grat = d3.geoGraticule().step([5, 5]);
      this.mapSvg.setAttribute('viewBox', '0 0 ' + w + ' ' + h);
      this.mapSvg.innerHTML = '';
      const g = svgEl('g', {});
      g.style.transition = 'transform 1500ms cubic-bezier(.35,.02,.15,1)';
      g.style.transformOrigin = '0 0';
      this.mapG = g;
      this.mapSvg.appendChild(g);
      const defs = svgEl('defs', {});
      const mk = svgEl('marker', { id: 'stage-arrow', viewBox: '0 0 10 10', refX: 8, refY: 5, markerWidth: 4.5, markerHeight: 4.5, orient: 'auto-start-reverse' });
      mk.appendChild(svgEl('path', { d: 'M0,1 L9,5 L0,9 z', fill: 'var(--gold)' }));
      defs.appendChild(mk);
      this.mapSvg.appendChild(defs);
      g.appendChild(svgEl('rect', { x: -w * 4, y: -h * 4, width: w * 9, height: h * 9, fill: 'var(--coast)', opacity: .05 }));
      g.appendChild(svgEl('path', { d: path(grat()), fill: 'none', stroke: 'var(--coast)', 'stroke-width': .4, opacity: .35 }));
      g.appendChild(svgEl('path', { d: path(this.land), fill: 'var(--land)', stroke: 'var(--coast)', 'stroke-width': 1 }));
      g.appendChild(svgEl('path', { d: path(this.borders), fill: 'none', stroke: 'var(--coast)', 'stroke-width': .4, opacity: .3, 'stroke-dasharray': '2 3' }));
      this.routeG = svgEl('g', {}); g.appendChild(this.routeG);
      this.pinG = svgEl('g', {}); g.appendChild(this.pinG);
    }

    xy(key) { const c = CITIES[key]; return c ? this.proj(c.c) : null; }

    arc(a, b, bend) {
      const [x1, y1] = a, [x2, y2] = b;
      const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
      const dx = x2 - x1, dy = y2 - y1;
      return 'M' + x1 + ',' + y1 + ' Q' + (mx - dy * bend) + ',' + (my + dx * bend) + ' ' + x2 + ',' + y2;
    }

    applyMapView(cur, instant) {
      if (!cur) return;
      const op = cur.dataset.mapop ?? '.25';
      this.mapLayer.style.opacity = op;
      if (!this.proj || !this.mapG) return;
      const reduce = REDUCE.matches;
      const r = this.mapSvg.getBoundingClientRect();
      const w = Math.max(320, r.width), h = Math.max(240, r.height);

      const k = +(cur.dataset.zoom || 1);
      const f = (cur.dataset.focus || '37,33').split(',').map(Number);
      const p = this.proj(f);
      /* the focus sits right of centre, because the prose sits on the left */
      const cx = w * 0.66;
      this.mapG.style.transition = (instant || reduce) ? 'none' : 'transform 1500ms cubic-bezier(.35,.02,.15,1)';
      this.mapG.style.transform = 'translate(' + (cx - k * p[0]) + 'px,' + (h * 0.5 - k * p[1]) + 'px) scale(' + k + ')';
      if (instant && !reduce) {
        this.mapG.getBoundingClientRect();
        this.mapG.style.transition = 'transform 1500ms cubic-bezier(.35,.02,.15,1)';
      }

      this.routeG.innerHTML = '';
      this.pinG.innerHTML = '';
      /* strokes and radii are given in screen pixels, so they are divided back
         out of whatever the station's zoom multiplies them by */
      const inv = 1 / k;

      const names = (cur.dataset.routes || '').split(',').filter(Boolean);
      const pins = new Set((cur.dataset.pins || '').split(',').filter(Boolean));
      names.forEach((rn, idx) => {
        const R = ROUTES[rn]; if (!R) return;
        pins.add(R.a); pins.add(R.b);
        const a = this.xy(R.a), b = this.xy(R.b); if (!a || !b) return;
        const d = this.arc(a, b, R.bend);
        this.routeG.appendChild(svgEl('path', { d, fill: 'none', stroke: 'var(--coast)', 'stroke-width': 3 * inv, opacity: .18 }));
        const K = KINDS[R.kind] || { w: 1.6, dash: '5 4' };
        const line = svgEl('path', {
          d, fill: 'none', stroke: 'var(--gold)', 'stroke-width': K.w * inv,
          'stroke-linecap': 'round', 'marker-end': 'url(#stage-arrow)',
          'stroke-dasharray': K.dash ? K.dash.split(' ').map((v) => +v * inv).join(' ') : ''
        });
        this.routeG.appendChild(line);
        if (reduce) return;
        const L = line.getTotalLength();
        line.style.strokeDasharray = L;
        line.style.strokeDashoffset = L;
        line.style.transition = 'stroke-dashoffset 1900ms cubic-bezier(.5,0,.2,1) ' + (400 + idx * 300) + 'ms';
        line.getBoundingClientRect();
        line.style.strokeDashoffset = '0';
        /* a traveller walking the road as it draws */
        const dot = svgEl('circle', { r: 3.2 * inv, fill: 'var(--gold)' });
        this.routeG.appendChild(dot);
        const t0 = performance.now() + 400 + idx * 300;
        const step = () => {
          const u = Math.min(1, Math.max(0, (performance.now() - t0) / 1900));
          const pt = line.getPointAtLength(u * L);
          dot.setAttribute('cx', pt.x);
          dot.setAttribute('cy', pt.y);
          dot.setAttribute('opacity', u >= 1 ? 0 : 1);
          if (u < 1 && this.routeG.contains(dot)) setTimeout(step, 24);
        };
        setTimeout(step, 24);
      });

      pins.forEach((key) => {
        const c = CITIES[key]; if (!c) return;
        const [x, y] = this.proj(c.c);
        const gg = svgEl('g', {});
        if (!reduce) gg.style.animation = 'omRise 700ms ease both';
        gg.appendChild(svgEl('circle', { cx: x, cy: y, r: 3.2 * inv, fill: 'var(--gold)' }));
        gg.appendChild(svgEl('circle', { cx: x, cy: y, r: 7 * inv, fill: 'none', stroke: 'var(--gold)', 'stroke-width': .8 * inv, opacity: .5 }));
        const o = c.o || [10, 4];
        const lab = svgEl('text', { x: x + o[0] * inv, y: y + (o[1] + 4) * inv, fill: 'var(--ink)', 'text-anchor': o[2] || 'start', 'font-family': "'Cormorant Garamond',serif", 'font-size': 15 * inv });
        lab.textContent = c.n;
        gg.appendChild(lab);
        const lab2 = svgEl('text', { x: x + o[0] * inv, y: y + (o[1] + 20) * inv, 'text-anchor': o[2] || 'start', fill: 'var(--gold)', 'font-family': "'Amiri',serif", 'font-size': 13 * inv, opacity: .8 });
        lab2.textContent = c.ar;
        gg.appendChild(lab2);
        this.pinG.appendChild(gg);
      });
    }

    /* ---------- lenses ---------- */

    openLens(name) {
      const node = this.root.querySelector('[data-lens="' + name + '"]');
      if (!node) return;
      this.closeLens();
      this.lens = node;
      /* where focus goes back to on close. The masthead button is the fallback
         when the lens was opened from something that cannot take focus back --
         a station's own link, or nothing at all. */
      const a = document.activeElement;
      this._opener = (a && a !== document.body && this.root.contains(a) && !node.contains(a))
        ? a : this.root.querySelector('.lensbtn[data-lensbtn="' + name + '"]');
      node.classList.add('on');
      this.behind.forEach((n) => { n.inert = true; });
      this.root.querySelectorAll('[data-lensbtn]').forEach((b) => {
        b.setAttribute('aria-expanded', String(b.dataset.lensbtn === name));
      });
      if (name === 'atlas') this.renderAtlas(node);
      else if (name === 'isnad') this.renderIsnad(node);
      else if (name === 'index') this.fitIndexTail();
      const close = node.querySelector('[data-lensclose]');
      if (close) close.focus();
    }

    closeLens() {
      if (!this.lens) return;
      clearTimeout(this._playT);
      this.lens.classList.remove('on');
      this.lens = null;
      this.behind.forEach((n) => { n.inert = false; });
      /* that just un-inerted both arrows, including the one the current station
         wants kept out of the way */
      this.updateThread();
      this.root.querySelectorAll('[data-lensbtn]').forEach((b) => b.setAttribute('aria-expanded', 'false'));
      if (this._opener && this._opener.isConnected) this._opener.focus();
      this._opener = null;
    }

    /* ---------- the funeral ---------- */

    crowd(sec) {
      const reduce = REDUCE.matches;
      const box = sec.querySelector('[data-crowd]');
      const out = sec.querySelector('[data-crowdcount]');
      if (box) {
        box.innerHTML = '';
        const frag = document.createDocumentFragment();
        for (let i = 0; i < 1600; i++) {
          const d = el('div', 'crowd-dot');
          const s = (1.4 + Math.random() * 2.4).toFixed(1);
          d.style.left = (Math.random() * 100).toFixed(2) + '%';
          d.style.top = (Math.random() * 100).toFixed(2) + '%';
          d.style.width = s + 'px';
          d.style.height = s + 'px';
          if (!reduce) d.style.transition = 'opacity 1200ms ease ' + Math.round(Math.random() * 3200) + 'ms';
          frag.appendChild(d);
        }
        box.appendChild(frag);
        box.getBoundingClientRect();
        Array.from(box.children).forEach((c) => { c.style.opacity = (0.18 + Math.random() * 0.62).toFixed(2); });
      }
      if (out) {
        const target = 500000;
        if (reduce) { out.textContent = target.toLocaleString('en-US') + '+'; return; }
        const t0 = performance.now(), dur = 3400;
        out.textContent = '0';
        const tick = () => {
          const u = Math.min(1, (performance.now() - t0) / dur);
          const e = 1 - Math.pow(1 - u, 3);
          out.textContent = Math.round(target * e).toLocaleString('en-US') + (u >= 1 ? '+' : '');
          if (u < 1) setTimeout(tick, 40);
        };
        setTimeout(tick, 40);
      }
    }

    /* ---------- the atlas lens ---------- */

    renderAtlas(node) {
      const svg = node.querySelector('[data-atlassvg]');
      if (!svg) return;
      this.buildAtlasList(node);
      /* opened before the geometry landed: draw the roads as soon as it does */
      if (!this.land || !window.d3) return;
      const r = svg.getBoundingClientRect();
      const w = Math.max(360, r.width), h = Math.max(280, r.height);
      const proj = d3.geoMercator().fitExtent([[58, 50], [w - 58, h - 50]],
        { type: 'MultiPoint', coordinates: [[28, 20], [48.5, 38.8]] });
      const path = d3.geoPath(proj);
      svg.setAttribute('viewBox', '0 0 ' + w + ' ' + h);
      svg.innerHTML = '';

      const defs = svgEl('defs', {});
      const head = svgEl('marker', { id: 'atlas-arrow', viewBox: '0 0 10 10', refX: 8, refY: 5, markerWidth: 5, markerHeight: 5, orient: 'auto-start-reverse' });
      head.appendChild(svgEl('path', { d: 'M0,1 L9,5 L0,9 z', fill: 'var(--gold)' }));
      defs.appendChild(head);
      svg.appendChild(defs);

      /* sea first, so the land reads as a plate rather than an outline */
      svg.appendChild(svgEl('rect', { x: 0, y: 0, width: w, height: h, fill: 'var(--coast)', opacity: .06 }));
      svg.appendChild(svgEl('path', { d: path(d3.geoGraticule().step([5, 5])()), fill: 'none', stroke: 'var(--coast)', 'stroke-width': .4, opacity: .22 }));
      svg.appendChild(svgEl('path', { d: path(this.land), fill: 'var(--land)', stroke: 'var(--coast)', 'stroke-width': 1.1 }));
      svg.appendChild(svgEl('path', { d: path(this.borders), fill: 'none', stroke: 'var(--coast)', 'stroke-width': .4, opacity: .22, 'stroke-dasharray': '2 3' }));

      const routeG = svgEl('g', {}); svg.appendChild(routeG);
      const dotG = svgEl('g', {}); svg.appendChild(dotG);

      const keys = Object.keys(ROUTES).sort((a, b) => ROUTES[a].order - ROUTES[b].order);
      const visits = {};
      keys.forEach((k) => {
        visits[ROUTES[k].a] = (visits[ROUTES[k].a] || 0) + 1;
        visits[ROUTES[k].b] = (visits[ROUTES[k].b] || 0) + 1;
      });

      const drawn = {};
      keys.forEach((k) => {
        const R = ROUTES[k], K = KINDS[R.kind];
        const a = proj(CITIES[R.a].c), b = proj(CITIES[R.b].c);
        const d = this.arc(a, b, R.bend);
        const g = svgEl('g', { 'data-route': k, style: 'cursor:pointer' });
        /* a fat invisible line so a hair-thin road is still easy to hit */
        g.appendChild(svgEl('path', { d, fill: 'none', stroke: 'transparent', 'stroke-width': 16 }));
        const line = svgEl('path', { d, fill: 'none', stroke: 'var(--gold)', 'stroke-width': K.w, 'stroke-linecap': 'round', 'stroke-dasharray': K.dash, 'marker-end': 'url(#atlas-arrow)' });
        g.appendChild(line);
        const t = document.createElementNS(SVGNS, 'title');
        t.textContent = R.year + ' AH  ' + R.label;
        g.appendChild(t);
        routeG.appendChild(g);
        drawn[k] = { g, line, len: line.getTotalLength() };
      });

      const named = new Set();
      keys.forEach((k) => { named.add(ROUTES[k].a); named.add(ROUTES[k].b); });
      const pts = Object.keys(CITIES).map((k) => {
        const c = CITIES[k], p = proj(c.c);
        return { key: k, c, x: p[0], y: p[1] };
      });
      pts.forEach((p) => {
        const g = svgEl('g', {});
        if (named.has(p.key)) {
          /* a place he was sent to more than once gets a larger mark */
          const n = visits[p.key] || 1;
          g.appendChild(svgEl('circle', { cx: p.x, cy: p.y, r: 3 + Math.min(n, 6) * 0.9, fill: 'var(--gold)' }));
          g.appendChild(svgEl('circle', { cx: p.x, cy: p.y, r: 3 + Math.min(n, 6) * 0.9 + 5, fill: 'none', stroke: 'var(--gold)', 'stroke-width': .8, opacity: .4 }));
        } else {
          g.appendChild(svgEl('circle', { cx: p.x, cy: p.y, r: 1.8, fill: 'var(--coast)', opacity: .55 }));
        }
        dotG.appendChild(g);
        p.g = g;
      });

      /* place each label in the first of sixteen slots that does not overlap
         something already placed, and lead a hairline back to the dot when the
         label had to go far */
      const taken = pts.map((p) => ({ l: p.x - 9, r: p.x + 9, t: p.y - 9, b: p.y + 9 }));
      const over = (a) => taken.reduce((s2, b) =>
        s2 + Math.max(0, Math.min(a.r, b.r) - Math.max(a.l, b.l)) * Math.max(0, Math.min(a.b, b.b) - Math.max(a.t, b.t)), 0);
      const SLOTS = [[13, 4, 'start'], [-13, 4, 'end'], [13, -13, 'start'], [-13, -13, 'end'], [13, 20, 'start'], [-13, 20, 'end'], [0, -20, 'middle'], [0, 32, 'middle'], [13, -30, 'start'], [-13, -30, 'end'], [13, 36, 'start'], [-13, 36, 'end'], [26, -46, 'start'], [-26, -46, 'end'], [26, 52, 'start'], [-26, 52, 'end']];
      pts.filter((p) => named.has(p.key)).sort((a, b) => a.y - b.y).forEach((p) => {
        const t1 = svgEl('text', { fill: 'var(--ink)', 'font-family': "'Cormorant Garamond',serif", 'font-size': 16 });
        t1.textContent = p.c.n;
        const t2 = svgEl('text', { fill: 'var(--gold)', 'font-family': "'Amiri',serif", 'font-size': 13, opacity: .85 });
        t2.textContent = p.c.ar;
        p.g.appendChild(t1); p.g.appendChild(t2);
        const wd = Math.max(t1.getComputedTextLength(), t2.getComputedTextLength());
        let chosen = null, box = null, best = Infinity;
        for (const sl of SLOTS) {
          const left = sl[2] === 'start' ? p.x + sl[0] : sl[2] === 'end' ? p.x + sl[0] - wd : p.x + sl[0] - wd / 2;
          const cand = { l: left - 3, r: left + wd + 3, t: p.y + sl[1] - 15, b: p.y + sl[1] + 26 };
          const cost = over(cand);
          if (cost === 0) { chosen = sl; box = cand; break; }
          if (cost < best) { best = cost; chosen = sl; box = cand; }
        }
        taken.push(box);
        [t1, t2].forEach((t, i2) => {
          t.setAttribute('x', p.x + chosen[0]);
          t.setAttribute('y', p.y + chosen[1] + (i2 ? 20 : 4));
          t.setAttribute('text-anchor', chosen[2]);
        });
        if (Math.abs(chosen[0]) > 20 || Math.abs(chosen[1]) > 26) {
          const ax = Math.max(box.l, Math.min(p.x, box.r)), ay = Math.max(box.t, Math.min(p.y, box.b));
          p.g.insertBefore(svgEl('path', { d: 'M' + p.x + ',' + p.y + ' L' + ax + ',' + ay, stroke: 'var(--gold)', 'stroke-width': .8, fill: 'none', opacity: .5 }), t1);
        }
      });

      this._atlas = { svg, drawn, keys };
      this.atlasShow(null);
    }

    buildAtlasList(node) {
      const list = node.querySelector('[data-atlaslist]');
      if (!list || list.childElementCount) return;
      const keys = Object.keys(ROUTES).sort((a, b) => ROUTES[a].order - ROUTES[b].order);
      keys.forEach((k) => {
        const R = ROUTES[k];
        const b = el('button', 'atlas-item');
        b.type = 'button';
        b.dataset.atlasitem = k;
        b.setAttribute('aria-pressed', 'false');
        b.appendChild(el('span', 'atlas-y', String(R.year)));
        const right = el('span', null, CITIES[R.a].n + ' to ' + CITIES[R.b].n);
        right.appendChild(el('span', 'atlas-kind', KINDS[R.kind].label));
        b.appendChild(right);
        list.appendChild(b);
      });
    }

    /* null shows every road at rest; a key isolates one and walks a traveller
       along it */
    atlasShow(key) {
      const node = this.root.querySelector('[data-lens="atlas"]');
      const A = this._atlas;
      if (!A || !A.svg.isConnected) return;
      A.keys.forEach((k) => {
        const D = A.drawn[k], on = !key || k === key;
        D.line.setAttribute('opacity', on ? (key ? 1 : .55) : .1);
        D.line.setAttribute('marker-end', on ? 'url(#atlas-arrow)' : '');
      });
      node.querySelectorAll('[data-atlasitem]').forEach((b) => {
        b.setAttribute('aria-pressed', String(b.dataset.atlasitem === key));
      });
      if (A.walker) { A.walker.remove(); A.walker = null; }
      const note = node.querySelector('[data-atlasnote]');
      if (!note) return;
      note.textContent = '';
      if (!key) {
        note.appendChild(el('div', 'eyebrow eyebrow--tiny eyebrow--quiet', 'Hover a road, or pick one'));
        note.lastChild.style.marginBottom = '8px';
        note.appendChild(el('p', null, 'Eleven roads, and only one of them his own idea. He was born in one country, buried in another, and spent seven years in a third because men in a council chamber decided he should.'));
        return;
      }
      const R = ROUTES[key], D = A.drawn[key];
      note.appendChild(el('div', 'eyebrow eyebrow--tiny', R.year + ' AH · ' + KINDS[R.kind].label));
      const h = el('div', null, CITIES[R.a].n + ' to ' + CITIES[R.b].n);
      h.style.cssText = "font-family:var(--font-heading);font-size:19px;line-height:1.15;margin:5px 0 6px;";
      note.appendChild(h);
      const p = el('p', null, R.note);
      p.style.cssText = 'font-size:13px;line-height:1.55;margin:0 0 10px;color:var(--ink);text-align:justify;';
      note.appendChild(p);
      const jump = el('button', 'btn-line btn-line--xs', 'Go to this station');
      jump.type = 'button';
      jump.dataset.jump = R.st;
      note.appendChild(jump);

      if (REDUCE.matches) return;
      const dot = svgEl('circle', { r: 4.2, fill: 'var(--gold)' });
      A.svg.appendChild(dot);
      A.walker = dot;
      const dur = 1600, t0 = performance.now();
      const step = () => {
        if (A.walker !== dot || !dot.isConnected) return;
        const u = Math.min(1, (performance.now() - t0) / dur);
        const pt = D.line.getPointAtLength(u * D.len);
        dot.setAttribute('cx', pt.x);
        dot.setAttribute('cy', pt.y);
        if (u < 1) setTimeout(step, 24);
      };
      step();
    }

    atlasPlay() {
      const A = this._atlas;
      if (!A) return;
      clearTimeout(this._playT);
      let i = 0;
      const next = () => {
        if (!this.lens || this.lens.dataset.lens !== 'atlas') return;
        if (i >= A.keys.length) { this.atlasShow(null); return; }
        this.atlasShow(A.keys[i++]);
        this._playT = setTimeout(next, 2100);
      };
      next();
    }

    /* ---------- the isnād lens ---------- */

    renderIsnad(node) {
      const wrap = node.querySelector('[data-isnadwrap]');
      const svg = node.querySelector('[data-isnadlines]');
      const centre = node.querySelector('[data-node="c"]');
      if (!wrap || !svg || !centre) return;
      /* on a narrow screen the three columns stack and the sheet hides the
         chains: there is nothing to join up */
      if (getComputedStyle(svg).display === 'none') return;
      /* Measured synchronously. The lens is laid out before it is shown --
         .on only changes opacity and visibility, neither of which moves a box
         -- so waiting a frame buys nothing, and a page the browser is not
         painting never gets that frame. */
      const W = wrap.getBoundingClientRect();
      const C = centre.getBoundingClientRect();
      if (!W.width) return;
      svg.setAttribute('viewBox', '0 0 ' + W.width + ' ' + W.height);
      svg.innerHTML = '';
      const nodes = Array.from(wrap.querySelectorAll('[data-node="t"],[data-node="s"]'));
      nodes.forEach((n, idx) => {
        const b = n.getBoundingClientRect();
        const teacher = n.dataset.node === 't';
        const x1 = (teacher ? b.right : b.left) - W.left;
        const y1 = b.top + b.height / 2 - W.top;
        const x2 = (teacher ? C.left : C.right) - W.left;
        const y2 = C.top + C.height / 2 - W.top;
        const mx = (x1 + x2) / 2;
        const p = svgEl('path', {
          d: 'M' + x1 + ',' + y1 + ' C' + mx + ',' + y1 + ' ' + mx + ',' + y2 + ' ' + x2 + ',' + y2,
          fill: 'none', stroke: 'var(--gold)', 'stroke-width': '1', opacity: '.42'
        });
        svg.appendChild(p);
        if (!REDUCE.matches) {
          const L = p.getTotalLength();
          p.style.strokeDasharray = L;
          p.style.strokeDashoffset = L;
          p.style.transition = 'stroke-dashoffset 1100ms cubic-bezier(.4,0,.2,1) ' + (120 + idx * 70) + 'ms, opacity 300ms ease';
          p.getBoundingClientRect();
          p.style.strokeDashoffset = '0';
        }
        n.onmouseenter = () => { p.setAttribute('opacity', '1'); p.setAttribute('stroke-width', '2'); n.classList.add('lit'); };
        n.onmouseleave = () => { p.setAttribute('opacity', '.42'); p.setAttribute('stroke-width', '1'); n.classList.remove('lit'); };
      });
    }

    /* ---------- the library lens ---------- */

    showBook(btn) {
      const panel = this.root.querySelector('[data-bookpanel]');
      if (!panel) return;
      this.root.querySelectorAll('[data-book]').forEach((b) => b.setAttribute('aria-pressed', String(b === btn)));
      const d = btn.dataset;
      panel.textContent = '';

      const ar = el('div', 'book-ar', d.ar);
      ar.lang = 'ar';
      panel.appendChild(ar);
      panel.appendChild(el('h3', null, d.t));
      const hair = el('div', 'hair');
      hair.style.cssText = '--w: 50px; opacity: .55';
      panel.appendChild(hair);

      const defs = el('div', 'defs');
      defs.style.cssText = 'font-size:13.5px;line-height:1.55;';
      defs.appendChild(el('span', 'defs-k', 'When'));
      defs.appendChild(el('span', null, d.w));
      defs.appendChild(el('span', 'defs-k', 'Where'));
      defs.appendChild(el('span', null, d.p));
      panel.appendChild(defs);

      if (btn.hasAttribute('data-prison')) {
        panel.appendChild(el('div', 'book-prison', 'Written under lock and key'));
      }
      panel.appendChild(el('p', 'book-p', d.n));

      /* the one title on this shelf that is also the corpus behind this site */
      if (d.href) {
        const a = el('a', 'btn-line btn-line--xs', 'Read it here');
        a.href = d.href;
        a.style.alignSelf = 'flex-start';
        panel.appendChild(a);
      }
    }
  }

  const root = document.getElementById('stage');
  if (root) new Road(root);
})();
