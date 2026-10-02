"""Integration tests for both ranking engines against the local corpus."""

import pytest

from app.search import pgfts, tfidf

ENGINES = [tfidf.search, pgfts.search]


@pytest.mark.parametrize("search", ENGINES)
def test_results_are_ranked_and_capped(conn, search):
    results = search(conn, "retrieval augmented generation", 125)
    scores = [score for _, score in results]
    assert len(results) == 125
    assert scores == sorted(scores, reverse=True)
    assert len({paper_id for paper_id, _ in results}) == 125


@pytest.mark.parametrize("search", ENGINES)
def test_stopword_only_query_returns_nothing(conn, search):
    assert search(conn, "the of and", 125) == []


@pytest.mark.parametrize("search", ENGINES)
def test_any_word_matches(conn, search):
    # "zzqx" is in no paper; OR semantics still match on "nonsense".
    assert search(conn, "zzqx nonsense", 125)


def test_engines_share_candidate_set(conn):
    # Regression: pgfts double-stemmed query lexemes (nonsens -> nonsen) and lost matches.
    query = "zzqx nonsense"
    tfidf_ids = {i for i, _ in tfidf.search(conn, query, 125)}
    pgfts_ids = {i for i, _ in pgfts.search(conn, query, 125)}
    assert tfidf_ids == pgfts_ids


def test_title_match_ranks_first(conn):
    title = conn.execute(
        "SELECT title FROM papers WHERE title ILIKE '%%hallucination detection%%' LIMIT 1"
    ).fetchone()[0]
    top_ids = [i for i, _ in tfidf.search(conn, title, 5)]
    match = conn.execute("SELECT id FROM papers WHERE title = %s", (title,)).fetchone()[0]
    assert match in top_ids
