"""Hybrid retrieval: dense (BGE-M3) + lexical (BM25), fused with Reciprocal
Rank Fusion. Loads indexes once and answers search() queries.

This module does NOT need an API key — search works fully offline/local.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

from src import config
from src.arabic import clean_for_embedding, tokenize_for_search


@dataclass
class Hit:
    passage: dict
    dense_score: float = 0.0    # cosine similarity (0..1)
    bm25_score: float = 0.0
    rrf_score: float = 0.0
    rank: int = 0
    row: int = -1               # index into the embeddings matrix


class Retriever:
    def __init__(self):
        self.meta: list[dict] = self._load_meta()
        self.embeddings: np.ndarray = np.load(config.EMBEDDINGS_FILE)
        self._model = None          # lazy — only loaded when a query arrives
        self._bm25 = None

    @staticmethod
    def _load_meta() -> list[dict]:
        rows = []
        with config.PASSAGE_META_FILE.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    @property
    def model(self):
        if self._model is None:
            import torch
            from sentence_transformers import SentenceTransformer
            device = "cuda" if torch.cuda.is_available() else "cpu"
            mk = {"torch_dtype": torch.float16} if device == "cuda" else {}
            self._model = SentenceTransformer(config.EMBED_MODEL, device=device,
                                              model_kwargs=mk)
            self._model.max_seq_length = config.EMBED_MAX_TOKENS
        return self._model

    @property
    def bm25(self):
        if self._bm25 is None:
            import bm25s
            self._bm25 = bm25s.BM25.load(str(config.BM25_DIR))
        return self._bm25

    # -- individual retrievers -------------------------------------------------
    def _dense(self, query: str, k: int) -> list[tuple[int, float]]:
        q = self.model.encode([clean_for_embedding(query)],
                              normalize_embeddings=True,
                              convert_to_numpy=True).astype(np.float32)[0]
        scores = self.embeddings @ q
        k = min(k, len(scores))
        idx = np.argpartition(-scores, k - 1)[:k]
        idx = idx[np.argsort(-scores[idx])]
        return [(int(i), float(scores[i])) for i in idx]

    def _bm25_search(self, query: str, k: int) -> list[tuple[int, float]]:
        q_tokens = tokenize_for_search(query)
        if not q_tokens:
            return []
        k = min(k, len(self.meta))
        results, scores = self.bm25.retrieve([q_tokens], k=k)
        # Drop non-positive scores: for a query with no Arabic terms in the
        # vocab, BM25 returns arbitrary zero-scored docs that only add noise.
        return [(int(results[0][j]), float(scores[0][j]))
                for j in range(len(results[0])) if scores[0][j] > 0.0]

    # -- fusion ----------------------------------------------------------------
    def search(self, query: str, k: int | None = None) -> list[Hit]:
        k = k or config.TOP_K_FUSED
        dense = self._dense(query, config.TOP_K_DENSE)
        lexical = self._bm25_search(query, config.TOP_K_BM25)

        dense_rank = {i: r for r, (i, _) in enumerate(dense)}
        lex_rank = {i: r for r, (i, _) in enumerate(lexical)}
        dense_score = {i: s for i, s in dense}
        lex_score = {i: s for i, s in lexical}

        rrf: dict[int, float] = {}
        for i, r in dense_rank.items():
            rrf[i] = rrf.get(i, 0.0) + 1.0 / (config.RRF_K + r)
        for i, r in lex_rank.items():
            rrf[i] = rrf.get(i, 0.0) + 1.0 / (config.RRF_K + r)

        ordered = sorted(rrf.items(), key=lambda kv: -kv[1])[:k]
        hits = []
        for rank, (i, score) in enumerate(ordered):
            hits.append(Hit(
                passage=self.meta[i],
                dense_score=dense_score.get(i, 0.0),
                bm25_score=lex_score.get(i, 0.0),
                rrf_score=score,
                rank=rank,
                row=i,
            ))
        return hits

    def similar(self, row: int, k: int = 5) -> list[Hit]:
        """Passages most semantically similar to the given one (excluding itself).
        Pure vector math on the cached embeddings — instant, offline, no AI."""
        q = self.embeddings[row]
        scores = self.embeddings @ q
        scores[row] = -1.0                         # exclude the passage itself
        k = min(k, len(scores) - 1)
        idx = np.argpartition(-scores, k - 1)[:k]
        idx = idx[np.argsort(-scores[idx])]
        return [Hit(passage=self.meta[i], dense_score=float(scores[i]), row=int(i))
                for i in idx]


@lru_cache(maxsize=1)
def get_retriever() -> Retriever:
    return Retriever()
