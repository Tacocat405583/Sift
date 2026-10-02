"""GET /search — ranked papers plus the graph edges between them (Checkpoint D)."""

import time
from datetime import date
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from psycopg import Connection
from psycopg.rows import dict_row
from pydantic import BaseModel

from app.api.deps import DEV_USER_ID, get_conn
from app.config import settings
from app.search import pgfts, tfidf
from app.services import citations

router = APIRouter(tags=["search"])


class Engine(StrEnum):
    tfidf = "tfidf"
    pgfts = "pgfts"


ENGINES = {Engine.tfidf: tfidf.search, Engine.pgfts: pgfts.search}


class PaperOut(BaseModel):
    id: int
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    categories: list[str]
    published_at: date
    citation_count: int | None
    score: float


class Edge(BaseModel):
    source: int
    target: int
    similarity: float


class SearchResponse(BaseModel):
    query: str
    engine: Engine
    took_ms: float
    papers: list[PaperOut]
    edges: list[Edge]


PAPERS = """
SELECT p.id, p.arxiv_id, p.title, p.abstract, p.published_at, p.citation_count,
       coalesce((SELECT array_agg(a.name ORDER BY pa.position)
                 FROM paper_authors pa JOIN authors a ON a.id = pa.author_id
                 WHERE pa.paper_id = p.id), '{}') AS authors,
       coalesce((SELECT array_agg(pc.category ORDER BY pc.category)
                 FROM paper_categories pc WHERE pc.paper_id = p.id), '{}') AS categories
FROM papers p
WHERE p.id = ANY(%s)
"""

# Top-K neighbor lists aren't symmetric (A in B's top 20 doesn't imply B in A's), so the
# same pair can appear twice; it is deduped below.
EDGES = """
SELECT paper_id, neighbor_id, similarity
FROM neighbors
WHERE paper_id = ANY(%(ids)s) AND neighbor_id = ANY(%(ids)s)
"""


@router.get("/search", response_model=SearchResponse)
def search(
    q: Annotated[str, Query(min_length=1, max_length=200)],
    conn: Annotated[Connection, Depends(get_conn)],
    background: BackgroundTasks,
    engine: Engine = Engine.tfidf,
    limit: Annotated[int, Query(ge=1, le=settings.result_limit)] = settings.result_limit,
) -> SearchResponse:
    started = time.perf_counter()
    ranked = ENGINES[engine](conn, q, limit)
    took_ms = (time.perf_counter() - started) * 1000  # ranking only, for the engine comparison

    ids = [paper_id for paper_id, _ in ranked]
    scores = dict(ranked)
    cur = conn.cursor(row_factory=dict_row)
    by_id = {row["id"]: row for row in cur.execute(PAPERS, (ids,))}
    papers = [PaperOut(**by_id[i], score=scores[i]) for i in ids]

    edges: dict[tuple[int, int], Edge] = {}
    for a, b, sim in conn.execute(EDGES, {"ids": ids}):
        edges.setdefault((min(a, b), max(a, b)), Edge(source=a, target=b, similarity=sim))

    conn.execute(
        "INSERT INTO searches (user_id, query, engine) VALUES (%s, %s, %s)",
        (DEV_USER_ID, q, engine.value),
    )
    if any(p.citation_count is None for p in papers):
        background.add_task(citations.hydrate, ids)  # runs after the response is sent
    return SearchResponse(
        query=q, engine=engine, took_ms=round(took_ms, 1), papers=papers, edges=list(edges.values())
    )
