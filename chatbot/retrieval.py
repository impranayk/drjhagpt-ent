"""Hybrid retrieval with cross-encoder reranking (Phase 1 enterprise prototype).

Builds on the same prebuilt index as the base app (data/knowledge.npz +
data/chunks.json), but upgrades the retrieval stage:

  dense  :  vector cosine similarity only (what the base app does)
  hybrid :  dense + BM25 keyword search, fused with Reciprocal Rank Fusion
  hybrid_rerank : hybrid candidates re-scored by a cross-encoder reranker

The three modes exist so the evaluation harness can quantify the lift from
each stage (see eval/run_eval.py).
"""
import json
import re
from functools import lru_cache
from typing import List, Dict

import numpy as np

from . import config

_TOKEN_RE = re.compile(r"[a-z0-9]+")

CANDIDATES = getattr(config, "RETRIEVE_CANDIDATES", 40)
RRF_K = getattr(config, "RRF_K", 60)
TOP_K = getattr(config, "RAG_TOP_K", 4)
DEFAULT_MODE = getattr(config, "RETRIEVAL_MODE", "hybrid_rerank")


def _tok(text: str) -> List[str]:
    return _TOKEN_RE.findall((text or "").lower())


@lru_cache(maxsize=1)
def _load():
    if not config.EMBEDDINGS_PATH.exists() or not config.CHUNKS_PATH.exists():
        return np.empty((0, 0), dtype=np.float32), []
    with np.load(config.EMBEDDINGS_PATH) as d:
        vectors = d["vectors"].astype(np.float32)
    with open(config.CHUNKS_PATH, "r", encoding="utf-8") as fh:
        chunks = json.load(fh)
    return vectors, chunks


@lru_cache(maxsize=1)
def _bm25():
    from rank_bm25 import BM25Okapi

    _, chunks = _load()
    corpus = [_tok(c.get("title", "") + " " + c.get("text", "")) for c in chunks]
    return BM25Okapi(corpus)


@lru_cache(maxsize=1)
def _embedder():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=config.EMBED_MODEL)


@lru_cache(maxsize=1)
def _reranker():
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(model_name=getattr(config, "RERANK_MODEL",
                                               "Xenova/ms-marco-MiniLM-L-6-v2"))


def _embed(text: str) -> np.ndarray:
    vec = np.array(list(_embedder().embed([text]))[0], dtype=np.float32)
    norm = np.linalg.norm(vec)
    return vec / norm if norm else vec


def has_knowledge() -> bool:
    vectors, chunks = _load()
    return len(chunks) > 0 and vectors.size > 0


def _dense_topk(question: str, limit: int):
    """Top-`limit` chunk indices + scores by dense similarity.

    Uses the configured vector backend: in-memory NumPy (default) or Qdrant
    (local/embedded) when VECTOR_BACKEND=qdrant.
    """
    q = _embed(question)
    if getattr(config, "VECTOR_BACKEND", "numpy") == "qdrant":
        from . import vectorstore

        return vectorstore.search(q, limit)
    vectors, _ = _load()
    scores = vectors @ q                        # index vectors are L2-normalized
    order = np.argsort(scores)[::-1][:limit]
    return [int(i) for i in order], [float(scores[i]) for i in order]


def _bm25_scores(question: str) -> np.ndarray:
    return np.asarray(_bm25().get_scores(_tok(question)), dtype=np.float32)


def _rrf(*rank_lists) -> Dict[int, float]:
    """Reciprocal Rank Fusion over several ranked index lists (best -> worst)."""
    scores: Dict[int, float] = {}
    for ranks in rank_lists:
        for position, idx in enumerate(ranks):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (RRF_K + position + 1)
    return scores


def retrieve(question: str, mode: str = None, top_k: int = None) -> List[Dict]:
    """Return the top-k chunks for a question under the given retrieval mode."""
    vectors, chunks = _load()
    if not chunks:
        return []
    mode = mode or DEFAULT_MODE
    top_k = top_k or TOP_K

    if mode == "dense":
        idx, scores = _dense_topk(question, top_k)
        picked = list(zip(idx, scores))
    else:
        dense_rank, _ = _dense_topk(question, CANDIDATES)
        bm25 = _bm25_scores(question)
        bm25_rank = [int(i) for i in np.argsort(bm25)[::-1][:CANDIDATES]]
        fused = _rrf(dense_rank, bm25_rank)
        cand = sorted(fused, key=fused.get, reverse=True)[:CANDIDATES]

        if mode == "hybrid":
            picked = [(int(i), float(fused[i])) for i in cand[:top_k]]
        else:  # hybrid_rerank
            docs = [chunks[i].get("text", "") for i in cand]
            rr = list(_reranker().rerank(question, docs))
            ranked = sorted(zip(cand, rr), key=lambda t: t[1], reverse=True)[:top_k]
            picked = [(int(i), float(s)) for i, s in ranked]

    results = []
    for i, score in picked:
        item = dict(chunks[i])
        item["score"] = score
        results.append(item)
    return results
