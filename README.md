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

```bash
uvicorn searchify.service:app
curl -s http://localhost:8000/search  -d '{"query": "solid-state batteries"}'
curl -s http://localhost:8000/extract -d '{"urls": ["https://en.wikipedia.org/wiki/Web_scraping"]}'
```

## Configuration

Every setting is optional and read from the environment (see `.env.example`):
`SEARCH_BACKEND`, `SEARCH_FALLBACK`, `SEARXNG_URL`, `SERPER_API_KEY`,
`RERANKER_MODEL`, `FETCH_TIMEOUT`. No key is ever read from code.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the extraction load ladder
and the search backend chain.

## License

MIT. See [`LICENSE`](LICENSE).
