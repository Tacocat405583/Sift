import numpy as np
from scipy import sparse

from app.search.neighbors import top_k


def _normalized(rows):
    m = np.array(rows, dtype=np.float32)
    return sparse.csr_matrix(m / np.linalg.norm(m, axis=1, keepdims=True))


def test_top_k_excludes_self_and_orders_by_similarity():
    #            t0   t1   t2
    m = _normalized([[1, 0, 0], [0.9, 0.1, 0], [0, 1, 0], [0, 0, 1]])
    indices, sims = top_k(m, 2)

    assert indices[0].tolist() == [1, 2]  # nearest to row 0 is row 1, then row 2
    assert all(row not in indices[row] for row in range(4))
    assert np.all(np.diff(sims, axis=1) <= 0)  # descending
    assert np.isclose(sims[0, 0], m[0].toarray() @ m[1].toarray().T)


def test_k_is_capped_at_n_minus_one():
    indices, _ = top_k(_normalized([[1, 0], [0, 1]]), 20)
    assert indices.shape == (2, 1)
