-- SIFT schema. Idempotent: safe to run against an empty or existing database.

-- ---------- Corpus ----------

CREATE TABLE IF NOT EXISTS papers (
    id                  serial PRIMARY KEY,
    arxiv_id            text NOT NULL UNIQUE,
    title               text NOT NULL,
    abstract            text NOT NULL,
    published_at        date NOT NULL,          -- <created> of v1
    updated_at          date NOT NULL,          -- OAI <datestamp> (last modified)
    citation_count      integer,                -- NULL = not fetched yet
    citation_fetched_at timestamptz,
    -- Postgres full-text engine (?engine=pgfts). Title weighted above abstract.
    search_vector       tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', title), 'A') ||
        setweight(to_tsvector('english', abstract), 'B')
    ) STORED
);
CREATE INDEX IF NOT EXISTS papers_search_vector_idx ON papers USING gin (search_vector);
CREATE INDEX IF NOT EXISTS papers_published_at_idx ON papers (published_at);

CREATE TABLE IF NOT EXISTS categories (
    code  text PRIMARY KEY,                     -- 'cs.AI'
    name  text
);

CREATE TABLE IF NOT EXISTS paper_categories (
    paper_id  integer NOT NULL REFERENCES papers (id) ON DELETE CASCADE,
    category  text    NOT NULL REFERENCES categories (code),
    PRIMARY KEY (paper_id, category)
);
CREATE INDEX IF NOT EXISTS paper_categories_category_idx ON paper_categories (category);

CREATE TABLE IF NOT EXISTS authors (
    id    serial PRIMARY KEY,
    name  text NOT NULL UNIQUE                  -- "First Last"; no disambiguation in v1
);

CREATE TABLE IF NOT EXISTS paper_authors (
    paper_id   integer  NOT NULL REFERENCES papers (id) ON DELETE CASCADE,
    author_id  integer  NOT NULL REFERENCES authors (id),
    position   smallint NOT NULL,               -- author order on the paper
    PRIMARY KEY (paper_id, author_id)
);
CREATE INDEX IF NOT EXISTS paper_authors_author_idx ON paper_authors (author_id);

-- ---------- Hand-rolled TF-IDF index ----------

CREATE TABLE IF NOT EXISTS terms (
    id                  serial PRIMARY KEY,
    term                text    NOT NULL UNIQUE,
    document_frequency  integer NOT NULL,
    idf                 real    NOT NULL
);

CREATE TABLE IF NOT EXISTS postings (
    term_id         integer NOT NULL REFERENCES terms (id) ON DELETE CASCADE,
    paper_id        integer NOT NULL REFERENCES papers (id) ON DELETE CASCADE,
    term_frequency  integer NOT NULL,
    doc_norm        real    NOT NULL,           -- exact formula decided at Checkpoint C
    PRIMARY KEY (term_id, paper_id)             -- query path: term -> papers
);

-- ---------- Graph ----------

CREATE TABLE IF NOT EXISTS neighbors (
    paper_id     integer NOT NULL REFERENCES papers (id) ON DELETE CASCADE,
    neighbor_id  integer NOT NULL REFERENCES papers (id) ON DELETE CASCADE,
    similarity   real    NOT NULL,
    PRIMARY KEY (paper_id, neighbor_id)
);

-- ---------- Users (single hardcoded user in v1) ----------

CREATE TABLE IF NOT EXISTS users (
    id      serial PRIMARY KEY,
    topics  text[] NOT NULL DEFAULT '{}'        -- user-picked filters, separate from index scope
);

CREATE TABLE IF NOT EXISTS library (
    user_id   integer     NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    paper_id  integer     NOT NULL REFERENCES papers (id) ON DELETE CASCADE,
    saved_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, paper_id)
);

CREATE TABLE IF NOT EXISTS searches (
    id          serial PRIMARY KEY,
    user_id     integer     NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    query       text        NOT NULL,
    engine      text        NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS searches_user_created_idx ON searches (user_id, created_at DESC);

-- ---------- Seed ----------

INSERT INTO categories (code, name) VALUES
    ('cs.AI', 'Artificial Intelligence'),
    ('cs.LG', 'Machine Learning'),
    ('cs.CL', 'Computation and Language'),
    ('cs.MA', 'Multiagent Systems'),
    ('cs.IR', 'Information Retrieval')
ON CONFLICT DO NOTHING;

INSERT INTO users (id, topics) VALUES (1, '{cs.AI,cs.LG,cs.CL,cs.MA,cs.IR}')
ON CONFLICT DO NOTHING;
SELECT setval(pg_get_serial_sequence('users', 'id'), (SELECT max(id) FROM users));
