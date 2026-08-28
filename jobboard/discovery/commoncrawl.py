"""Common Crawl index -- first-party, re-runnable board enumeration.

Better than any static slug dump: we query the CDX index ourselves, so we can
union across many monthly crawls and re-run against the newest one. Verified
2026-08: jobs.ashbyhq.com/* is only ~2 pages per crawl, so a wide sweep is a
few dozen GETs.
"""
from __future__ import annotations

import json
from typing import Iterator
from urllib.parse import quote

from ..core import http, urls
from ..core.models import BoardRef, FetchError
from .base import Source

COLLINFO = "https://index.commoncrawl.org/collinfo.json"
INDEX = "https://index.commoncrawl.org/{crawl}-index"

# Only hosts whose URLs carry the board slug in the path are worth sweeping.
DEFAULT_HOSTS = ("jobs.ashbyhq.com",)
ALL_HOSTS = (
    "jobs.ashbyhq.com",
    "job-boards.greenhouse.io",
    "boards.greenhouse.io",
    "jobs.lever.co",
    "apply.workable.com",
    "jobs.smartrecruiters.com",
)


class CommonCrawlSource(Source):
    name = "commoncrawl"

    def __init__(self, hosts=None, crawls: int = 4):
        self.hosts = tuple(hosts or DEFAULT_HOSTS)
        self.crawls = crawls

    def _recent_crawls(self) -> list[str]:
        data = http.get_json(COLLINFO)
        return [c["id"] for c in data[: self.crawls]]

    def _pages(self, crawl: str, host: str) -> int:
        url = INDEX.format(crawl=crawl)
        try:
            info = http.get_json(url, params={
                "url": f"{host}/*", "output": "json", "showNumPages": "true"})
        except FetchError:
            return 0
        return int(info.get("pages", 0)) if isinstance(info, dict) else 0

    def discover(self) -> Iterator[BoardRef]:
        seen: set[tuple[str, str]] = set()
        for crawl in self._recent_crawls():
            for host in self.hosts:
                pages = self._pages(crawl, host)
                for page in range(pages):
                    url = INDEX.format(crawl=crawl)
                    try:
                        lines = http.get_lines(url, params={
                            "url": f"{host}/*", "output": "json", "page": str(page)})
                        for line in lines:
                            if not line.startswith("{"):
                                continue
                            try:
                                rec = json.loads(line)
                            except ValueError:
                                continue
                            ref = urls.parse(rec.get("url", ""))
                            if ref and (ref.ats, ref.slug) not in seen:
                                seen.add((ref.ats, ref.slug))
                                yield BoardRef(ref.ats, ref.slug, None, self.name,
                                               {"crawl": crawl, "host": host})
                    except FetchError:
                        continue
