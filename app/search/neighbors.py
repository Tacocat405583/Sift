"""Precompute each paper's top-K most similar papers (the graph's edges). Offline job.

Similarity is cosine between TF-IDF vectors, w = (1 + ln tf) * idf, L2-normalized. (Doc-to-doc
needs IDF on both sides, unlike the lnc document weights used at query time.) Vectors are
built from `postings` + `terms`, so they always match the live index.

All-pairs is N^2 (~380M for 19.5k papers): done as sparse X_chunk @ X.T in row chunks so
only a chunk x N dense block is in memory at once.

    uv run python -m app.search.neighbors
"""

import time

import numpy as np
from psycopg import Connection
from scipy import sparse

from app.config import settings
from app.db import pool

CHUNK = 1000


def load_matrix(conn: Connection) -> tuple[sparse.csr_matrix, np.ndarray]:
    """Return (row-normalized TF-IDF matrix, paper id for each row)."""
    rows = conn.execute("""
        SELECT p.paper_id, p.term_id, (1 + ln(p.term_frequency)) * t.idf
        FROM postings p JOIN terms t ON t.id = p.term_id
    """).fetchall()
    paper, term, weight = (np.array(col) for col in zip(*rows, strict=True))

    paper_ids, row = np.unique(paper, return_inverse=True)
    matrix = sparse.csr_matrix(
        (weight.astype(np.float32), (row, term)), shape=(len(paper_ids), term.max() + 1)
    )
    norms = sparse.linalg.norm(matrix, axis=1)
    norms[norms == 0] = 1
    return sparse.diags(1 / norms).astype(np.float32) @ matrix, paper_ids


def top_k(matrix: sparse.csr_matrix, k: int) -> tuple[np.ndarray, np.ndarray]:
    """For every row: column indices and similarities of its k most similar *other* rows."""
    n = matrix.shape[0]
    k = min(k, n - 1)
    indices = np.empty((n, k), dtype=np.int64)
    sims = np.empty((n, k), dtype=np.float32)

    for start in range(0, n, CHUNK):
        stop = min(start + CHUNK, n)
        block = (matrix[start:stop] @ matrix.T).toarray()
        block[np.arange(stop - start), np.arange(start, stop)] = -1  # exclude self
        part = np.argpartition(-block, k, axis=1)[:, :k]  # unordered top k
        part_sims = np.take_along_axis(block, part, axis=1)
        order = np.argsort(-part_sims, axis=1)
        indices[start:stop] = np.take_along_axis(part, order, axis=1)
        sims[start:stop] = np.take_along_axis(part_sims, order, axis=1)
    return indices, sims


def build(conn: Connection, k: int) -> None:
    started = time.perf_counter()
    matrix, paper_ids = load_matrix(conn)
    print(f"matrix {matrix.shape[0]} x {matrix.shape[1]}, {matrix.nnz} nonzeros")

    indices, sims = top_k(matrix, k)
    with conn.transaction():
        conn.execute("TRUNCATE neighbors")
        with conn.cursor().copy(
            "COPY neighbors (paper_id, neighbor_id, similarity) FROM STDIN"
        ) as copy:
            for row, paper_id in enumerate(paper_ids):
                for col, sim in zip(indices[row], sims[row], strict=True):
                    if sim > 0:
                        copy.write_row((int(paper_id), int(paper_ids[col]), float(sim)))
    print(f"neighbors: top {k} for {len(paper_ids)} papers in {time.perf_counter() - started:.1f}s")


if __name__ == "__main__":
    with pool, pool.connection() as conn:
        build(conn, settings.neighbors_k)
