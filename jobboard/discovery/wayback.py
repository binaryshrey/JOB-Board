"""Wayback Machine CDX index.

A genuinely different corpus from Common Crawl -- the Archive captures pages CC
never sampled, and captures them more often. The catch is aggressive rate
limiting (a single large query returns 429), so this source paginates and paces
itself deliberately rather than asking for everything at once.
"""
from __future__ import annotations

import time
from typing import Iterator

from .. import http, urls
from ..models import BoardRef, FetchError
from .base import Source

CDX = "https://web.archive.org/cdx/search/cdx"
DEFAULT_HOSTS = ("jobs.ashbyhq.com",)


class WaybackSource(Source):
    name = "wayback"

    def __init__(self, hosts=None, pause: float = 3.0, max_pages: int = 40,
                 retries: int = 4):
        self.hosts = tuple(hosts or DEFAULT_HOSTS)
        self.pause = pause
        self.max_pages = max_pages
        self.retries = retries

    def _params(self, host: str, **extra) -> dict:
        return {"url": host, "matchType": "prefix", "fl": "original",
                "collapse": "urlkey", "output": "text", **extra}

    def _pages(self, host: str) -> int:
        try:
            for line in http.get_lines(CDX, params=self._params(host, showNumPages="true")):
                return int(line.strip())
        except (FetchError, ValueError):
            return 1
        return 1

    def discover(self) -> Iterator[BoardRef]:
        seen: set[tuple[str, str]] = set()
        for host in self.hosts:
            pages = min(self._pages(host), self.max_pages)
            for page in range(pages):
                lines = None
                for attempt in range(self.retries):
                    try:
                        # Materialize inside the retry loop: a 429 surfaces on
                        # the first read, not at request time.
                        lines = list(http.get_lines(
                            CDX, params=self._params(host, page=str(page))))
                        break
                    except FetchError:
                        time.sleep(self.pause * (2 ** attempt))
                if lines is None:
                    continue
                for line in lines:
                    ref = urls.parse(line.strip())
                    if ref and (ref.ats, ref.slug) not in seen:
                        seen.add((ref.ats, ref.slug))
                        yield BoardRef(ref.ats, ref.slug, None, self.name,
                                       {"host": host, "page": page})
                time.sleep(self.pause)
