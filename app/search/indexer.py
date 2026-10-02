"""Build the inverted index (terms + postings) for the hand-rolled TF-IDF engine.

Scoring is lnc.ltc (Checkpoint C):
    document side  w_d = (1 + ln tf) / doc_norm,   doc_norm = sqrt(sum (1 + ln tf)^2)
    query side     w_q = (1 + ln tf_q) * idf,       idf = ln(N / df)
doc_norm has no IDF in it, so an IDF refresh only rewrites `terms` (O(vocab)), never postings.
Title terms are counted twice (field boost, parity with pgfts title weight A).

    uv run python -m app.search.indexer            # full rebuild
    uv run python -m app.search.indexer --idf      # refresh IDF only
"""

import math
import sys
import time
from collections import Counter

from psycopg import Connection

from app.db import pool
from app.search.tokenizer import tokenize

TITLE_BOOST = 2


def document_terms(title: str, abstract: str) -> Counter[str]:
    return Counter(tokenize(title) * TITLE_BOOST + tokenize(abstract))


def doc_norm(tf: Counter[str]) -> float:
    return math.sqrt(sum((1 + math.log(count)) ** 2 for count in tf.values()))


def build(conn: Connection) -> None:
    started = time.perf_counter()
    rows = conn.execute("SELECT id, title, abstract FROM papers").fetchall()
    n_docs = len(rows)

    docs: list[tuple[int, Counter[str], float]] = []
    df: Counter[str] = Counter()
    for paper_id, title, abstract in rows:
        tf = document_terms(title, abstract)
        docs.append((paper_id, tf, doc_norm(tf)))
        df.update(tf.keys())

    term_ids = {term: i for i, term in enumerate(sorted(df), start=1)}

    with conn.transaction():
        conn.execute("TRUNCATE terms, postings RESTART IDENTITY")
        with conn.cursor().copy(
            "COPY terms (id, term, document_frequency, idf) FROM STDIN"
        ) as copy:
            for term, term_id in term_ids.items():
                copy.write_row((term_id, term, df[term], math.log(n_docs / df[term])))
        with conn.cursor().copy(
            "COPY postings (term_id, paper_id, term_frequency, doc_norm) FROM STDIN"
        ) as copy:
            n_postings = 0
            for paper_id, tf, norm in docs:
                for term, count in tf.items():
                    copy.write_row((term_ids[term], paper_id, count, norm))
                    n_postings += 1
        conn.execute("SELECT setval(pg_get_serial_sequence('terms', 'id'), %s)", (len(term_ids),))

    print(
        f"indexed {n_docs} papers: {len(term_ids)} terms, {n_postings} postings "
        f"in {time.perf_counter() - started:.1f}s"
    )


def refresh_idf(conn: Connection) -> None:
    """Recompute df/idf from postings. Touches only `terms`."""
    with conn.transaction():
        conn.execute("""
            WITH n AS (SELECT count(*)::float AS docs FROM papers),
                 df AS (SELECT term_id, count(*) AS df FROM postings GROUP BY term_id)
            UPDATE terms t
            SET document_frequency = df.df, idf = ln(n.docs / df.df)
            FROM df, n
            WHERE t.id = df.term_id
        """)
    print("idf refreshed")


if __name__ == "__main__":
    with pool, pool.connection() as conn:
        refresh_idf(conn) if "--idf" in sys.argv else build(conn)
