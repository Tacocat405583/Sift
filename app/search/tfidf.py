"""Hand-rolled TF-IDF engine (lnc.ltc, see indexer.py for the weights).

Only the query's terms are touched: their `terms` rows give idf, their postings give
(1 + ln tf) / doc_norm, and the dot product is summed per paper in SQL. The query
vector is not length-normalized: it scales every score equally, so ranking is unchanged.
"""

from collections import Counter

from psycopg import Connection

from app.search.tokenizer import tokenize

SEARCH = """
SELECT p.paper_id,
       sum((1 + ln(q.tf)) * t.idf * (1 + ln(p.term_frequency)) / p.doc_norm) AS score
FROM unnest(%(terms)s::text[], %(tfs)s::int[]) AS q (term, tf)
JOIN terms t ON t.term = q.term
JOIN postings p ON p.term_id = t.id
GROUP BY p.paper_id
ORDER BY score DESC
LIMIT %(limit)s
"""


def search(conn: Connection, query: str, limit: int) -> list[tuple[int, float]]:
    """Return [(paper_id, score)] best first. Empty if no query term is in the vocabulary."""
    tf = Counter(tokenize(query))
    if not tf:
        return []
    return conn.execute(
        SEARCH, {"terms": list(tf), "tfs": list(tf.values()), "limit": limit}
    ).fetchall()
