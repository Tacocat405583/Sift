"""Bulk-harvest arXiv cs via OAI-PMH into data/cs/, one XML file per page.

Resumable: pages already on disk are not re-fetched; their resumption token is
read back from the file and the walk continues. (Tokens expire after ~a day, so
resume within that window or delete the partial run.)

    uv run python -m app.crawler.harvest
"""

import time
from datetime import date

from app.config import settings
from app.crawler.parser import parse_page
from app.crawler.response import fetch

BASE = "https://oaipmh.arxiv.org/oai"
DELAY_SECONDS = 3  # arXiv courtesy limit: 1 request / 3s, single connection


def harvest(start: date, end: date) -> list:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    url = f"{BASE}?verb=ListRecords&set=cs&metadataPrefix=arXiv&from={start}&until={end}"
    paths = []
    page = 1

    while url:
        path = settings.data_dir / f"cs_{start}_{end}_p{page:03d}.xml"
        if path.exists():
            body = path.read_bytes()
            print(f"p{page:03d} on disk")
        else:
            body = fetch(url)
            path.write_bytes(body)
            time.sleep(DELAY_SECONDS)

        papers, token = parse_page(body)
        print(f"p{page:03d}: {len(papers)} target papers")
        paths.append(path)

        url = f"{BASE}?verb=ListRecords&resumptionToken={token}" if token else None
        page += 1

    return paths


if __name__ == "__main__":
    pages = harvest(settings.harvest_from, date.today())
    print(f"done: {len(pages)} pages in {settings.data_dir}")
