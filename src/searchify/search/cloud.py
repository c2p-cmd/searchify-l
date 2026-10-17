"""Optional cloud backend: Google results via the Serper API.

This is off by default. It only runs when SERPER_API_KEY is set, as an optional
last resort when you want Google coverage. The local backends (DuckDuckGo,
SearXNG) need no key and are the default.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import httpx

from ..config import get_settings
from ._common import COUNTRY_FOR_LANG, SearchBackendError, dedupe_and_filter, site_scoped


def serper_search(
    query: str,
    max_results: int = 10,
    *,
    topic: str = "general",
    language: Optional[str] = None,
    country: Optional[str] = None,
    time_range: Optional[str] = None,
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None,
    **_: object,
) -> List[Dict[str, str]]:
    """Google results via Serper (SERPER_API_KEY from the environment)."""
    settings = get_settings()
    if not settings.serper_api_key:
        raise SearchBackendError("SERPER_API_KEY is not set (set it only via the environment).")

    body: Dict[str, object] = {
        "q": site_scoped(query, include_domains),
        "num": 10 if max_results <= 10 else 20,
    }
    if language:
        body["hl"] = language
    gl = country or COUNTRY_FOR_LANG.get(language or "")
    if gl:
        body["gl"] = gl
    if time_range:
        body["tbs"] = {"day": "qdr:d", "week": "qdr:w", "month": "qdr:m", "year": "qdr:y"}.get(time_range, "")
    endpoint = "news" if topic == "news" else "search"

    try:
        with httpx.Client(timeout=settings.fetch_timeout) as client:
            resp = client.post(
                f"https://google.serper.dev/{endpoint}",
                json=body,
                headers={"X-API-KEY": settings.serper_api_key},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:120] if exc.response is not None else ""
        raise SearchBackendError(f"Serper error {exc.response.status_code}: {detail}") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise SearchBackendError(f"Serper unreachable: {type(exc).__name__}") from exc

    items = data.get("news" if topic == "news" else "organic", [])
    hits = [
        {
            "title": (it.get("title") or "").strip(),
            "url": (it.get("link") or "").strip(),
            "content": (it.get("snippet") or "").strip(),
            "engine": "serper",
        }
        for it in items
    ]
    return dedupe_and_filter(hits, exclude_domains or [], max_results, include_domains)
