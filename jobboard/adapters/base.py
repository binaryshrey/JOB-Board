"""Adapter contract. One class per ATS; the reconciler knows nothing else."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Posting


class Adapter(ABC):
    ats: str = ""

    @abstractmethod
    def board_url(self, slug: str) -> str:
        """The endpoint a poll hits. Used for logging and per-host throttling."""

    @abstractmethod
    def fetch(self, slug: str) -> list[Posting]:
        """Return every currently-listed posting on the board.

        Must raise FetchError(permanent=True) when the board provably does not
        exist, and FetchError(permanent=False) for anything transient. The
        reconciler relies on that distinction: it never closes postings on a
        failed poll, and only a permanent failure can mark a board dead.
        """
