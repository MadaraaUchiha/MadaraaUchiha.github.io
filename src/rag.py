"""Retrieval-Augmented Generation with strict citation grounding.

Design principle: this is a *research/retrieval* tool that surfaces what Ibn
Taymiyyah actually wrote — not a mufti that issues its own rulings. The model
may ONLY answer from the retrieved passages, must cite them, and must say when
the sources do not contain the answer. Every claim is traceable to vol/page.
"""
from __future__ import annotations

from dataclasses import dataclass

from src import config
from src.retrieve import Hit, get_retriever


ANSWER_SYSTEM = """You are a careful research assistant for classical Islamic \
texts. You answer ONLY from the numbered source passages provided (excerpts from \
Ibn Taymiyyah's Majmu' al-Fatawa). You are NOT a mufti and you do NOT issue \
rulings of your own.

Strict rules:
- Use ONLY information present in the SOURCES. Never add outside knowledge, and \
never invent fatwas, quotes, citations, or rulings.
- After each claim, cite the source(s) it comes from using the bracket id, e.g. [S1].
- Quote the key Arabic wording when it matters, then give its English meaning.
- If the sources do not contain enough to answer, say so plainly: "The retrieved \
passages from this volume do not directly address this." Do not guess.
- Distinguish what Ibn Taymiyyah asserts from positions he reports or refutes.
- Be precise and scholarly; preserve technical terms (Tawhid, Shirk, Bid'ah, \
Ijma', Qiyas...) rather than over-simplifying.

Format:
1. A direct answer grounded in the sources, with [S#] citations inline.
2. A short "Sources used" line listing the [S#] you relied on."""


@dataclass
class RagResult:
    question: str
    answer: str
    hits: list[Hit]
    retrieval_confidence: float   # honest heuristic from retrieval scores, 0..1


def _format_sources(hits: list[Hit]) -> str:
    blocks = []
    for n, h in enumerate(hits, 1):
        p = h.passage
        cite = f"{p['work']}, vol {p['volume']}, p. {p['page_start']}"
        if p["page_end"] != p["page_start"]:
            cite += f"-{p['page_end']}"
        blocks.append(f"[S{n}] ({cite})\n{p['text_ar']}")
    return "\n\n".join(blocks)


def _confidence(hits: list[Hit]) -> float:
    """Honest, heuristic 'how well did retrieval match' score (NOT a truth
    probability). Based on the best dense cosine similarity."""
    if not hits:
        return 0.0
    top = max(h.dense_score for h in hits)
    # BGE-M3 relevant matches typically score ~0.5-0.8; map to a readable 0..1.
    return round(min(1.0, max(0.0, (top - 0.3) / 0.5)), 3)


def answer(question: str, k: int | None = None, llm=None) -> RagResult:
    retriever = get_retriever()
    hits = retriever.search(question, k=k or config.TOP_K_FUSED)
    if not hits:
        return RagResult(question, "No matching passages were found.", [], 0.0)

    if llm is None:
        from src.llm import get_llm
        llm = get_llm()

    user = (
        f"QUESTION:\n{question}\n\n"
        f"SOURCES (excerpts from {config.WORK_TITLE}, {config.WORK_EDITION}):\n\n"
        f"{_format_sources(hits)}\n\n"
        "Answer the question using only these sources, with [S#] citations."
    )
    text = llm.complete(ANSWER_SYSTEM, user)
    return RagResult(question, text, hits, _confidence(hits))
