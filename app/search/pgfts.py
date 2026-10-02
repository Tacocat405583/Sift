"""Postgres full-text engine: the comparison baseline for the hand-rolled TF-IDF.

Uses the generated, GIN-indexed `papers.search_vector` (title weight A, abstract B).
Matches ANY query word (OR), like the TF-IDF engine, so the comparison is about ranking
alone (Checkpoint D). plainto_tsquery gives 'a' & 'b'; we swap & for |.
"""

from psycopg import Connection

SEARCH = """
SELECT id, ts_rank_cd(search_vector, q) AS score
FROM papers,
     to_tsquery('english', replace(plainto_tsquery('english', %(query)s)::text, '&', '|')) AS q
WHERE search_vector @@ q
ORDER BY score DESC
LIMIT %(limit)s
"""


def search(conn: Connection, query: str, limit: int) -> list[tuple[int, float]]:
    """Return [(paper_id, score)] best first."""
    return conn.execute(SEARCH, {"query": query, "limit": limit}).fetchall()
