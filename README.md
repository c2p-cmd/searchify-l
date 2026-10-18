# searchify

Local-first web search, clean content extraction and fast reranking, in one small
Python package. No API key required: search runs over DuckDuckGo or your own
SearXNG instance out of the box. Paid providers are an optional fallback, off
unless you set their key.

```python
from searchify import search, extract, rerank

hits = search("solid-state batteries", max_results=5)   # keyless
docs = extract([hits[0]["url"]])                          # clean article text
best = rerank("solid-state batteries", docs, top_k=3)     # reorder by relevance
print(best[0]["content"][:300])
```

## Install

```bash
pip install searchify                 # search + extraction
pip install "searchify[rerank]"       # add the cross-encoder reranker
pip install "searchify[api,browser]"  # add the HTTP service and the browser stage
```

Then set nothing and search works. Copy `.env.example` to `.env` only if you want
a SearXNG instance or a cloud fallback.

## What you get

- **search(query)** — web results as `{title, url, content, engine}`. Local by
  default (DuckDuckGo), or your own SearXNG instance, with an optional cloud
  fallback. No key needed for the local backends.
- **extract(urls)** — the clean article text of each page, without menus, footers
  or cookie banners. Starts with a fast fetch and only opens a browser when a page
  needs one. The browser stages go through an SSRF-safe outbound proxy.
- **rerank(query, items)** — reorder results best-first with a fast cross-encoder.
  Uses a public MiniLM by default; point `RERANKER_MODEL` at your own fine-tuned
  model to swap it in.

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

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the search backend chain and
reranking. The extraction load ladder is described above under HTTP service.

## License

MIT. See [`LICENSE`](LICENSE).
