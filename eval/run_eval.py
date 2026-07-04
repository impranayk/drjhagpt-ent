"""Retrieval evaluation harness.

Runs a golden question set through each retrieval mode (dense / hybrid /
hybrid_rerank) and reports hit-rate@k and Mean Reciprocal Rank (MRR), so the
lift from hybrid search and reranking is measurable rather than assumed.

Run from the repo root:  python eval/run_eval.py
No Groq API key required — this measures retrieval only.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from chatbot import retrieval  # noqa: E402

MODES = ["dense", "hybrid", "hybrid_rerank"]
K = 5


def first_hit_rank(results, expects):
    """1-based rank of the first result whose URL matches any expected substring."""
    for rank, r in enumerate(results, start=1):
        url = (r.get("url") or "").lower()
        if any(e.lower() in url for e in expects):
            return rank
    return 0


def main():
    golden = json.loads((Path(__file__).parent / "golden.json").read_text(encoding="utf-8"))
    print(f"Golden questions: {len(golden)} | top_k = {K}\n")

    results_by_mode = {}
    for mode in MODES:
        hits, rr = 0, 0.0
        details = []
        for item in golden:
            res = retrieval.retrieve(item["question"], mode=mode, top_k=K)
            rank = first_hit_rank(res, item["expect"])
            if rank:
                hits += 1
                rr += 1.0 / rank
            details.append(rank)
        n = len(golden)
        results_by_mode[mode] = (hits / n, rr / n, details)

    print(f"{'mode':16}{'hit@' + str(K):>10}{'MRR':>10}")
    print("-" * 36)
    for mode in MODES:
        hit_rate, mrr, _ = results_by_mode[mode]
        print(f"{mode:16}{hit_rate * 100:9.1f}%{mrr:10.3f}")

    print("\nPer-question first-hit rank (0 = miss):")
    print(f"{'#':>2}  " + "  ".join(f"{m[:12]:>12}" for m in MODES))
    for i in range(len(golden)):
        row = "  ".join(f"{results_by_mode[m][2][i]:>12}" for m in MODES)
        print(f"{i + 1:>2}  {row}")


if __name__ == "__main__":
    main()
