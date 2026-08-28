"""Careers-page probing: company domain -> ATS board reference.

The most general discovery vector we have. Every other source is limited to
companies some crawler or forum already mentioned; this one only needs a list
of company domains, so its reach is bounded by the corpus rather than by what
the web happened to index. Slow per company, which is why it is concurrent and
short-timeout: most probes miss, and a miss must be cheap.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Iterable, Iterator
from urllib.parse import urlsplit

from ..core import http, urls
from ..core.models import FetchError
from ..core.urls import Ref

# Ordered by hit rate. Kept short: every extra path multiplies the cost of
# the misses, which are the overwhelming majority.
PATHS = ("/careers", "/jobs", "")
# Careers pages are React apps that stash the board URL in a JSON payload at
# the very end -- ramp.com/careers puts it at byte 3.74M of 3.89M. A tight cap
# silently loses exactly the big companies we most want, and it was never the
# real cost anyway: the retry-free session is what made misses cheap.
MAX_BYTES = 4_500_000

# A careers page that links to many different boards is an aggregator, a VC
# portfolio page or a talent network -- not one company's page. Its boards are
# still worth having, but attributing the page owner's name to all of them is
# how getcargo.io ended up labelling 121 boards (Ramp included) as "Cargo".
MAX_ATTRIBUTABLE_REFS = 3


def domain_of(website: str) -> str | None:
    if not website:
        return None
    if "://" not in website:
        website = "https://" + website
    host = (urlsplit(website).hostname or "").lower()
    return host or None


def probe(domain: str, paths: Iterable[str] = PATHS, timeout: float = 6.0
          ) -> tuple[str | None, list[Ref]]:
    """Fetch likely careers URLs; return (url_that_matched, refs).

    Returning the matching URL matters as much as the refs: stored on the board
    it becomes a durable pointer to the company's own careers page, which
    survives an ATS migration that kills the slug.
    """
    found: dict[tuple[str, str], Ref] = {}
    for path in paths:
        for scheme in ("https",):
            try:
                html = http.get_text(f"{scheme}://{domain}{path}", timeout=timeout,
                                     allow_redirects=True, probe=True,
                                     max_bytes=MAX_BYTES)
            except (FetchError, OSError, ValueError):
                # Network-level misses are the normal case here. Anything else
                # (TypeError, AttributeError) is a bug and must not be hidden --
                # a swallowed TypeError once made this look like a 0% hit rate.
                continue
            for ref in urls.extract_all(html):
                found.setdefault((ref.ats, ref.slug), ref)
            if found:
                return f"{scheme}://{domain}{path}", list(found.values())
    return None, []


def probe_many(domains: Iterable[tuple[str, str | None]], workers: int = 12
               ) -> Iterator[tuple[str, str | None, str | None, list[Ref]]]:
    """Yield (domain, company_name, careers_url, refs) concurrently."""
    items = list(domains)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for (domain, name), (url, refs) in zip(items, pool.map(lambda d: probe(d[0]), items)):
            yield domain, name, url, refs
