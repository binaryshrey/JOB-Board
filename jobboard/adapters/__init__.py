"""Adapter registry. `ats` strings here must match those produced by urls.parse."""
from __future__ import annotations

from .ashby import AshbyAdapter
from .base import Adapter

ADAPTERS: dict[str, Adapter] = {
    AshbyAdapter.ats: AshbyAdapter(),
}

# Recognized by the URL router and stored in the registry, but not yet pollable.
# Adding one is: write the adapter, register it above, and the boards are
# already waiting in the database.
PLANNED = ("greenhouse", "lever", "workday", "smartrecruiters", "workable",
           "recruitee", "breezy", "icims", "bamboohr", "rippling", "jobvite")


def get(ats: str) -> Adapter | None:
    return ADAPTERS.get(ats)


def supported() -> list[str]:
    return sorted(ADAPTERS)
