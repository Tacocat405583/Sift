import json
from pathlib import Path
from bs4 import BeautifulSoup
from tokenizer import tokenize
from collections import Counter

from bs4 import XMLParsedAsHTMLWarning, MarkupResemblesLocatorWarning
import warnings
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

from tqdm import tqdm

PARTIAL_THRESHOLD = 15000

IMPORTANT_TAGS = ["title", "h1", "h2", "h3", "b", "strong"]

def parse_document(filepath):
    p = Path(filepath)
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
        url = data["url"].split("#")[0]
        content = data["content"]
    except (json.JSONDecodeError, KeyError, OSError) as e:
        print(f"Skipping {p.name}: {type(e).__name__}")
        return None
    
    soup = BeautifulSoup(content, "lxml")

    text = soup.get_text()
    tokens = tokenize(text)

    important_tokens = []
    for tag in soup.find_all(IMPORTANT_TAGS):
        important_tokens.extend(tokenize(tag.get_text()))

    return (url, tokens, important_tokens)


def dump_partial(index, partial_num):
    path = f"partial_{partial_num}.json"
    with open(path, "w") as f:
        json.dump(index, f)


def merge_partials():
    final_index = {}
    for pf in sorted(Path(".").glob("partial_*.json")):
        with open(pf, "r") as f:
            partial = json.load(f)
        for token, postings in partial.items():
            if token not in final_index:
                final_index[token] = []
            final_index[token].extend(postings)
        pf.unlink()
    return final_index


def build_index(dataset_path, doc_ids_path="doc_ids.json"):
    p = Path(dataset_path)
    if not p.exists():
        raise FileNotFoundError(
            f"Dataset path not found: {dataset_path}. "
            f"Did you unzip the corpus into this folder?"
        )

    index = {}
    doc_id_map = {} # this is for turning urls to nums
    doc_count = 0
    partial_num = 0

    for file_path in tqdm(list(p.rglob("*.json"))):
        result = parse_document(filepath=file_path)
        if result is None:
            continue
        doc_count += 1
        doc_id = doc_count

        url, tokens, important_tokens = result
        doc_id_map[doc_id] = url

        counts = Counter(tokens)
        imp_counts = Counter(important_tokens)

        for token, freq in counts.items():
            if token not in index:
                index[token] = []
            index[token].append({
                "doc_id": doc_id, 
                "frequency": freq,
                "importance": imp_counts.get(token, 0)
            })

        if doc_count % PARTIAL_THRESHOLD == 0:
            dump_partial(index, partial_num)
            index = {}
            partial_num += 1

    dump_partial(index, partial_num)
    index = merge_partials()

    with open(doc_ids_path, "w") as f:
        json.dump(doc_id_map, f)

    return index, doc_count


def save_index(index, output_pth):
    with open(output_pth, "w") as f:
        json.dump(index, f)

    return Path(output_pth).stat().st_size / 1024


if __name__ == "__main__":
    print("DEVELOPER DATA")
    index, doc_count = build_index("developer/DEV", "doc_ids_developer.json")
    save_index(index, "index_developer.json")
