"""Upload-and-analyze: turn a user's PDF into searchable, embedded chunks so the
assistant can answer from it alongside the site knowledge base.

Session-scoped and in-memory (nothing is persisted) — a clean "chat with your
document" feature. Reuses the same embedding model as the site index, so uploaded
chunks and site chunks live in the same vector space and are directly comparable.
"""
import re
from typing import List, Dict, Tuple

import numpy as np

from . import retrieval

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
MIN_CHUNK = 60


def extract_pages(file) -> List[Tuple[int, str]]:
    """Return [(page_number, text), ...] from a PDF file-like object."""
    from pypdf import PdfReader

    reader = PdfReader(file)
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append((i, text))
    return pages


def chunk_pages(pages: List[Tuple[int, str]], source: str) -> List[Dict]:
    chunks = []
    for page_no, text in pages:
        text = re.sub(r"\s+", " ", text).strip()
        start = 0
        while start < len(text):
            piece = text[start:start + CHUNK_SIZE].strip()
            if len(piece) >= MIN_CHUNK:
                chunks.append({"text": piece, "source": source, "page": page_no})
            start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def embed_chunks(chunks: List[Dict]) -> Tuple[List[Dict], np.ndarray]:
    """Embed chunk texts (L2-normalized, same model as the site index)."""
    if not chunks:
        return chunks, np.empty((0, 0), dtype=np.float32)
    vectors = np.array([retrieval._embed(c["text"]) for c in chunks], dtype=np.float32)
    return chunks, vectors


def process(file, source: str) -> Tuple[List[Dict], np.ndarray]:
    """Full pipeline for one uploaded PDF: extract -> chunk -> embed."""
    return embed_chunks(chunk_pages(extract_pages(file), source))


def search(query_vec: np.ndarray, chunks: List[Dict], vectors: np.ndarray,
           top_k: int = 3) -> List[Dict]:
    """Top-k uploaded chunks for a query (cosine over normalized vectors)."""
    if not chunks or vectors.size == 0:
        return []
    scores = vectors @ query_vec
    order = np.argsort(scores)[::-1][:top_k]
    out = []
    for i in order:
        item = dict(chunks[int(i)])
        item["score"] = float(scores[int(i)])
        out.append(item)
    return out


def format_context(hits: List[Dict]) -> str:
    """Render uploaded-doc hits into a context block for the LLM."""
    blocks = []
    for h in hits:
        blocks.append(f"[Uploaded document: {h['source']}, page {h['page']}]\n{h['text']}")
    return "\n\n".join(blocks)
