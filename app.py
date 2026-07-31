"""Islamic Knowledge Engine — search UI (Streamlit).

A calm, readable, single-column reader for Ibn Taymiyyah's Majmu' al-Fatawa:
search by meaning or keyword, read flowing English on demand, and see every
Qur'anic citation identified to the exact verse.

Run:  .venv\\Scripts\\streamlit run app.py
"""
from __future__ import annotations

import re
import streamlit as st

from src import config
from src.retrieve import get_retriever
from src.quran import get_quran

st.set_page_config(page_title="Islamic Knowledge Engine", page_icon="📖",
                   layout="centered", initial_sidebar_state="collapsed")

AYAH_RE = re.compile(r"\{([^{}]+)\}")
SHOW_N = 10

EXAMPLES = [
    "Is it permissible to seek help from the dead?",
    "shortening prayer while travelling",
    "the reality of love of Allah",
    "حكم زيارة القبور",
]

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Spectral:ital,wght@0,400;0,500;0,600;1,400&family=Inter:wght@400;500;600&display=swap');
:root{
  --bg:#faf7f1; --bg2:#f3ede1; --card:#ffffff;
  --ink:#26211a; --muted:#6f6757; --faint:#9a917f;
  --line:#ece5d6; --line2:#e0d6bf;
  --accent:#8a6a2e; --accent2:#6f5320; --gold:#a9842f;
}
.stApp{background:var(--bg);color:var(--ink);}
#MainMenu,footer,[data-testid="stToolbar"],[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"],[data-testid="collapsedControl"]{display:none !important;}
[data-testid="stHeader"]{background:transparent;height:0;}
.block-container{padding-top:2.1rem;padding-bottom:4rem;max-width:760px;}
h1,h2,h3,h4{font-family:'Spectral',Georgia,serif !important;color:var(--ink) !important;font-weight:600;}

/* Masthead */
.mast{text-align:center;margin:.2rem 0 1.3rem;}
.mast .mark{color:var(--gold);font-size:1.5rem;line-height:1;}
.mast .wm{font-family:'Spectral',serif;font-size:2.5rem;font-weight:600;color:var(--ink);
  letter-spacing:.2px;margin:.2rem 0 0;}
.mast .rule{width:60px;height:2px;background:var(--gold);opacity:.6;margin:.7rem auto;}
.mast .corpus{font-family:'Inter',sans-serif;font-size:.85rem;color:var(--muted);letter-spacing:.2px;}

/* Search */
[data-testid="stTextInput"] label{display:none;}
[data-testid="stTextInput"] input{background:var(--card);border:1.5px solid var(--line2);
  border-radius:14px;padding:1rem 1.15rem;font-size:1.1rem;color:var(--ink);
  box-shadow:0 2px 14px rgba(80,60,20,.05);font-family:'Inter',sans-serif;}
[data-testid="stTextInput"] input::placeholder{color:var(--faint);}
[data-testid="stTextInput"] input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(138,106,46,.14);}

/* Buttons */
.stButton button{font-family:'Inter',sans-serif;font-size:.85rem;font-weight:500;
  border-radius:999px;padding:.4rem 1rem;transition:all .15s ease;}
.stButton button[kind="secondary"]{background:var(--card);color:var(--accent2);
  border:1.4px solid var(--line2);}
.stButton button[kind="secondary"]:hover{border-color:var(--accent);color:var(--accent);}
.stButton button[kind="primary"]{background:var(--accent);color:#fff;border:1.4px solid var(--accent);}
.stButton button[kind="primary"]:hover{background:var(--accent2);border-color:var(--accent2);}

/* Result cards */
@keyframes fade{from{opacity:0;transform:translateY(6px);}to{opacity:1;transform:none;}}
[data-testid="stVerticalBlockBorderWrapper"]{background:var(--card);
  border:1px solid var(--line) !important;border-radius:16px;padding:2px;
  box-shadow:0 3px 16px rgba(70,52,18,.045);margin-bottom:14px;
  animation:fade .28s ease both;transition:box-shadow .22s ease,transform .22s ease;}
[data-testid="stVerticalBlockBorderWrapper"]:hover{box-shadow:0 10px 30px rgba(70,52,18,.10);
  transform:translateY(-2px);}
.en-block,.quran-panel{animation:fade .25s ease both;}
.meta-row{display:flex;gap:.45rem;flex-wrap:wrap;align-items:center;margin-bottom:.35rem;}
.badge{font-family:'Inter',sans-serif;font-size:.74rem;font-weight:600;padding:.2rem .6rem;
  border-radius:999px;white-space:nowrap;}
.badge.cite{background:#f1ece0;color:#6a5a36;}
.badge.quran{background:#f6eeda;color:#8a6a1e;border:1px solid #e7d5a4;}
.relbar{height:5px;width:64px;background:#ece4d2;border-radius:3px;overflow:hidden;margin-inline-start:auto;}
.relbar>span{display:block;height:100%;background:var(--gold);opacity:.75;}
.treatise{font-family:'Amiri',serif;font-size:1.05rem;color:var(--accent2);direction:rtl;
  text-align:right;margin:.1rem 0 .55rem;}
.arabic{font-family:'Amiri',serif;font-size:1.6rem;line-height:2.2;color:#231f18;
  direction:rtl;text-align:right;}
.arabic.sm{font-size:1.32rem;line-height:2.05;}
.arabic .ayah{color:var(--gold);font-weight:700;}

/* English block */
.en-block{background:#f7f3ea;border:1px solid #e7ddca;border-radius:12px;
  padding:.85rem 1.05rem;margin:.7rem 0 0;}
.en-label{font-family:'Inter',sans-serif;font-size:10.5px;letter-spacing:.8px;
  text-transform:uppercase;color:var(--faint);margin-bottom:6px;}
.en-text{font-family:'Spectral',Georgia,serif;font-size:1.08rem;line-height:1.78;color:#2c2719;}

/* Qur'an panel */
.quran-panel{background:#fbf5e6;border:1px solid #ebdcb3;border-radius:12px;
  padding:.75rem 1.05rem;margin:.7rem 0 0;}
.qhead{font-family:'Inter',sans-serif;font-size:10.5px;letter-spacing:1px;text-transform:uppercase;
  color:#8a6a1e;font-weight:600;margin-bottom:8px;}
.qrow{border-top:1px solid #f0e3c2;padding:9px 0 5px;}
.qrow:first-of-type{border-top:none;}
.qref a{font-family:'Inter',sans-serif;font-size:12.5px;font-weight:600;color:#8a6a1e;text-decoration:none;}
.qref a:hover{text-decoration:underline;}
.qar{font-family:'Amiri',serif;font-size:1.32rem;line-height:1.95;color:#231f18;
  direction:rtl;text-align:right;margin:4px 0;}
.qen{font-family:'Spectral',serif;font-size:1rem;line-height:1.6;color:#5d5440;font-style:italic;}
.qmore{font-family:'Inter',sans-serif;font-size:11.5px;color:#8a6a1e;margin-top:6px;}

/* Similar + misc */
.sim-head{font-family:'Inter',sans-serif;color:var(--accent2);font-weight:600;font-size:.85rem;
  margin:.7rem 0 .2rem;}
.count{font-family:'Inter',sans-serif;color:var(--muted);font-size:.9rem;margin:.2rem 0 .8rem;}
.hint{font-family:'Inter',sans-serif;color:var(--muted);text-align:center;font-size:.9rem;margin:.5rem 0 .6rem;}
.status{font-family:'Inter',sans-serif;text-align:center;font-size:.78rem;color:var(--faint);margin:.55rem 0 0;}
.status b{color:var(--accent2);font-weight:600;}
.footer{font-family:'Inter',sans-serif;text-align:center;font-size:.76rem;color:var(--faint);
  margin-top:2.4rem;padding-top:1.1rem;border-top:1px solid var(--line);}
html{scroll-behavior:smooth;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_resource(show_spinner="Loading search engine (one-time, ~10s)...")
def _retriever():
    return get_retriever()


@st.cache_resource(show_spinner=False)
def _quran():
    return get_quran()


# --------------------------------------------------------------------------- #
# Render helpers
# --------------------------------------------------------------------------- #
def esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def citation(p: dict) -> str:
    c = f"vol {p['volume']} · p. {p['page_start']}"
    if p["page_end"] != p["page_start"]:
        c += f"–{p['page_end']}"
    return c


def arabic_html(text: str) -> str:
    safe = esc(text)
    safe = AYAH_RE.sub(lambda m: f'<span class="ayah">﴿{m.group(1)}﴾</span>', safe)
    return safe.replace("\n", "<br>")


def relevance_pct(score: float) -> int:
    return max(8, min(100, round((score - 0.30) / 0.45 * 100)))


def english_block(text: str, engine: str) -> str:
    return (f'<div class="en-block"><div class="en-label">English · {esc(engine)}</div>'
            f'<div class="en-text">{esc(text)}</div></div>')


def quran_panel(matches) -> str:
    rows = []
    for m in matches[:5]:
        rows.append(
            f'<div class="qrow"><div class="qref"><a href="{m.url}" target="_blank">'
            f'﴿ Sūrat {m.surah_translit} · {m.ref} ﴾ ↗</a></div>'
            f'<div class="qar">{esc(m.arabic)}</div>'
            f'<div class="qen">{esc(m.english)}</div></div>')
    more = (f'<div class="qmore">+{len(matches) - 5} more verse(s) cited</div>'
            if len(matches) > 5 else "")
    return (f'<div class="quran-panel"><div class="qhead">Qur’ān references identified</div>'
            f'{"".join(rows)}{more}</div>')


def render_card(p: dict, row: int, score: float, prefix: str, show_similar: bool):
    found = [m for m in _quran().identify(p["text_ar"]) if m.found]
    with st.container(border=True):
        meta = [f'<span class="badge cite">{citation(p)}</span>']
        if found:
            meta.append(f'<span class="badge quran">﴿ {len(found)} Qur’ān ﴾</span>')
        meta.append(f'<span class="relbar"><span style="width:{relevance_pct(score)}%"></span></span>')
        st.markdown(f'<div class="meta-row">{"".join(meta)}</div>', unsafe_allow_html=True)
        if p.get("treatise"):
            st.markdown(f'<div class="treatise">📖 {esc(p["treatise"])}</div>',
                        unsafe_allow_html=True)
        cls = "arabic" if show_similar else "arabic sm"
        st.markdown(f'<div class="{cls}">{arabic_html(p["text_ar"])}</div>',
                    unsafe_allow_html=True)

        en_state = f"en_{prefix}_{row}"
        showing = st.session_state.get(en_state, False)
        cols = st.columns([1.6, 1.6, 4]) if show_similar else st.columns([1.7, 5])
        if cols[0].button("Hide English" if showing else "Read in English",
                          key=f"enbtn_{prefix}_{row}", type="primary",
                          use_container_width=True):
            showing = not showing
            st.session_state[en_state] = showing
        if show_similar and cols[1].button("✦ Find similar", key=f"sim_{prefix}_{row}",
                                            type="secondary", use_container_width=True):
            st.session_state.explore = None if st.session_state.explore == row else row

        if showing:
            from src.translate import translate_passage
            with st.spinner("Translating…"):
                en, engine = translate_passage(p["text_ar"])
            st.markdown(english_block(en, engine), unsafe_allow_html=True)

        if found:
            st.markdown(quran_panel(found), unsafe_allow_html=True)

        if show_similar and st.session_state.explore == row:
            st.markdown('<div class="sim-head">✦ Similar passages across the whole book</div>',
                        unsafe_allow_html=True)
            for nb in _retriever().similar(row, k=3):
                render_card(nb.passage, nb.row, nb.dense_score,
                            prefix=f"sim{row}", show_similar=False)


def set_query(text: str):
    st.session_state.q = text
    st.session_state.explore = None


# --------------------------------------------------------------------------- #
# Page
# --------------------------------------------------------------------------- #
st.markdown(
    '<div class="mast"><div class="mark">۞</div>'
    '<div class="wm">Islamic Knowledge Engine</div><div class="rule"></div>'
    '<div class="corpus">Majmūʿ al-Fatāwā · Ibn Taymiyyah (d. 728 AH) · '
    '37 volumes · 16,436 passages</div></div>',
    unsafe_allow_html=True)

st.session_state.setdefault("q", "")
st.session_state.setdefault("explore", None)

retriever = _retriever()
_quran()

st.text_input("Search", key="q",
              placeholder="Ask or search — English or Arabic   ·   e.g. seeking help from the dead")

from src.translate import engine_available
_eng = engine_available()
if "NLLB" in _eng or "local" in _eng:
    st.markdown('<div class="status">Translations use a local fallback · add a free '
                '<a href="https://aistudio.google.com/apikey" target="_blank">Gemini key</a> '
                'for fluent English</div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div class="status">✦ Fluent English translation ready · <b>{_eng}</b></div>',
                unsafe_allow_html=True)

query = st.session_state.q.strip()

if not query:
    st.markdown('<div class="hint">Try one of these to begin</div>', unsafe_allow_html=True)
    cols = st.columns(len(EXAMPLES))
    for col, ex in zip(cols, EXAMPLES):
        disp = ex if len(ex) <= 30 else ex[:28] + "…"
        col.button(disp, key=f"ex_{ex}", on_click=set_query, args=(ex,),
                   use_container_width=True)
else:
    hits = retriever.search(query, k=SHOW_N)
    if not hits:
        st.info("No matching passages found. Try different or broader wording.")
    else:
        st.markdown(f'<div class="count">{len(hits)} passages · most relevant first</div>',
                    unsafe_allow_html=True)
        for h in hits:
            render_card(h.passage, h.row, h.dense_score, prefix="main", show_similar=True)

st.markdown('<div class="footer">Majmūʿ al-Fatāwā · OpenITI text · King Fahd Complex '
            'edition (ed. Ibn Qāsim) · runs locally on your machine</div>',
            unsafe_allow_html=True)
