from lxml import etree

path = "../../data/cs/cs_2026-08-20_2026-08-21_p001.xml"

with open(path,'r') as file:
    xml_data = file.read()



root = etree.fromstring(xml_data.encode('utf-8'))

# Map prefixes
ns = {
    'oai':"http://www.openarchives.org/OAI/2.0/",
    'arxiv': 'http://arxiv.org/OAI/arXiv/'
}


records = root.xpath('//oai:record',namespace = ns)


# 3. Find all record elements using the 'arxiv' prefix
records = root.xpath('//oai:record', namespaces=ns)

for record in records:
    # Extract from <header> (uses OAI namespace)
    identifier = record.xpath('.//oai:identifier/text()', namespaces=ns)
    
    # Extract from <metadata> -> <arXiv> (uses arXiv namespace)
    title = record.xpath('.//arxiv:title/text()', namespaces=ns)
    abstract = record.xpath('.//arxiv:abstract/text()', namespaces=ns)

    arxiv_id = record.xpath('.//arxiv:id/text()', namespaces=ns)
    
    print(f"ID: {identifier} | ArXiv ID: {arxiv_id}")
    print(f"Title: {title}\n" + "-"*50)
    print(f"Abstract: {abstract}")
