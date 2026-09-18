import urllib, urllib.request
import arxiv


#Rules

# Point to dedicated mirror
# https://export.arxiv.org

# No more than 1 request every 3 seconds (single connection)
# No multithreading
# 25000 items ≈ 21 hours of continuous running

#Include a descriptive User-Agent header in request
#e.g., User-Agent: MySearchEngineBot/1.0 (contact: myemail@example.com)


output_file = "../../data/cs"


## url = 'http://export.arxiv.org/oai2?verb=Identify'
url = 'https://oaipmh.arxiv.org/oai?verb=ListRecords&set=cs&metadataPrefix=arXiv&from=2026-08-20&until=2026-08-21'

with urllib.request.urlopen(url) as response, open(output_file,"wb") as output_file:
    body = response.read().decode('utf-8')
    response.write()
    print(body)



