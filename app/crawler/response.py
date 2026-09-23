import time
import urllib, urllib.error, urllib.request


#Rules

# Point to dedicated mirror
# https://export.arxiv.org

# No more than 1 request every 3 seconds (single connection)
# No multithreading
# 25000 items ≈ 21 hours of continuous running

#Include a descriptive User-Agent header in request
#e.g., User-Agent: MySearchEngineBot/1.0 (contact: myemail@example.com)

USER_AGENT = "SIFTBot/0.1 (contact: nicolashernan2029@gmail.com, nicolaeh@uci.edu)"

# Fastly sits in front of the OAI endpoint and intermittently answers with a
# bare 406 (empty body, Via: varnish). arXiv also uses 503 + Retry-After for
# flow control. Both mean "ask again", not "your request is wrong".
RETRY_CODES = {406, 503}


def fetch(url: str, attempts: int = 5) -> bytes:

    #headers are useragent
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code not in RETRY_CODES or attempt == attempts:
                raise
            #if we are in our retry codes try again 
            delay = int(error.headers.get("Retry-After", 0)) or attempt * 5
            print(f"  {error.code} {error.reason} - retrying in {delay}s "
                  f"(attempt {attempt}/{attempts})")
            time.sleep(delay)

    raise RuntimeError("unreachable")




if __name__ == "__main__":
    output_file = "../../data/cs/cs_2026-08-20_2026-08-21_p001.xml"

    ## url = 'http://export.arxiv.org/oai2?verb=Identify'
    url = 'https://oaipmh.arxiv.org/oai?verb=ListRecords&set=cs&metadataPrefix=arXiv&from=2026-08-20&until=2026-08-21'

    body = fetch(url)
    with open(output_file,"wb") as file:
        file.write(body)

    print(len(body), "bytes")



