"""Build the retrieval indexes from passages.jsonl:
  * Dense embeddings (BGE-M3, multilingual) -> embeddings.npy + aligned meta
  * Lexical BM25 (bm25s) over Arabic-normalized tokens -> bm25/ dir

Run:  python -m src.index
"""
from __future__ import annotations

import json
import sys

import numpy as np

from src import config
from src.arabic import clean_for_embedding, tokenize_for_search


def load_passages() -> list[dict]:
    rows = []
    with config.PASSAGES_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_dense(passages: list[dict]) -> None:
    import torch
    from sentence_transformers import SentenceTransformer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Embedding on: {device} "
          f"({torch.cuda.get_device_name(0) if device == 'cuda' else 'CPU'})")

    model_kwargs = {"torch_dtype": torch.float16} if device == "cuda" else {}
    model = SentenceTransformer(config.EMBED_MODEL, device=device,
                                model_kwargs=model_kwargs)
    model.max_seq_length = config.EMBED_MAX_TOKENS

    texts = [clean_for_embedding(p["text_ar"]) for p in passages]
    emb = model.encode(
        texts,
        batch_size=config.EMBED_BATCH,
        normalize_embeddings=True,      # so dot product == cosine
        show_progress_bar=True,
        convert_to_numpy=True,
    ).astype(np.float32)

    np.save(config.EMBEDDINGS_FILE, emb)
    with config.PASSAGE_META_FILE.open("w", encoding="utf-8") as f:
        for p in passages:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"Saved {emb.shape[0]} embeddings (dim={emb.shape[1]}) -> {config.EMBEDDINGS_FILE}")


def build_bm25(passages: list[dict]) -> None:
    import bm25s

    corpus_tokens = [tokenize_for_search(p["text_ar"]) for p in passages]
    retriever = bm25s.BM25()
    retriever.index(corpus_tokens)
    config.BM25_DIR.mkdir(parents=True, exist_ok=True)
    retriever.save(str(config.BM25_DIR))
    print(f"Saved BM25 index ({len(corpus_tokens)} docs) -> {config.BM25_DIR}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    config.ensure_dirs()
    passages = load_passages()
    print(f"Loaded {len(passages)} passages from {config.PASSAGES_FILE}")
    if not passages:
        print("No passages found. Run `python -m src.parse` first.")
        return
    build_dense(passages)
    build_bm25(passages)
    print("\nIndex build complete.")


if __name__ == "__main__":
    main()
