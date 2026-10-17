# Architecture

## Search backend chain

`search(query)` tries the configured `SEARCH_BACKEND`, then `SEARCH_FALLBACK`,
and returns the first backend that yields results.

- **duckduckgo** — keyless, via the `ddgs` package. The convenient baseline.
- **searxng** — your own SearXNG instance (`SEARXNG_URL`). Keyless, fast, private.
  Needs JSON output enabled in the instance (`settings.yml`: `search.formats`
  includes `json`).
- **serper** — optional Google results via Serper. Runs only if `SERPER_API_KEY`
  is set, as a last resort.

Each backend returns a uniform list of `{title, url, content, engine}` hits,
deduplicated and domain-filtered.

## Extraction load ladder

`extract(urls)` escalates only as far as a page needs:

1. **Static fetch** with httpx, falling back to `curl_cffi` on 403/429/503.
2. A thin result (under 40 words, or under 300 with challenge text) counts as a
   miss and escalates.
3. **Shared browser** — one shared Chromium, all requests through the SSRF-checked
   proxy, a few slots, closed after idle.
4. **Direct browser** — a page in the same browser that loads through the outbound
   proxy (public addresses and the normal web ports only, resolved address pinned),
   with a short challenge wait.
5. If every stage fails, the static text is kept.

Browser stages need the `browser` extra (`playwright`), and `playwright install
chromium-headless-shell`. The outbound proxy only ever connects to public
addresses on ports 80/443/8080/8443.

## Reranking

`rerank(query, items)` scores each candidate with a cross-encoder and reorders
best-first. The default is a public MiniLM, downloaded on first use. Set
`RERANKER_MODEL` to another Hugging Face name or a local directory to use your own.
