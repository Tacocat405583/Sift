import argparse
import json
import time
from pathlib import Path

from reference.tokenizer import tokenize


class SearchIndex:
    def __init__(self, dataset):
        index_path = Path(f"index_{dataset}.txt")
        offsets_path = Path(f"offsets_{dataset}.json")
        doc_ids_path = Path(f"doc_ids_{dataset}.json")
        norms_path = Path(f"doc_norms_{dataset}.json")

        for p in (index_path, offsets_path, doc_ids_path, norms_path):
            if not p.exists():
                raise FileNotFoundError(
                    f"{p} not found. Run indexer.py and build_seekable.py first."
                )

        print(f"Loading {offsets_path}...")
        with open(offsets_path, "r", encoding="utf-8") as f:
            self.offsets = json.load(f)

        print(f"Loading {doc_ids_path}...")
        with open(doc_ids_path, "r", encoding="utf-8") as f:
            self.doc_ids = json.load(f)

        print(f"Loading {norms_path}...")
        with open(norms_path, "r", encoding="utf-8") as f:
            self.doc_norms = json.load(f)

        print(f"Opening {index_path}...")
        self.index_file = open(index_path, "rb")
        print(
            f"Ready. {len(self.offsets):,} tokens, "
            f"{len(self.doc_ids):,} documents.\n"
        )

    def get_postings(self, token):
        offset = self.offsets.get(token)
        if offset is None:
            return None
        self.index_file.seek(offset)
        line = self.index_file.readline()
        return json.loads(line)["p"]

    def search(self, query, top_k=5):
        start = time.perf_counter()
        # deduplicate tokens while preserving order
        seen = set()
        tokens = []
        for t in tokenize(query):
            if t not in seen:
                seen.add(t)
                tokens.append(t)

        if not tokens:
            return [], 0, 0.0

        all_postings = []
        for tok in tokens:
            postings = self.get_postings(tok)
            if postings:  # skip terms absent from index (zero-IDF terms excluded at build time)
                all_postings.append(postings)

        if not all_postings:
            return [], 0, (time.perf_counter() - start) * 1000

        all_postings.sort(key=len)

        # AND intersection: only score docs containing every indexed query term
        hits = {p[0] for p in all_postings[0]}
        for postings in all_postings[1:]:
            hits &= {p[0] for p in postings}
            if not hits:
                return [], 0, (time.perf_counter() - start) * 1000

        # Accumulate tf-idf dot product for intersection docs
        dot = {}
        for postings in all_postings:
            for doc_id, tf_idf in postings:
                if doc_id in hits:
                    dot[doc_id] = dot.get(doc_id, 0.0) + tf_idf

        # Cosine normalize by pre-computed doc L2 norm
        scores = {}
        for doc_id, d in dot.items():
            norm = self.doc_norms.get(str(doc_id), 1.0)
            scores[doc_id] = d / norm if norm > 0 else 0.0

        ranked = sorted(scores.items(), key=lambda x: -x[1])
        results = []
        seen_urls = set()
        for doc_id, score in ranked:
            url = self.doc_ids[str(doc_id)]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            results.append((url, score))
            if len(results) >= top_k:
                break

        elapsed = (time.perf_counter() - start) * 1000
        return results, len(scores), elapsed

    def close(self):
        self.index_file.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset", choices=["analyst", "developer"], default="developer"
    )
    parser.add_argument("--top", type=int, default=5)
    args = parser.parse_args()

    idx = SearchIndex(args.dataset)
    print("Type a query and press enter. Type 'exit' or Ctrl-D to quit.\n")

    try:
        while True:
            try:
                query = input("query> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not query:
                continue
            if query.lower() in ("exit", "quit", ":q"):
                break

            results, total_hits, elapsed = idx.search(query, top_k=args.top)

            if not results:
                print(f"  (no results, {elapsed:.1f} ms)\n")
                continue

            for i, (url, score) in enumerate(results, 1):
                print(f"  {i}. [{score:.4f}] {url}")
            print(f"  ({total_hits} hits, {elapsed:.1f} ms)\n")
    finally:
        idx.close()


if __name__ == "__main__":
    main()
