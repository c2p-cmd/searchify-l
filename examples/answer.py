"""Answer a question with the passages that say it, straight from the web.

    python examples/answer.py "When did the Berlin Wall fall?"
"""
import sys
import time
from urllib.parse import urlparse

from searchify import extract, rerank, search


def short(text: str, limit: int = 160) -> str:
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " ..."


def main() -> None:
    question = " ".join(sys.argv[1:]) or "When did the Berlin Wall fall?"

    t = time.perf_counter()
    hits = search(question, max_results=8)
    pages = extract([h["url"] for h in hits[:5]])
    read_s = time.perf_counter() - t

    passages = [
        {"content": para.strip(), "url": page["url"]}
        for page in pages
        for para in page["content"].split("\n")
        if len(para.split()) >= 12
    ]
    rerank(question, passages[:1])  # load the model once, so the timing below is the ranking
    t = time.perf_counter()
    best = rerank(question, passages, top_k=3)
    rank_s = time.perf_counter() - t

    for i, p in enumerate(best, 1):
        print(f"{i}. {short(p['content'])}\n   {urlparse(p['url']).netloc}")
    print(f"\nsearched and read {len(pages)} pages in {read_s:.1f} s, "
          f"ranked {len(passages)} passages in {rank_s:.1f} s")


if __name__ == "__main__":  # extraction uses worker processes, so the guard is required
    main()
