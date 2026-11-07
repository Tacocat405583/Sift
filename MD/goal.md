sift

Search, rank, and explore arXiv papers by relevance — with a graph view of how they connect.

What it is

You type a query like "AI automation." sift returns a ranked list of arXiv papers, plus a force-directed graph of those results showing how they relate to each other. Heavily cited papers appear as large central nodes; similar papers are linked.

Ranking is TF-IDF, hand-rolled. Not an AI agent, not LLM-powered. An agent layer could be added later but is explicitly out of scope.

Scope
Corpus (v1)

Computer Science only. Five subcategories:

Category	Field
cs.AI	Artificial Intelligence
cs.LG	Machine Learning
cs.CL	Computation and Language
cs.MA	Multiagent Systems
cs.IR	Information Retrieval
Date window: last 3 months
Expected size: ~27,000 papers (measured against the live API, deduped for cross-listing)

Rationale: the date window is the size lever, not the category count. Measured volumes over 12 months are cs.AI 57k, cs.LG 53k, cs.CL 26k, cs.IR 4.9k, cs.MA 3.5k — 105k deduped, far too large for v1. Cross-list dedupe does not meaningfully reduce this. At 3 months the corpus is dense enough for a good graph, computable locally, and the neighbors job stays tractable (~366M pair comparisons rather than ~5.5B).

User topics ≠ index scope

Two separate concepts, separate schema fields:

Index scope — what's in the database. Decided by us, fixed above.
User topics — 5 subcategories a user picks at onboarding. Filters/personalizes results within the index.

They start as the same list. They should not be the same column.

Data model
Sources
arXiv — metadata (title, abstract, authors, categories, dates, arXiv ID). No citation data available here.
Semantic Scholar API — citation counts and reference lists. Direct arXiv:XXXX.XXXXX lookup, batch endpoint accepts up to 500 IDs per call. Get an API key — the unauthenticated tier is roughly 1 req/sec on a shared pool.
Ingest: OAI-PMH, not the query API

The arXiv query API caps at 2000 results/request, wants a 3s courtesy delay, and degrades on deep start offsets. For a 27k-paper bulk pull use OAI-PMH, which is the sanctioned bulk access path. The query API is fine for incremental daily top-ups.

Citation hydration: lazy and async

Do not fetch citations at index time. When a query returns its result set, batch-fetch citation counts for those papers, write to citation_count, cache indefinitely (refresh monthly at most).

Async, not blocking. The search endpoint returns immediately. Citation fetching happens in the background; the client polls a second endpoint (GET /papers/citations?ids=...) once and resizes nodes when the data lands. Cold queries render with uniform node sizes for a beat rather than stalling 1–2s.

Effect: popular papers hydrate naturally through use; the long tail never costs an API call.

Tables (sketch)
papers — arxiv_id, title, abstract, authors, categories, published_at, citation_count, citation_fetched_at
terms — term, document_frequency, idf
postings — term, paper_id, term_frequency, doc_norm
neighbors — paper_id, neighbor_id, similarity (top-K, precomputed)
users — id, topics
library — user_id, paper_id, saved_at
searches — user_id, query, created_at

Every user-scoped table carries user_id from day one, even though v1 hardcodes a single dev user. Auth then becomes "populate this column properly" rather than a migration across every table.

Ranking
The key distinction

TF-IDF scores are query-dependent. A paper has no single fixed score — it has a score relative to a query.

At index time (precomputed once):

Strip LaTeX, then tokenize title + abstract
Term frequency per document → postings.term_frequency
Document length normalization → postings.doc_norm
IDF across the corpus → terms.idf

At query time:

Look up postings only for the query's terms
Multiply TF × IDF at query time, dot product, sort
Why IDF lives in terms, not baked into postings

If IDF were folded into each posting's weight, every nightly IDF refresh would require rewriting all ~3M posting rows. Keeping IDF in the terms table means a refresh is O(vocab) instead of O(postings), and a query touches only the handful of term rows it needs. The cost is one multiply per posting at query time, which is nothing.

Tokenization

arXiv abstracts are full of LaTeX — $O(n\log n)$, \cite{}, \emph{}. A naive [a-zA-Z0-9]+ regex produces junk tokens (O, n, log, cite, emph) that pollute the vocabulary and distort IDF. Strip LaTeX before tokenizing.

Reindexing

New papers get indexed on arrival. Old papers are never re-scored — only IDF needs touching up as the corpus grows, and that batches nightly.

Two ranking engines, one codebase
Hand-rolled TF-IDF — the point of the project
Postgres full-text search — tsvector + GIN index + ts_rank

Selected by query parameter: ?engine=tfidf|pgfts. Not separate git branches — the whole value is comparing them side by side on the same corpus, which requires both running at once.

Graph
Result set cap

A query retrieves the top 125 papers by score. The graph draws all 125. The list paginates through them (15 on page 1, +25 per "load more"). Without a cap a broad query matching thousands of papers cannot render.

Edges: precomputed top-K neighbors

Cosine similarity between paper TF-IDF vectors. All-pairs on 27k papers is ~366M comparisons — too slow live, fine as an offline batch job.

Each paper stores its top 20 nearest neighbors. Rendering a query's graph is then: keep edges where both endpoints are in the result set. No live similarity math.

Two behaviors from one job:

Query-independent "related work" web (a paper's neighbors are always its neighbors)
Query-dependent clustering (filter those edges to the current results)

Similarity threshold is a UI slider — loosen or tighten the web.

Node sizing

By citation_count, populated asynchronously as described above.

Stability under pagination

The list paginates. The graph does not. It renders all 125 nodes from the start and stays fixed while the list pages beneath it.

Views
1. Query graph — v1

Force-directed cluster of the result set. Nodes = papers, sized by citations. Edges = top-K similarity, filtered to the result set.

2. Citation / inheritance tree — v1.5

Click a paper → expand its citation lineage one hop at a time, fetched on demand from Semantic Scholar, depth-limited so it doesn't explode. Interactive rather than precomputed.

3. Author view — later

Authors as nodes, sized by total citations or paper count. Fields/subfields overlaid. Deliberately vague for now.

Stack
Backend — FastAPI (Python; numpy/scipy available for the TF-IDF math)
Database — Postgres
Frontend — React + react-force-graph (d3-force wrapper; zoom, drag, collision handled out of the box)
Division of work

Frontend is handled for Nick. Backend is the learning target — REST method design, schema design, the inverted index, TF-IDF implementation, and comparing ranking engines. Backend work gets walked through step by step, including the schema, and Nick writes it. Not handed over finished.

v1 done criteria
 ~27k CS papers ingested via OAI-PMH from the 5 subcategories, last 3 months
 LaTeX-stripped tokenizer
 Inverted index built (TF + norm in postings, IDF in terms)
 TF-IDF query returns sensible ranked results, top 125
 ?engine= toggle with Postgres FTS as the comparison
 Top-K neighbors precomputed
 Query graph renders, stable under pagination
 Citation counts hydrate async and resize nodes
 Library + recent searches persist (single hardcoded user)
Explicitly not in v1
Authentication
Citation/inheritance tree
Author graph
Summarization
Any LLM or agent layer
Non-CS arXiv categories