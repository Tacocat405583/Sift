from app.search.tokenizer import tokenize


def test_drops_inline_and_display_math():
    assert tokenize(r"error bound $\varepsilon = 0.99$ in $$\mathbb{R}^d$$ space") == [
        "error",
        "bound",
        "space",
    ]


def test_unwraps_formatting_commands_and_drops_citations():
    assert tokenize(r"\emph{novel} \hlb{method} \cite{smith2020}") == ["novel", "method"]


def test_drops_urls():
    assert tokenize("code at https://github.com/x/y and www.example.com") == ["code"]


def test_splits_hyphens_and_drops_pure_numbers():
    assert tokenize("Retrieval-augmented GPT-4 in 2026") == ["retriev", "augment", "gpt"]


def test_removes_stopwords_and_stems():
    assert tokenize("We are running the agents") == ["run", "agent"]


def test_query_and_document_agree():
    assert tokenize("agent") == tokenize("Agents")
