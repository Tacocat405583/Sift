"""API integration tests against the local corpus. Semantic Scholar is never called."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import citations


@pytest.fixture(scope="module")
def client(conn):  # `conn` fixture skips the module when the DB/index isn't available
    last_search = conn.execute("SELECT coalesce(max(id), 0) FROM searches").fetchone()[0]
    with TestClient(app) as test_client:
        yield test_client
    # Don't leave test queries in the dev user's recent searches.
    conn.execute("DELETE FROM searches WHERE id > %s", (last_search,))
    conn.commit()


@pytest.fixture(autouse=True)
def no_citation_fetch(monkeypatch):
    calls = []
    monkeypatch.setattr(citations, "hydrate", lambda ids: calls.append(ids))
    return calls


@pytest.mark.parametrize("engine", ["tfidf", "pgfts"])
def test_search_returns_papers_and_edges_within_results(client, engine):
    body = client.get("/search", params={"q": "graph neural networks", "engine": engine}).json()

    ids = {p["id"] for p in body["papers"]}
    assert body["engine"] == engine
    assert len(body["papers"]) == 125
    assert body["edges"], "neighbors table should give some edges among 125 related papers"
    assert all(e["source"] in ids and e["target"] in ids for e in body["edges"])
    pairs = [frozenset((e["source"], e["target"])) for e in body["edges"]]
    assert len(pairs) == len(set(pairs)), "edges are deduplicated"


def test_search_schedules_citation_hydration(client, conn, no_citation_fetch):
    client.get("/search", params={"q": "speech recognition", "limit": 10})
    pending = conn.execute("SELECT count(*) FROM papers WHERE citation_count IS NULL").fetchone()[0]
    assert no_citation_fetch if pending else not no_citation_fetch


@pytest.mark.parametrize(
    "params", [{"q": ""}, {"q": "x", "engine": "bm25"}, {"q": "x", "limit": 126}]
)
def test_search_rejects_bad_params(client, params):
    assert client.get("/search", params=params).status_code == 422


def test_citations_endpoint(client):
    ids = [
        p["id"] for p in client.get("/search", params={"q": "agents", "limit": 3}).json()["papers"]
    ]
    body = client.get("/papers/citations", params={"ids": ",".join(map(str, ids))}).json()
    assert set(body["citations"]) == {str(i) for i in ids}
    assert client.get("/papers/citations", params={"ids": "1,abc"}).status_code == 422


def test_library_save_list_unsave(client):
    paper_id = client.get("/search", params={"q": "agents", "limit": 1}).json()["papers"][0]["id"]

    assert client.put(f"/library/{paper_id}").status_code == 204
    assert client.put(f"/library/{paper_id}").status_code == 204  # idempotent
    assert paper_id in [p["id"] for p in client.get("/library").json()]

    assert client.delete(f"/library/{paper_id}").status_code == 204
    assert paper_id not in [p["id"] for p in client.get("/library").json()]


def test_library_unknown_paper_is_404(client):
    assert client.put("/library/999999999").status_code == 404


def test_recent_searches_newest_first(client):
    client.get("/search", params={"q": "first query zz"})
    client.get("/search", params={"q": "second query zz", "engine": "pgfts"})
    recent = client.get("/searches", params={"limit": 2}).json()
    assert [s["query"] for s in recent] == ["second query zz", "first query zz"]
    assert recent[0]["engine"] == "pgfts"


def test_fetch_counts_aligns_and_handles_unknown(monkeypatch):
    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return [{"citationCount": 7}, None]

    monkeypatch.setattr(citations.requests, "post", lambda *a, **k: FakeResponse())
    assert citations.fetch_counts(["2609.00001", "0000.00000"]) == [7, None]


def test_fetch_counts_backs_off_then_succeeds(monkeypatch):
    class Resp:
        def __init__(self, status, body=None):
            self.status_code, self._body, self.headers = status, body, {}

        def raise_for_status(self):
            pass

        def json(self):
            return self._body

    replies = iter([Resp(429), Resp(503), Resp(200, [{"citationCount": 3}])])
    sleeps = []
    monkeypatch.setattr(citations.requests, "post", lambda *a, **k: next(replies))
    monkeypatch.setattr(citations.time, "sleep", sleeps.append)
    monkeypatch.setattr(citations, "MIN_INTERVAL", 0)

    assert citations.fetch_counts(["2609.00001"]) == [3]
    assert len(sleeps) == 2 and 1 <= sleeps[0] < 2 <= sleeps[1] < 3  # 1s then 2s, plus jitter


def test_backoff_honors_retry_after():
    assert citations.backoff_delay(3, "7") == 7.0


def test_recent_searches_are_distinct(client):
    for _ in range(3):
        client.get("/search", params={"q": "repeated query zz"})
    queries = [s["query"].lower() for s in client.get("/searches").json()]
    assert queries.count("repeated query zz") == 1
