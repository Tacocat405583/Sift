from datetime import date

from app.crawler.parser import parse_page

PAGE = b"""<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <ListRecords>
    <record>
      <header>
        <identifier>oai:arXiv.org:2609.00001</identifier>
        <datestamp>2026-09-02</datestamp>
      </header>
      <metadata>
        <arXiv xmlns="http://arxiv.org/OAI/arXiv/">
          <id>2609.00001</id>
          <created>2026-09-01</created>
          <authors>
            <author><keyname>Lovelace</keyname><forenames>Ada</forenames></author>
            <author><keyname>Turing</keyname></author>
          </authors>
          <title>Attention
            Is Enough</title>
          <categories>cs.CL cs.LG</categories>
          <abstract>  We study
            attention.  </abstract>
        </arXiv>
      </metadata>
    </record>
    <record>
      <header>
        <identifier>oai:arXiv.org:2609.00002</identifier>
        <datestamp>2026-09-02</datestamp>
      </header>
      <metadata>
        <arXiv xmlns="http://arxiv.org/OAI/arXiv/">
          <id>2609.00002</id>
          <created>2026-09-01</created>
          <title>Compilers</title>
          <categories>cs.PL</categories>
          <abstract>Off topic.</abstract>
        </arXiv>
      </metadata>
    </record>
    <record>
      <header status="deleted">
        <identifier>oai:arXiv.org:2609.00003</identifier>
        <datestamp>2026-09-02</datestamp>
      </header>
    </record>
    <resumptionToken cursor="0">abc%3D123</resumptionToken>
  </ListRecords>
</OAI-PMH>"""


def test_parse_page_keeps_target_categories_only():
    papers, token = parse_page(PAGE)

    assert token == "abc%3D123"
    assert [p.arxiv_id for p in papers] == ["2609.00001"]

    paper = papers[0]
    assert paper.title == "Attention Is Enough"
    assert paper.abstract == "We study attention."
    assert paper.authors == ["Ada Lovelace", "Turing"]
    assert paper.categories == ["cs.CL", "cs.LG"]
    assert paper.published_at == date(2026, 9, 1)
    assert paper.updated_at == date(2026, 9, 2)


def test_last_page_has_no_token():
    last = PAGE.replace(
        b'<resumptionToken cursor="0">abc%3D123</resumptionToken>', b'<resumptionToken cursor="0"/>'
    )
    _, token = parse_page(last)
    assert token is None
