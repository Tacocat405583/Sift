"""Parse every harvested page in data/cs/ and upsert into Postgres.

Idempotent: re-running updates changed papers and rewrites their author and
category links.

    uv run python -m app.crawler.load
"""

from psycopg import Connection

from app.config import settings
from app.crawler.parser import Paper, parse_page
from app.db import pool

UPSERT_PAPER = """
INSERT INTO papers (arxiv_id, title, abstract, published_at, updated_at)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (arxiv_id) DO UPDATE SET
    title = EXCLUDED.title,
    abstract = EXCLUDED.abstract,
    published_at = EXCLUDED.published_at,
    updated_at = EXCLUDED.updated_at
RETURNING id
"""

# DO UPDATE (a no-op) instead of DO NOTHING so RETURNING yields the id for existing names too.
UPSERT_AUTHOR = """
INSERT INTO authors (name) VALUES (%s)
ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
RETURNING id
"""


def load_paper(conn: Connection, paper: Paper) -> None:
    paper_id = conn.execute(
        UPSERT_PAPER,
        (paper.arxiv_id, paper.title, paper.abstract, paper.published_at, paper.updated_at),
    ).fetchone()[0]

    conn.execute("DELETE FROM paper_categories WHERE paper_id = %s", (paper_id,))
    for code in dict.fromkeys(paper.categories):  # dedupe, keep order
        conn.execute("INSERT INTO categories (code) VALUES (%s) ON CONFLICT DO NOTHING", (code,))
        conn.execute(
            "INSERT INTO paper_categories (paper_id, category) VALUES (%s, %s)", (paper_id, code)
        )

    conn.execute("DELETE FROM paper_authors WHERE paper_id = %s", (paper_id,))
    for position, name in enumerate(dict.fromkeys(paper.authors)):
        author_id = conn.execute(UPSERT_AUTHOR, (name,)).fetchone()[0]
        conn.execute(
            "INSERT INTO paper_authors (paper_id, author_id, position) VALUES (%s, %s, %s)",
            (paper_id, author_id, position),
        )


def main() -> None:
    pages = sorted(settings.data_dir.glob("cs_*.xml"))
    total = 0
    with pool, pool.connection() as conn:
        for path in pages:
            papers, _ = parse_page(path.read_bytes())
            with conn.transaction():  # one commit per page
                for paper in papers:
                    load_paper(conn, paper)
            total += len(papers)
            print(f"{path.name}: {len(papers)}")
        count = conn.execute("SELECT count(*) FROM papers").fetchone()[0]
    print(f"loaded {total} records from {len(pages)} pages; papers table has {count} rows")


if __name__ == "__main__":
    main()
