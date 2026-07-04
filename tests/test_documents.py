from chatbot import documents, retrieval


def test_chunk_embed_search_roundtrip():
    pages = [(1, "VMware HCX enables secure workload migration to the cloud. " * 40)]
    chunks = documents.chunk_pages(pages, "test.pdf")
    assert len(chunks) >= 1
    assert all(c["source"] == "test.pdf" and c["page"] == 1 for c in chunks)

    ch, vecs = documents.embed_chunks(chunks)
    assert vecs.shape[0] == len(ch)

    qv = retrieval._embed("How does HCX migrate workloads to the cloud?")
    hits = documents.search(qv, ch, vecs, top_k=2)
    assert len(hits) >= 1
    assert hits[0]["source"] == "test.pdf"
    assert "score" in hits[0]
