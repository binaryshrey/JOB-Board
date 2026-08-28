"""Normalized shapes shared by every adapter."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional

# Fields that define "the posting changed". Deliberately excludes volatile
# server-side timestamps (Greenhouse bumps updated_at on no-op republishes),
# which would otherwise make every job look edited on every poll.
_HASHED = (
    "title", "location", "locations", "department", "team",
    "employment_type", "workplace_type", "is_remote", "url", "compensation",
)


@dataclass(slots=True)
class Posting:
    ats: str
    slug: str
    external_id: str
    title: str
    url: str
    apply_url: Optional[str] = None
    location: Optional[str] = None
    locations: list[str] = field(default_factory=list)
    department: Optional[str] = None
    team: Optional[str] = None
    employment_type: Optional[str] = None
    workplace_type: Optional[str] = None
    is_remote: Optional[bool] = None
    posted_at: Optional[int] = None            # epoch seconds, UTC
    compensation: Optional[dict[str, Any]] = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        """Vendor-scoped stable id. Two sources naming the same posting collapse."""
        return f"{self.ats}:{self.slug}:{self.external_id}"

    def content_hash(self) -> str:
        payload = {k: getattr(self, k) for k in _HASHED}
        blob = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


@dataclass(slots=True)
class BoardRef:
    """A board we know about, before it has been validated or polled."""
    ats: str
    slug: str
    company_name: Optional[str] = None
    source: Optional[str] = None
    detail: Optional[dict[str, Any]] = None   # provenance payload, e.g. sample url
    posting: Optional["Posting"] = None       # some sources carry a seed posting


class FetchError(RuntimeError):
    """Transient or permanent failure fetching a board."""

    def __init__(self, message: str, *, permanent: bool = False, status: int | None = None):
        super().__init__(message)
        self.permanent = permanent
        self.status = status
