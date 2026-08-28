"""Discovery source registry."""
from __future__ import annotations

from .base import Source
from .commoncrawl import CommonCrawlSource
from .github import GitHubSource
from .hn import HackerNewsSource
from .hnhiring import HNHiringSource
from .seedfile import SeedFileSource
from .simplify import SimplifySource
from .wayback import WaybackSource

SOURCES: dict[str, type[Source]] = {
    "simplify": SimplifySource,
    "seedfile": SeedFileSource,
    "commoncrawl": CommonCrawlSource,
    "wayback": WaybackSource,
    "hn": HackerNewsSource,
    "hn_hiring": HNHiringSource,
    "github": GitHubSource,
}

# Ordered cheapest/highest-precision first, so a partial run is still useful.
DEFAULT_ORDER = ("seedfile", "simplify", "hn", "hn_hiring",
                 "commoncrawl", "wayback", "github")


def build(name: str, **kwargs) -> Source:
    return SOURCES[name](**kwargs)
