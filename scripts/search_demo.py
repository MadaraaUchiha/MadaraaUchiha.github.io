"""Quick retrieval smoke test (no API key needed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from src.retrieve import get_retriever

QUERIES = [
    "Can I shorten and combine my prayers while travelling?",   # fiqh (later vols)
    "ثلاث طلقات بلفظ واحد",                                       # talaq, vol ~33
    "visiting the graves of the prophets and righteous",        # EN -> AR
]


def main():
    r = get_retriever()
    for q in QUERIES:
        print("=" * 80)
        print(f"QUERY: {q}")
        for n, h in enumerate(r.search(q, k=3), 1):
            p = h.passage
            tr = f" | 📚 {p.get('treatise')}" if p.get("treatise") else ""
            print(f"\n  [{n}] vol {p['volume']} p.{p['page_start']}-{p['page_end']} "
                  f"| dense={h.dense_score:.3f} bm25={h.bm25_score:.2f}{tr}")
            print("  " + p["text_ar"][:240].replace("\n", " "))
        print()


if __name__ == "__main__":
    main()
