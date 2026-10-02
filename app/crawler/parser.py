"""Turn one OAI-PMH ListRecords page (metadataPrefix=arXiv) into Paper objects.

Bytes in, papers out. Records outside the target categories are dropped here so
nothing downstream ever sees them.
"""

from datetime import date

from lxml import etree
from pydantic import BaseModel

from app.config import settings

NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "arxiv": "http://arxiv.org/OAI/arXiv/",
}


class Paper(BaseModel):
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    categories: list[str]
    published_at: date  # <created> of the first version
    updated_at: date  # OAI <datestamp>: last modified, which is what from/until filters on


def _text(node: etree._Element, path: str) -> str:
    """First match of an XPath, whitespace collapsed (titles/abstracts contain hard newlines)."""
    found = node.xpath(path, namespaces=NS)
    return " ".join(found[0].split()) if found else ""


def _authors(meta: etree._Element) -> list[str]:
    names = []
    for author in meta.xpath("arxiv:authors/arxiv:author", namespaces=NS):
        parts = [
            _text(author, "arxiv:forenames/text()"),
            _text(author, "arxiv:keyname/text()"),
            _text(author, "arxiv:suffix/text()"),
        ]
        names.append(" ".join(p for p in parts if p))
    return names


def parse_page(xml: bytes) -> tuple[list[Paper], str | None]:
    """Return (papers in target categories, resumption token or None if this is the last page)."""
    root = etree.fromstring(xml)
    papers = []

    for record in root.xpath("//oai:record", namespaces=NS):
        header = record.find("oai:header", NS)
        if header.get("status") == "deleted":  # withdrawn records carry no metadata
            continue

        meta = record.find("oai:metadata/arxiv:arXiv", NS)
        categories = _text(meta, "arxiv:categories/text()").split()
        if not settings.categories.intersection(categories):
            continue

        papers.append(
            Paper(
                arxiv_id=_text(meta, "arxiv:id/text()"),
                title=_text(meta, "arxiv:title/text()"),
                abstract=_text(meta, "arxiv:abstract/text()"),
                authors=_authors(meta),
                categories=categories,
                published_at=_text(meta, "arxiv:created/text()"),
                updated_at=_text(header, "oai:datestamp/text()"),
            )
        )

    token = root.xpath("//oai:resumptionToken/text()", namespaces=NS)
    return papers, (token[0].strip() or None) if token else None


if __name__ == "__main__":
    sample = settings.data_dir / "cs_2026-08-20_2026-08-21_p001.xml"
    papers, token = parse_page(sample.read_bytes())
    print(f"{len(papers)} papers kept, next token: {token}")
    print(papers[0].model_dump_json(indent=2))
