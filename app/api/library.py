"""Saved papers and recent searches for the (single, hardcoded) dev user."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from psycopg import Connection, errors
from psycopg.rows import class_row
from pydantic import BaseModel

from app.api.deps import DEV_USER_ID, get_conn

router = APIRouter(tags=["library"])


class SavedPaper(BaseModel):
    id: int
    arxiv_id: str
    title: str
    published_at: date
    saved_at: datetime


class RecentSearch(BaseModel):
    query: str
    engine: str
    created_at: datetime


@router.get("/library", response_model=list[SavedPaper])
def list_library(conn: Annotated[Connection, Depends(get_conn)]):
    cur = conn.cursor(row_factory=class_row(SavedPaper))
    return cur.execute(
        """
        SELECT p.id, p.arxiv_id, p.title, p.published_at, l.saved_at
        FROM library l JOIN papers p ON p.id = l.paper_id
        WHERE l.user_id = %s
        ORDER BY l.saved_at DESC
        """,
        (DEV_USER_ID,),
    ).fetchall()


@router.put("/library/{paper_id}", status_code=204)
def save_paper(paper_id: int, conn: Annotated[Connection, Depends(get_conn)]):
    """Idempotent: saving an already-saved paper is a no-op."""
    try:
        conn.execute(
            "INSERT INTO library (user_id, paper_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (DEV_USER_ID, paper_id),
        )
    except errors.ForeignKeyViolation:
        raise HTTPException(404, "paper not found") from None
    return Response(status_code=204)


@router.delete("/library/{paper_id}", status_code=204)
def unsave_paper(paper_id: int, conn: Annotated[Connection, Depends(get_conn)]):
    conn.execute(
        "DELETE FROM library WHERE user_id = %s AND paper_id = %s", (DEV_USER_ID, paper_id)
    )
    return Response(status_code=204)


@router.get("/searches", response_model=list[RecentSearch])
def recent_searches(
    conn: Annotated[Connection, Depends(get_conn)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """Each distinct query once, at its most recent run, newest first."""
    cur = conn.cursor(row_factory=class_row(RecentSearch))
    return cur.execute(
        """
        SELECT query, engine, created_at FROM (
            SELECT DISTINCT ON (lower(query)) query, engine, created_at
            FROM searches WHERE user_id = %s
            ORDER BY lower(query), created_at DESC
        ) latest
        ORDER BY created_at DESC LIMIT %s
        """,
        (DEV_USER_ID, limit),
    ).fetchall()
