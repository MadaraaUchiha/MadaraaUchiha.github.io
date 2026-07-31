"""Command-line Q&A / search over the indexed corpus.

  python scripts/ask.py "Is it permissible to seek help from the dead?"
  python scripts/ask.py --search "الاستغاثة بغير الله"
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from src import config
from src.retrieve import get_retriever


def cite(p):
    c = f"{p['work']}, vol {p['volume']}, p. {p['page_start']}"
    if p["page_end"] != p["page_start"]:
        c += f"-{p['page_end']}"
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="+")
    ap.add_argument("--search", action="store_true",
                    help="retrieval only (no LLM, no API key needed)")
    ap.add_argument("-k", type=int, default=config.TOP_K_FUSED)
    args = ap.parse_args()
    query = " ".join(args.query)

    retriever = get_retriever()

    if args.search:
        for n, h in enumerate(retriever.search(query, k=args.k), 1):
            p = h.passage
            print(f"\n[S{n}] {cite(p)}  (relevance {h.dense_score:.2f})")
            print(p["text_ar"][:400])
        return

    try:
        from src.rag import answer
        result = answer(query, k=args.k)
    except Exception as e:  # noqa: BLE001
        print(f"[AI answer unavailable: {e}]\n\nFalling back to passage search:\n")
        for n, h in enumerate(retriever.search(query, k=args.k), 1):
            p = h.passage
            print(f"\n[S{n}] {cite(p)}  (relevance {h.dense_score:.2f})")
            print(p["text_ar"][:400])
        return

    print("\n=== ANSWER ===\n")
    print(result.answer)
    print(f"\n(retrieval match: {result.retrieval_confidence:.0%})")
    print("\n=== SOURCES ===")
    for n, h in enumerate(result.hits, 1):
        print(f"\n[S{n}] {cite(h.passage)}")


if __name__ == "__main__":
    main()
