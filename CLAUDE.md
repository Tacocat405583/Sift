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
- Python 3.13, `uv`, FastAPI, psycopg3 (raw SQL, no ORM), numpy/scipy. Postgres 16 via
  [docker-compose.yml](docker-compose.yml). Frontend (later): Vite + React + TS + react-force-graph-2d.
- Hosting (Session 5): Render free web service (Docker) + Neon free Postgres. Only the Neon
  connection string is needed — not Neon Auth, not the Neon CLI/MCP.

```
docker compose up -d                                    # local Postgres (Docker Desktop must be running)
docker exec -i sift-db psql -U sift -d sift < database/schema.sql   # apply schema (idempotent)
uv run python -m app.crawler.harvest                    # OAI-PMH -> data/cs/*.xml (resumable)
uv run python -m app.crawler.load                       # data/cs/*.xml -> papers (idempotent upsert)
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
- [app/search/](app/search/) — `tokenizer.py` (naive, to be replaced), `indexer.py`/`tfidf.py` empty.
- [database/schema.sql](database/schema.sql) — full schema incl. index, graph and user tables.
- [reference/](reference/) — Nick's earlier reference code; keep it, don't delete.

## Design decisions made
- **Checkpoint A (schema):** `papers.id serial` + unique `arxiv_id` (int ids keep postings/neighbors
  small). Categories and authors in **join tables** (`paper_categories`, `authors`+`paper_authors`
  with `position`). pgfts uses a **generated stored tsvector** (title weight A, abstract B) + GIN.
  All non-target categories are also stored in `categories` (e.g. cs.SE cross-lists).
- Keep papers whose *modified* date is in window even if created years ago; store both
  `published_at` (`<created>`) and `updated_at` (`<datestamp>`). No date filtering in the parser.
- IDF lives in `terms`, TF + `doc_norm` in `postings` (per goal.md). `doc_norm` formula is
  still open → Checkpoint C.
- Single hardcoded user (`users.id = 1`, seeded); every user table carries `user_id`.

## Progress log
Plan: `~/.claude/plans/im-in-school-and-eager-fox.md` (5 sessions).

**Session 1 — Foundations + ingest** (in progress)
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
- [ ] Docker Desktop was not running → schema not applied, load not run yet.
      Next: `docker compose up -d`, apply schema, run load, sanity-check counts.

**Session 2 — Index + engines + search API** (next)
- Checkpoint B: tokenizer (LaTeX stripping — abstracts contain things like `\hlb{...}`, `$...$`;
  stopwords? stemming?)
- indexer.py (terms/postings via COPY), Checkpoint C: scoring formula, tfidf.py, pgfts.py
- Checkpoint D: API shape for `GET /search?q=&engine=tfidf|pgfts`

**Session 3** — neighbors (scipy sparse, chunked, top-20), edges in search response,
Semantic Scholar citations (BackgroundTasks + `GET /papers/citations?ids=`), library/searches endpoints.
**Session 4** — React frontend (graph + paginated list + engine toggle + similarity slider).
**Session 5** — Dockerfile, render.yaml, Neon (`pg_dump | psql` from local), CI, recruiter README.
