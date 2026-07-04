"""Build the RAG knowledge index from drpranayjha.com (WordPress REST API).

Pulls published posts + pages, strips HTML, splits into overlapping chunks,
embeds them with fastembed, and saves:
  data/knowledge.npz   -> L2-normalized float32 vectors
  data/chunks.json     -> [{title, url, text}, ...] aligned to the vectors

Run from the repo root:  python ingest/build_index.py
Re-run any time your website content changes.
"""
import html
import json
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path

import numpy as np
import requests

# Allow running as a script without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from chatbot import config  # noqa: E402

SITE = "https://drpranayjha.com"
ENDPOINTS = ["posts", "pages"]
CHUNK_SIZE = 900       # characters
CHUNK_OVERLAP = 150
MIN_CHUNK = 80         # skip tiny fragments


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def strip_html(raw: str) -> str:
    parser = _TextExtractor()
    parser.feed(raw)
    text = html.unescape("".join(parser.parts))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_items(endpoint: str):
    items, page = [], 1
    while True:
        url = f"{SITE}/wp-json/wp/v2/{endpoint}"
        params = {"per_page": 100, "page": page, "_fields": "title,link,content"}
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 400:  # past the last page
            break
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        items.extend(batch)
        print(f"  {endpoint}: page {page} -> {len(batch)} items")
        page += 1
        time.sleep(0.3)  # be polite to the server
    return items


def chunk_text(text: str):
    chunks, start = [], 0
    while start < len(text):
        end = start + CHUNK_SIZE
        piece = text[start:end].strip()
        if len(piece) >= MIN_CHUNK:
            chunks.append(piece)
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def build():
    records = []
    for endpoint in ENDPOINTS:
        print(f"Fetching {endpoint} …")
        for item in fetch_items(endpoint):
            title = strip_html(item.get("title", {}).get("rendered", "")) or "Untitled"
            url = item.get("link", SITE)
            body = strip_html(item.get("content", {}).get("rendered", ""))
            for piece in chunk_text(body):
                records.append({"title": title, "url": url, "text": piece})

    if not records:
        print("No content fetched — aborting.")
        return

    print(f"\nTotal chunks: {len(records)}")
    print(f"Embedding with {config.EMBED_MODEL} (first run downloads the model) …")

    from fastembed import TextEmbedding

    embedder = TextEmbedding(model_name=config.EMBED_MODEL)
    texts = [f"{r['title']}. {r['text']}" for r in records]
    vectors = np.array(list(embedder.embed(texts)), dtype=np.float32)

    # L2-normalize so retrieval can use a plain dot product as cosine similarity.
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    vectors = vectors / norms

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(config.EMBEDDINGS_PATH, vectors=vectors)
    with open(config.CHUNKS_PATH, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False)

    print(f"\n[done] Saved {len(records)} chunks")
    print(f"   {config.EMBEDDINGS_PATH}")
    print(f"   {config.CHUNKS_PATH}")


if __name__ == "__main__":
    build()
