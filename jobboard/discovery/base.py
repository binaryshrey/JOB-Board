"""Discovery source contract.

A source's only job is to yield BoardRefs. It never validates, never polls and
never decides what is real -- `jobboard validate` does that in one place, so a
noisy high-recall source costs nothing but HTTP.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from ..models import BoardRef


class Source(ABC):
    name: str = ""
    needs_auth: bool = False

    @abstractmethod
    def discover(self) -> Iterator[BoardRef]:
        ...

    def available(self) -> tuple[bool, str]:
        """Cheap precondition check so a missing token skips one source, not the run."""
        return True, ""
