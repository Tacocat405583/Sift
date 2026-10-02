"""Postgres full-text engine: the comparison baseline for the hand-rolled TF-IDF.

Uses the generated, GIN-indexed `papers.search_vector` (title weight A, abstract B).
Matches ANY query word (OR), like the TF-IDF engine, so the comparison is about ranking
alone (Checkpoint D). plainto_tsquery gives 'a' & 'b'; we swap & for | and cast straight
to tsquery. (Not to_tsquery('english', ...): that stems the already-stemmed lexemes again,
e.g. nonsense -> nonsens -> nonsen, which matches nothing.)
"""

from psycopg import Connection

SEARCH = """
WITH query AS (
    SELECT replace(plainto_tsquery('english', %(query)s)::text, '&', '|')::tsquery AS q
)
SELECT id, ts_rank_cd(search_vector, q) AS score
FROM papers, query
WHERE search_vector @@ q
ORDER BY score DESC
LIMIT %(limit)s
"""


def search(conn: Connection, query: str, limit: int) -> list[tuple[int, float]]:
    """Return [(paper_id, score)] best first."""
    return conn.execute(SEARCH, {"query": query, "limit": limit}).fetchall()
