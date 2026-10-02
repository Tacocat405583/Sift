"""Lazy, async citation hydration from Semantic Scholar (goal.md: "Citation hydration").

After a search responds, a background task fetches citation counts for result papers that
have never been fetched (or were fetched over REFRESH_AFTER ago) and stores them. The client
polls GET /papers/citations once and resizes graph nodes. Popular papers hydrate through use;
the long tail never costs an API call.
"""

import logging
import random
import threading
import time

import requests

from app.config import settings
from app.db import pool

log = logging.getLogger(__name__)

BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"
BATCH_SIZE = 500  # API maximum per call
REFRESH_AFTER = "30 days"

STALE = f"""
SELECT id, arxiv_id FROM papers
WHERE id = ANY(%s)
  AND (citation_fetched_at IS NULL OR citation_fetched_at < now() - interval '{REFRESH_AFTER}')
"""


MAX_ATTEMPTS = 5
BACKOFF_BASE = 1.0  # seconds; waits 1, 2, 4, 8 (+ jitter) between attempts
RETRY_STATUSES = {429, 500, 502, 503, 504}
MIN_INTERVAL = 1.0  # S2 rate limit: 1 request/second across all endpoints

# Concurrent searches each schedule a background task; serialize them so the whole process
# never sends more than one request per MIN_INTERVAL.
_lock = threading.Lock()
_last_request = 0.0


def _post(arxiv_ids: list[str], headers: dict[str, str]) -> requests.Response:
    global _last_request
    with _lock:
        wait = _last_request + MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            return requests.post(
                BATCH_URL,
                params={"fields": "citationCount"},
                json={"ids": [f"ARXIV:{a}" for a in arxiv_ids]},
                headers=headers,
                timeout=30,
            )
        finally:
            _last_request = time.monotonic()


def backoff_delay(attempt: int, retry_after: str | None) -> float:
    """Server's Retry-After if given, else exponential backoff with jitter."""
    if retry_after and retry_after.isdigit():
        return float(retry_after)
    return BACKOFF_BASE * 2**attempt + random.uniform(0, BACKOFF_BASE)


def fetch_counts(arxiv_ids: list[str]) -> list[int | None] | None:
    """Citation counts aligned with arxiv_ids (None = unknown to S2). None if S2 kept refusing."""
    headers = {}
    if settings.semantic_scholar_api_key:
        headers["x-api-key"] = settings.semantic_scholar_api_key

    for attempt in range(MAX_ATTEMPTS):
        response = _post(arxiv_ids, headers)
        if response.status_code not in RETRY_STATUSES:
            response.raise_for_status()
            return [paper["citationCount"] if paper else None for paper in response.json()]
        if attempt < MAX_ATTEMPTS - 1:
            time.sleep(backoff_delay(attempt, response.headers.get("Retry-After")))

    log.warning(
        "Semantic Scholar returned %s %d times; %d papers left unhydrated",
        response.status_code,
        MAX_ATTEMPTS,
        len(arxiv_ids),
    )
    return None


def hydrate(paper_ids: list[int]) -> None:
    """Background task: fetch and store citation counts for any stale papers in paper_ids."""
    try:
        with pool.connection() as conn:
            stale = conn.execute(STALE, (paper_ids,)).fetchall()
            for start in range(0, len(stale), BATCH_SIZE):
                batch = stale[start : start + BATCH_SIZE]
                counts = fetch_counts([arxiv_id for _, arxiv_id in batch])
                if counts is None:
                    return
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.executemany(
                            "UPDATE papers SET citation_count = %s, citation_fetched_at = now() "
                            "WHERE id = %s",
                            # Unknown to S2 -> 0, so it isn't re-requested every search.
                            [
                                (count or 0, pid)
                                for (pid, _), count in zip(batch, counts, strict=True)
                            ],
                        )
    except Exception:  # a background task must never take the server down
        log.exception("citation hydration failed")
