import math

from app.search.indexer import doc_norm, document_terms


def test_title_terms_count_twice():
    tf = document_terms("Graph agents", "agents plan")
    assert tf == {"graph": 2, "agent": 3, "plan": 1}


def test_doc_norm_is_lnc_and_idf_free():
    tf = document_terms("", "agents agents plan")  # agent: 2, plan: 1
    assert doc_norm(tf) == math.sqrt((1 + math.log(2)) ** 2 + 1)


def test_single_term_doc_has_unit_weight():
    tf = document_terms("", "agents")
    assert (1 + math.log(tf["agent"])) / doc_norm(tf) == 1.0
