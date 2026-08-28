"""Discovery source registry.

Sources only ever yield BoardRefs. They never validate and never poll, so a
noisy high-recall source costs nothing but HTTP -- `validate` is the single
place that decides what is real.
"""
from __future__ import annotations

from .ashby_customers import AshbyCustomersSource
from .base import Source
from .commoncrawl import CommonCrawlSource
from .github import GitHubSource
from .hn import HackerNewsSource
from .hnhiring import HNHiringSource
from .linkedin import LinkedInSource
from .seedfile import SeedFileSource
from .simplify import SimplifySource
from .urlscan import UrlscanSource
from .wayback import WaybackSource
from .websearch import WebSearchSource
from .ycombinator import YCombinatorSource
from .zero2sudo import Zero2SudoSource

SOURCES: dict[str, type[Source]] = {
    "seedfile": SeedFileSource,
    "ashby_customers": AshbyCustomersSource,
    "simplify": SimplifySource,
    "hn": HackerNewsSource,
    "hn_hiring": HNHiringSource,
    "urlscan": UrlscanSource,
    "commoncrawl": CommonCrawlSource,
    "wayback": WaybackSource,
    "github": GitHubSource,
    "websearch": WebSearchSource,
    "ycombinator": YCombinatorSource,
    "linkedin": LinkedInSource,
    "zero2sudo": Zero2SudoSource,
}

# Cheapest / highest-precision first, so a partial run is still useful.
DEFAULT_ORDER = (
    "seedfile", "ashby_customers", "simplify",
    "hn", "hn_hiring", "urlscan", "commoncrawl", "github",
    "websearch", "ycombinator",
)

# Real sources, excluded from a default run because they are slow, rate-limited
# or need credentials. Run explicitly with -s <name>.
OPT_IN = ("wayback", "linkedin", "zero2sudo")


def build(name: str, **kwargs) -> Source:
    return SOURCES[name](**kwargs)
