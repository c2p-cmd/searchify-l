<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
    <img src="assets/logo-light.svg" alt="searchify" width="380">
  </picture>
</p>

**Web search for AI agents, running on your own machine.** Ask a question and get back the
passages that answer it, with their sources. Search, clean page extraction and a fast
reranker in one small Python package. No API key needed: search runs over DuckDuckGo or
your own SearXNG instance, paid providers are an optional fallback.

```
$ python examples/answer.py "When did the Berlin Wall fall?"
1. The Berlin Wall fell on November 9, 1989, when East German authorities mistakenly
   announced immediate travel freedoms during a press conference. East Berliners ...
   www.berlintourism.org
2. The Berlin Wall fell on 9 November 1989 during the Peaceful Revolution, marking the
   beginning of the destruction of the figurative Iron Curtain, as East Berlin ...
   en.wikipedia.org
3. The fall of the Berlin Wall in November of 1989 was a defining moment in modern world
   history and the Cold War. In fact, the Berlin Wall had stood as one of ...
   historycrunch.com

searched and read 5 pages in 2.6 s, ranked 506 passages in 1.9 s
```

That is the whole pipeline in [`examples/answer.py`](examples/answer.py), about 20 lines:

```python
from searchify import search, extract, rerank

hits = search(question, max_results=8)                    # keyless web search
pages = extract([h["url"] for h in hits[:5]])             # clean text of the top pages
passages = [{"content": p, "url": page["url"]}            # one item per paragraph
            for page in pages for p in page["content"].split("\n")
            if len(p.split()) >= 12]
best = rerank(question, passages, top_k=3)                # the paragraphs that answer it
```

Run it once and the reranker model (about 470 MB) downloads; after that it is cached.

## Install

Not on PyPI yet, so install from GitHub:

```bash
pip install "searchify[rerank] @ git+https://github.com/sami-mag07/searchify-l"
```

| Extra | Adds |
|---|---|
| (none) | search and extraction |
| `rerank` | the cross-encoder reranker (`sentence-transformers`) |
| `api` | the HTTP service (`fastapi`, `uvicorn`) |
| `browser` | the browser stages for JavaScript and bot-protected pages (`playwright`) |
| `stealth` | the optional Camoufox stage |

Then set nothing and search works. Copy `.env.example` to `.env` only if you want a SearXNG
instance or a cloud fallback.

## What you get

| Call | What it does |
|---|---|
| `search(query)` | Web results as `{title, url, content, engine}`. DuckDuckGo by default, or your own SearXNG instance, with an optional cloud fallback. |
| `extract(urls)` | The clean article text of each page, without menus, footers or cookie banners. Starts with a fast fetch and only opens a browser when a page needs one. |
| `rerank(query, items)` | Reorders results or passages best-first with a multilingual cross-encoder (`mmarco-mMiniLMv2`). Point `RERANKER_MODEL` at your own model to swap it. |
| `POST /search`, `POST /extract` | The same as an HTTP service, see below. |

## Benchmark

Run `final_2031`, 15 Oct 2026, 146 fresh pages (Wikipedia, GitHub, Hacker News, news,
bot-protected) against the top open-source scrapers on GitHub. Fresh means no page was seen
in an earlier run, so nobody serves it from cache. Scrapling is not included in this run.

**Quality (F1) per scraper**, higher is better:

```
searchify      84%  ████████████████▊   best
patchright     83%  ████████████████▌
trafilatura    82%  ████████████████▍
firecrawl      73%  ██████████████▌
crawl4ai       66%  █████████████▏
```

F1 is the balance of precision and recall of the extracted main text: it drops both when real
article text is missing and when boilerplate leaks in. Searchify leads on F1 and on the share
of pages it handles at all, while two tools (firecrawl, crawl4ai) are fast but let a lot of
boilerplate through, which is why their F1 is low despite a high raw hit rate.

**Full table:**

| Scraper | Handled | Hit | Clean | F1 | p50 | p95 | RAM |
|---|---:|---:|---:|---:|---:|---:|---:|
| **searchify** | **87%** | 91% | 84% | **84%** | 0.47 s | 5.00 s | 3751 MB |
| own baseline | 85% | 91% | 81% | 82% | 0.24 s | 1.30 s | 4364 MB |
| patchright | 80% | 88% | 85% | 83% | 1.80 s | 7.01 s | 2196 MB |
| trafilatura | 79% | 88% | 84% | 82% | 0.23 s | 0.86 s | 195 MB |
| firecrawl | 84% | 92% | 65% | 73% | 2.68 s | 8.79 s | 3947 MB |
| crawl4ai | 84% | 92% | 58% | 66% | 1.11 s | 3.44 s | 1995 MB |

What the columns mean:

- **Handled**: pages that returned usable content at all.
- **Hit**: pages where the expected text was found.
- **Clean**: how much of the output is real article text and not navigation or boilerplate.
- **F1**: the overall quality score (precision and recall combined).
- **p50 / p95**: median and 95th-percentile response time.
- **RAM**: peak memory. Searchify's figure includes the reranker that runs inside the same
  service (around 1 to 2 GB); the other tools have no reranker, so their RAM is not directly
  comparable.

**Bot-protected pages (the hard set)**, share handled, higher is better:

```
searchify      31%  ███████████████▌   best
own baseline   19%  █████████▌
firecrawl      19%  █████████▌
crawl4ai       15%  ███████▌
patchright      0%
trafilatura     0%
```

Static-only tools (trafilatura) and plain headless browsers (patchright, in this run) get nothing
on these pages. Searchify gets the most through because its last stage waits out the challenge
on a real browser behind the outbound proxy.

**Versus the previous own baseline:** cleaner output (+3), higher F1 (+2), and 500 to 600 MB less
RAM. The one regression is p95 (1.3 s to 5.0 s): blocked pages wait up to 6 seconds for the
Cloudflare challenge to resolve. That affects about 4% of pages and is a deliberate trade, since
the challenge only clears after roughly 5 seconds.

Rules kept during tuning: no captcha solving, no result gaming (never remove real text just to
raise a number), the safety limits never weakened. The run measured the default ladder below;
the optional Camoufox stage (`READER_STEALTH=1`) was not part of it.

## How it works

```mermaid
flowchart LR
    Q[Question] --> S[search<br/>DuckDuckGo or SearXNG]
    S --> F[extract<br/>fast fetch first]
    F -->|thin or blocked| B[browser stages<br/>behind a safe proxy]
    F --> X[clean text<br/>resiliparse, trafilatura]
    B --> X
    X --> R[rerank<br/>cross-encoder]
    R --> O[Best passages<br/>with sources]
```

Every stage only runs when the previous one was not enough: most pages never open a
browser, and the browser stages only ever connect to public addresses on the normal web
ports. Details: [`docs/architecture.md`](docs/architecture.md).

## Search backends

| Backend | Key needed | Notes |
|---|---|---|
| `duckduckgo` | no | Default. Works immediately via the `ddgs` package. |
| `searxng` | no | Your own instance. Fast and private; set `SEARXNG_URL`. |
| `serper` | yes | Optional Google fallback. Off unless `SERPER_API_KEY` is set. |

Choose the primary with `SEARCH_BACKEND` and a fallback with `SEARCH_FALLBACK`.
The default chain is local only: DuckDuckGo, then SearXNG if configured.

```python
from searchify import search

# keyless, out of the box
hits = search("who makes solid-state batteries", max_results=10)

# your own SearXNG instance
hits = search("quarterly earnings tsmc", backend="searxng", time_range="month")

# restrict to domains
hits = search("transformer architecture", include_domains=["arxiv.org"])
```

## HTTP service

Run the service and send it web addresses, one or many at a time:

```bash
uvicorn searchify.service:app
curl -s http://localhost:8000/search  -H 'content-type: application/json' -d '{"query": "solid-state batteries"}'
curl -s http://localhost:8000/extract -H 'content-type: application/json' \
  -d '{"urls": ["https://en.wikipedia.org/wiki/Web_scraping",
                "https://en.wikipedia.org/wiki/Data_scraping"]}'
```

In Python:

```python
import requests

answer = requests.post(
    "http://localhost:8000/extract",
    json={"urls": ["https://en.wikipedia.org/wiki/Web_scraping"]},
)
print(answer.json())   # the clean text for each address
```

**How it decides how hard to try (the load ladder, `read_pages`):**

1. **Plain fetch** with httpx, falling back to curl_cffi when the site answers 403/429/503.
   The fast path.
2. A thin result (under 40 words, or under 300 with challenge text) counts as a miss and
   moves on.
3. **Shared browser**: one shared Chromium, all requests through the safety-checked proxy,
   3 slots, closes after 300 s idle. Reddit only works here.
4. **Direct browser**: a page in the same browser that loads through the outbound proxy
   (public addresses and the normal web ports only, address pinned), challenge wait 6 s,
   2 slots.
5. If every stage fails, the plain text is kept. At most 2 pages per request open a browser.

**Browser settings** (environment variables):

- `READER_RENDER=0` turns all browser stages off (plain fetch only).
- `RENDER_DIRECT=0` turns off stage 4 only.
- `RENDER_SLOTS`, `RENDER_DIRECT_SLOTS` set how many pages open a browser at once.
- `READER_STEALTH=1` with `CAMOUFOX_PYTHON` adds Camoufox as a last stage, at most once per
  request. Off by default.

The browser stages need `pip install "searchify[browser]"` and
`playwright install chromium-headless-shell`.

## Configuration

Every setting is optional and read from the environment (see `.env.example`):
`SEARCH_BACKEND`, `SEARCH_FALLBACK`, `SEARXNG_URL`, `SERPER_API_KEY`,
`RERANKER_MODEL`, `FETCH_TIMEOUT`. No key is ever read from code.

## Tests

```bash
pip install -e ".[dev,api]"
pytest
```

## Limits

- No own web index. Breadth depends on DuckDuckGo or the engines behind your SearXNG.
- DuckDuckGo rate-limits heavy use. For anything beyond a few queries a minute, run SearXNG.
- Bot-protected pages: 31% get through (see the benchmark). There is no captcha solving.
- The first `rerank` call loads the model, which takes a few seconds.

## License

MIT. See [`LICENSE`](LICENSE).
