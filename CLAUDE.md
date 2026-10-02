# SIFT

arXiv paper search engine: hand-rolled TF-IDF ranking (vs Postgres full-text as a comparison
engine) over CS papers in cs.AI/LG/CL/MA/IR, plus a force-directed graph of results.
Full spec: [MD/goal.md](MD/goal.md). Not an LLM/agent project — that is explicitly out of scope.

## How we work
- **Goal:** deployed, resume-ready v1 in ~1 week (started 2026-10-01). Nick is in school.
- **Claude writes the code, Nick reviews.** Nick owns design: at each **design checkpoint**, present
  2–3 options + a recommendation, let him pick, *then* implement. Never decide those silently.
- Short updates, not essays. "Where are we now" = give status from the progress log below.
- Commit only when Nick says so. **No `Co-Authored-By` / "Generated with" lines** in this repo.
- Secrets live in `.env` (gitignored), never pasted into chat. Template: [.env.example](.env.example).

## Stack & commands
- Local Postgres is on **localhost:5433** (5432 is taken by a native Windows Postgres 17 service).
- Python 3.13, `uv`, FastAPI, psycopg3 (raw SQL, no ORM), numpy/scipy. Postgres 16 via
  [docker-compose.yml](docker-compose.yml). Frontend (later): Vite + React + TS + react-force-graph-2d.
- Hosting (Session 5): Render free web service (Docker) + Neon free Postgres. Only the Neon
  connection string is needed — not Neon Auth, not the Neon CLI/MCP.

```
docker compose up -d                                    # local Postgres (Docker Desktop must be running)
docker exec -i sift-db psql -U sift -d sift < database/schema.sql   # apply schema (idempotent)
uv run python -m app.crawler.harvest                    # OAI-PMH -> data/cs/*.xml (resumable)
uv run python -m app.crawler.load                       # data/cs/*.xml -> papers (idempotent upsert)
uv run python -m app.search.indexer                     # build terms + postings (~45s)
uv run uvicorn app.main:app --reload                    # API on :8000, docs at /docs
uv run pytest -q
uv run ruff check app tests && uv run ruff format app tests
```
Run modules with `-m` from the repo root (imports are `app.*`).

## Layout
- [app/config.py](app/config.py) — pydantic-settings. `HARVEST_MONTHS` (1 = MVP, 3 = full corpus) is
  the single knob for corpus size. Target categories, result limit (125), neighbors K (20).
- [app/db.py](app/db.py) — `ConnectionPool` (opened explicitly: `with pool, pool.connection() as conn`).
- [app/crawler/](app/crawler/) — `response.py` (fetch w/ retry on 406/503), `parser.py`
  (`parse_page(xml) -> (papers, token)`, filters categories, skips deleted records),
  `harvest.py`, `load.py`.
- [app/search/](app/search/) — `tokenizer.py` (Checkpoint B rules), `indexer.py` (build/refresh index), `tfidf.py` and `pgfts.py` (`search(conn, q, limit) -> [(paper_id, score)]`).
- [database/schema.sql](database/schema.sql) — full schema incl. index, graph and user tables.
- [reference/](reference/) — Nick's earlier reference code; keep it, don't delete.

## Design decisions made
- **Checkpoint A (schema):** `papers.id serial` + unique `arxiv_id` (int ids keep postings/neighbors
  small). Categories and authors in **join tables** (`paper_categories`, `authors`+`paper_authors`
  with `position`). pgfts uses a **generated stored tsvector** (title weight A, abstract B) + GIN.
  All non-target categories are also stored in `categories` (e.g. cs.SE cross-lists).
- Keep papers whose *modified* date is in window even if created years ago; store both
  `published_at` (`<created>`) and `updated_at` (`<datestamp>`). No date filtering in the parser.
- **Checkpoint C (scoring): lnc.ltc cosine.** Doc `w = (1+ln tf)/doc_norm`,
  `doc_norm = sqrt(Σ(1+ln tf)²)` (no IDF → IDF refresh only touches `terms`). Query
  `w = (1+ln tf_q)·idf`, `idf = ln(N/df)`. Query vector not normalized (rank-invariant).
  **Title terms counted twice** (parity with pgfts weight A).
- **Checkpoint B (tokenizer):** drop `$...$`/`$$...$$` math entirely (~16% of abstracts have it)
  and URLs (~11%); unwrap `\cmd{word}` → word, drop `\cite{}`/`\ref{}`/`\url{}`; split on
  non-alphanumerics (hyphens split); drop pure numbers; NLTK English stopwords (embedded, no
  nltk.download); Porter stemming (parity with Postgres `english` config). Same fn for queries.
- **Checkpoint D (API):** `GET /search?q=&engine=tfidf|pgfts&limit=` returns
  `{query, engine, took_ms, papers[], edges[]}` in **one response**; papers include abstracts,
  authors (ordered), categories, score, citation_count. `took_ms` times ranking only.
  **pgfts matches ANY word** (plainto_tsquery with `&`→`|`) so it shares tfidf's candidate set.
- Single hardcoded user (`users.id = 1`, seeded); every user table carries `user_id`.

## Progress log
Plan: `~/.claude/plans/im-in-school-and-eager-fox.md` (5 sessions).

**Session 1 — Foundations + ingest** ✅ done 2026-10-02
- [x] Cleanup: removed mlflow/mlflowtest, `arxiv` dep, app/output, stale root files; added psycopg/numpy/scipy
- [x] config.py, db.py, .env.example
- [x] Checkpoint A + schema.sql
- [x] parser.py + tests/test_parser.py (2 passing)
- [x] harvest.py, load.py (written, lint-clean)
- [x] Fixed the 406s: they weren't transient. arXiv's Fastly CDN kept 406-ing `urllib` on URLs
      that curl and `requests` got 200 on (same headers). `fetch()` now uses a `requests.Session`.
- [x] Harvested 2026-09-01 → 2026-10-01: 26 pages (103 MB) in data/cs/, **18,779 target-category
      records** — ~2x the 9k estimate because the window is by *modified* date, so revised older
      papers come along (decision: keep them). Expect fewer rows after upsert if any repeat.
- [x] Schema applied, load run (2m45s): **19,476 papers** (15,901 created in Sept, 3,575 revised
      older ones), 65k authors, 142 categories. Per target category: cs.AI 9,953 · cs.LG 9,630 ·
      cs.CL 5,275 · cs.IR 856 · cs.MA 650. No empty titles/abstracts. pgfts query sanity-checked.
- [x] Docker Postgres moved to host port **5433**: a native Windows `postgresql-x64-17` service
      owns 5432 and was answering our connections (password auth failed).

**Session 2 — Index + engines + search API** (in progress)
- [x] Checkpoint B + tokenizer.py + tests/test_tokenizer.py (8 tests passing total)
- [x] Checkpoint C + indexer.py: 19,476 papers → 37,695 terms, 1.91M postings, 145 MB, 42s
      (`uv run python -m app.search.indexer`, `--idf` for IDF-only refresh)
- [x] tfidf.py + pgfts.py: both 2–20 ms for 125 results. Observed: pgfts ANDs query words (44
      results for "LLM hallucination detection" vs 125 for tfidf); tfidf's #1 there looks off —
      likely lnc.ltc's short-doc bias. Revisit once the UI makes side-by-side comparison easy.
- [x] tests/test_scoring.py (title boost, lnc doc_norm) — 11 tests passing total
- [x] Checkpoint D + API: `app/main.py` (lifespan opens pool), `app/api/deps.py` (`get_conn`,
      `DEV_USER_ID`), `app/api/search.py`. Verified: both engines 125 papers, 422 on bad
      engine/empty q, stopword-only query → empty list, searches logged. Edges = 0 until Session 3.
      pgfts in OR mode is slower (~340 ms vs ~20 ms for tfidf) — fine for now, note for comparison.

**Session 2** ✅ done 2026-10-02, committed.

**Session 3** — neighbors (scipy sparse, chunked, top-20), edges in search response,
Semantic Scholar citations (BackgroundTasks + `GET /papers/citations?ids=`), library/searches endpoints.
**Session 4** — React frontend (graph + paginated list + engine toggle + similarity slider).
**Session 5** — Dockerfile, render.yaml, Neon (`pg_dump | psql` from local), CI, recruiter README.
