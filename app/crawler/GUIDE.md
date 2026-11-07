# Assignment 1 — Write the parser

**File you're writing:** `app/crawler/parser.py`
**Test data you already have:** `data/cs/cs_2026-08-20_2026-08-21_p001.xml` (1300 records)
**Time:** an afternoon

---

## The job in one sentence

`response.py` downloads a page of XML from arXiv. Your parser turns that XML
into a list of Python objects we can put in the database.

That's it. Bytes in, papers out.

---

## Before you start: three things we already decided

**1. We keep old papers.**

arXiv's `from`/`until` filter works on *last modified*, not *created*. So when
we ask for "the last 3 months" we also get a 2013 paper that someone fixed a
typo in last week. Look at the first record in the sample file — created 2015,
datestamp 2026.

We're keeping those. You'll store two dates per paper (`published_at` and
`updated_at`) and we'll decide later which one matters. No date filtering in
your parser.

**2. You filter out the non-AI papers yourself.**

We ask arXiv for `set=cs`, which is *all* of computer science. We only want
five subcategories. You drop the rest inside the parser, so nothing downstream
ever sees them.

**3. Output is a pydantic model, not a dict.**

FastAPI already installs pydantic so it's free, and the model ends up being the
blueprint for the `papers` table. Two birds.

---

## What the finished file looks like

Four things at module level:

```python
NS = {...}                  # namespace map (see Task 2)
TARGET_CATEGORIES = {...}   # the five subcategories
class Paper(BaseModel):     # one row
def parse_page(xml: bytes) -> tuple[list[Paper], str | None]:
```

`parse_page` returns **two** things: the papers, and the "resumption token"
(arXiv's way of saying "there's more, here's your bookmark"). You return both
because the token lives in a different part of the XML than the papers, and
you're already walking the tree — may as well grab it on the way past.

---

# Task 1 — Build the Paper model

Seven fields. Here's where each one comes from in the XML:

```
arxiv_id      <id>              ->  "1307.3376"
title         <title>
abstract      <abstract>
authors       <authors>         ->  list of names
categories    <categories>      ->  "cs.AI cs.LG"  becomes  ["cs.AI", "cs.LG"]
published_at  <created>         ->  a date
updated_at    <datestamp>       ->  a date  (this one's in the header, not the metadata)
```

**Watch out:** there are *two* id-ish things in each record.

```xml
<identifier>oai:arXiv.org:1307.3376</identifier>   <- header, has a prefix, ignore it
<id>1307.3376</id>                                 <- metadata, this is what you want
```

**Do the cleanup in the model, not in the loop.** Pydantic gives you
`@field_validator(..., mode="before")`, which runs on the raw value on its way
in. Put the "split this string on spaces" and "collapse this ugly whitespace"
logic there. Then your parse loop just shovels raw strings at the model and
stays readable.

The titles and abstracts in this XML come wrapped with newlines and indentation
baked in, so they do need collapsing.

---

# Task 2 — Namespaces (read this before you debug anything)

This XML has two namespaces. The outer envelope is OAI's, the metadata inside
is arXiv's.

```python
NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "arxiv": "http://arxiv.org/OAI/arXiv/",
}
```

Every single lookup needs a prefix:

```python
root.findall(".//oai:record", NS)
meta.find("arxiv:title", NS)
```

**If you forget the prefix, lxml returns an empty list and does not raise.**
Your code runs, finds nothing, and tells you nothing. If your record count
comes back 0, come back and reread this section first.

---

# Task 3 — Walk the records

Loop over `.//oai:record`. For each one:

**First, check if it's deleted.**

```xml
<header status="deleted">
```

Deleted records have no `<metadata>` element at all. If you go straight for the
metadata you'll get `None`, then `AttributeError`, and it'll happen 900 records
into the page rather than on record 1. Check the header's `status` attribute
and `continue`.

**Then pull the fields.**

You'll write `elem.text.strip()` a lot, and `elem` is `None` whenever the tag
is missing — `.text` on `None` explodes. Write one small helper:

```python
def text_of(parent, path) -> str:
    """Return the text at `path`, or "" if the element isn't there."""
```

Use it everywhere. It replaces about ten `if x is not None:` branches.

**Authors have a catch.** The normal shape is:

```xml
<author><keyname>Kobayashi</keyname><forenames>Naoki</forenames></author>
```

But group authorships use a bare `<name>` with no keyname or forenames. If you
only handle the first shape, those authors quietly vanish. Handle both.

---

# Task 4 — Filter to our five categories

```python
TARGET_CATEGORIES = {"cs.AI", "cs.LG", "cs.CL", "cs.MA", "cs.IR"}
```

Keep a record if **any** of its categories is in that set. Cross-listed papers
count — a `cs.LG cs.CV` paper is ours.

Use the `<categories>` element you already parsed. There's also `<setSpec>` in
the header carrying the same information as `cs:cs:AI` triples — ignore it,
it's a worse version of the same thing.

---

# Task 5 — Grab the resumption token

At the bottom of the file:

```xml
<resumptionToken expirationDate="...">verb%3DListRecords%26...%26skip%3D514</resumptionToken>
```

Find it at `.//oai:resumptionToken` and return its text.

Two ways arXiv says "that was the last page": the element is **missing**, or
it's **there but empty**. Both should come back as `None` from your function.

One note for when you write the crawl loop later: the next request is
`?verb=ListRecords&resumptionToken=<token>` and *nothing else*. If you also
send `set` or `from`, OAI rejects it.

---

# Task 6 — Parse the whole thing

Use `etree.fromstring(xml)`. One page is a few MB — it fits in memory, don't
overthink it. (`iterparse` exists for streaming huge files. We don't have one.)

**Keep it as bytes.** Pass the raw `bytes` from `fetch()` straight through. If
you decode it to a `str` first, `fromstring` chokes on the
`<?xml version="1.0" encoding="UTF-8"?>` line at the top.

---

# Task 7 — Check your work

Add an `if __name__ == "__main__":` block that parses the sample file and
prints:

- how many `<record>` elements you saw
- how many were deleted
- how many survived the category filter
- the resumption token
- one complete `Paper`

**What you should see:**

| number | expected | if it's wrong |
|---|---|---|
| total records | 1300 | |
| token | ends in `skip=514` | |
| in-scope | clearly under 1300 | **= 1300** means your filter isn't running. **= 0** means your namespaces are wrong (Task 2) |

Also eyeball the sample `Paper`: find one where `published_at` and `updated_at`
are years apart. That's the whole reason both columns exist, and seeing it
confirms you mapped them to different elements.

---

# Done when

- [ ] `Paper` model exists, validators handle the splits and the whitespace
- [ ] `parse_page(xml)` returns `(papers, token_or_None)`
- [ ] deleted records are skipped, not crashed on
- [ ] group authors don't disappear
- [ ] category filter runs inside the parser
- [ ] the `__main__` numbers match the table above

Ping me when it runs and I'll review it.

---

## What's next after this

1. **LaTeX stripping** in `app/search/tokenizer.py`. Right now the regex is
   `[a-zA-Z0-9]+`, so `$O(n\log n)$` becomes the tokens `O`, `n`, `log`, `n`
   and `\cite{}` becomes `cite`. Those junk words go into the vocabulary and
   skew IDF for the entire corpus. `MD/goal.md` flags this specifically.
2. **`database/shema.sql`**, which is currently the words `CREATE DATABASE` and
   nothing else. The `papers` table falls straight out of your `Paper` model.
3. **The crawl loop** — `fetch` + `parse_page` + token, 3 seconds between
   requests. The full corpus is ~21 hours of that, so it has to survive being
   interrupted and resumed.
