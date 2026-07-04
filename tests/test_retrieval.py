import pytest

from chatbot import retrieval


def test_rrf_fuses_ranks():
    fused = retrieval._rrf([2, 0, 1], [0, 1, 2])
    # index 0 is rank 2 in the first list and rank 0 in the second -> positive score
    assert fused[0] > 0
    assert set(fused) == {0, 1, 2}


@pytest.mark.skipif(not retrieval.has_knowledge(), reason="index not present")
@pytest.mark.parametrize("mode", ["dense", "hybrid"])
def test_modes_return_grounded_results(mode):
    results = retrieval.retrieve("What is VMware HCX?", mode=mode, top_k=5)
    assert 0 < len(results) <= 5
    assert all("url" in r and "text" in r for r in results)
