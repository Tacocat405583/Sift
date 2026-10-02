import time

import requests

# Rules

# Point to dedicated mirror
# https://export.arxiv.org

# No more than 1 request every 3 seconds (single connection)
# No multithreading
# 25000 items ≈ 21 hours of continuous running

# Include a descriptive User-Agent header in request
# e.g., User-Agent: MySearchEngineBot/1.0 (contact: myemail@example.com)

USER_AGENT = "SIFTBot/0.1 (contact: nicolashernan2029@gmail.com, nicolaeh@uci.edu)"

# Fastly sits in front of the OAI endpoint and intermittently answers with a
# bare 406 (empty body, Via: varnish). arXiv also uses 503 + Retry-After for
# flow control. Both mean "ask again", not "your request is wrong".
RETRY_CODES = {406, 503}


# Fastly kept 406-ing urllib on requests that curl and `requests` got 200 on (same URL,
# same headers), so we use requests. One Session = one reused connection, per the rules.
_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/xml, */*"})


def fetch(url: str, attempts: int = 5) -> bytes:
    for attempt in range(1, attempts + 1):
        response = _session.get(url, timeout=90)
        if response.ok:
            return response.content
        if response.status_code not in RETRY_CODES or attempt == attempts:
            response.raise_for_status()
        # if we are in our retry codes try again
        delay = int(response.headers.get("Retry-After", 0)) or attempt * 5
        print(
            f"  {response.status_code} {response.reason} - retrying in {delay}s "
            f"(attempt {attempt}/{attempts})"
        )
        time.sleep(delay)

    raise RuntimeError("unreachable")


if __name__ == "__main__":
    output_file = "../../data/cs/cs_2026-08-20_2026-08-21_p001.xml"

    ## url = 'http://export.arxiv.org/oai2?verb=Identify'
    url = "https://oaipmh.arxiv.org/oai?verb=ListRecords&set=cs&metadataPrefix=arXiv&from=2026-08-20&until=2026-08-21"

    body = fetch(url)
    with open(output_file, "wb") as file:
        file.write(body)

    print(len(body), "bytes")
