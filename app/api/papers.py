"""GET /papers/citations — the client polls this once after a search to resize graph nodes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection
from pydantic import BaseModel

from app.api.deps import get_conn

router = APIRouter(prefix="/papers", tags=["papers"])


class CitationsResponse(BaseModel):
    citations: dict[int, int | None]  # paper id -> count, None = not fetched yet
    pending: int


@router.get("/citations", response_model=CitationsResponse)
def citations(
    ids: Annotated[str, Query(description="Comma-separated paper ids", max_length=2000)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> CitationsResponse:
    try:
        paper_ids = [int(i) for i in ids.split(",") if i.strip()]
    except ValueError:
        raise HTTPException(422, "ids must be comma-separated integers") from None

    rows = conn.execute(
        "SELECT id, citation_count FROM papers WHERE id = ANY(%s)", (paper_ids,)
    ).fetchall()
    counts = dict(rows)
    return CitationsResponse(citations=counts, pending=sum(1 for c in counts.values() if c is None))
