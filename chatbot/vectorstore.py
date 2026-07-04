"""Optional Qdrant vector backend in LOCAL (embedded) mode — a real vector
database with **no server to run**. The default backend stays in-memory NumPy;
set `VECTOR_BACKEND=qdrant` to persist and query vectors via Qdrant under
`data/qdrant/`.

The collection is (re)built automatically from the committed index on first use,
or explicitly with:  python -m chatbot.vectorstore

qdrant-client is an optional dependency (only needed for this backend):
    pip install qdrant-client
"""
import json
from functools import lru_cache

import numpy as np

from . import config

COLLECTION = "chunks"
_PATH = config.DATA_DIR / "qdrant"


@lru_cache(maxsize=1)
def _client():
    from qdrant_client import QdrantClient

    return QdrantClient(path=str(_PATH))


def _load_index():
    with np.load(config.EMBEDDINGS_PATH) as data:
        vectors = data["vectors"].astype(np.float32)
    with open(config.CHUNKS_PATH, "r", encoding="utf-8") as fh:
        chunks = json.load(fh)
    return vectors, chunks


def ensure_built():
    """Build the Qdrant collection from the index if missing or out of sync."""
    from qdrant_client import models

    client = _client()
    vectors, chunks = _load_index()
    dim = int(vectors.shape[1])

    if client.collection_exists(COLLECTION):
        try:
            if client.get_collection(COLLECTION).points_count == len(chunks):
                return  # already up to date
        except Exception:
            pass
        client.delete_collection(COLLECTION)

    client.create_collection(
        COLLECTION,
        vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
    )
    batch = 1000
    for start in range(0, len(chunks), batch):
        end = min(start + batch, len(chunks))
        points = [
            models.PointStruct(id=i, vector=vectors[i].tolist())
            for i in range(start, end)
        ]
        client.upsert(COLLECTION, points=points)


def search(query_vec: np.ndarray, limit: int):
    """Return (indices, scores) for the top-`limit` nearest chunks."""
    ensure_built()
    resp = _client().query_points(COLLECTION, query=query_vec.tolist(), limit=limit)
    idx = [int(p.id) for p in resp.points]
    scores = [float(p.score) for p in resp.points]
    return idx, scores


if __name__ == "__main__":
    ensure_built()
    print(f"Qdrant collection '{COLLECTION}' built at {_PATH}")
