"""One shared HTTP client with retries, timeouts and a per-host concurrency cap."""
from __future__ import annotations

import threading
from collections import defaultdict
from contextlib import contextmanager
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config

_local = threading.local()
_host_locks: dict[str, threading.Semaphore] = defaultdict(
    lambda: threading.Semaphore(config.PER_HOST_CONCURRENCY)
)
_host_locks_guard = threading.Lock()


def session() -> requests.Session:
    """Thread-local session: connection pooling without cross-thread sharing."""
    s = getattr(_local, "session", None)
    if s is None:
        s = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "HEAD"]),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=config.WORKERS * 2)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        s.headers.update({"User-Agent": config.USER_AGENT, "Accept": "application/json"})
        _local.session = s
    return s


@contextmanager
def host_slot(url: str):
    host = urlsplit(url).netloc
    with _host_locks_guard:
        sem = _host_locks[host]
    sem.acquire()
    try:
        yield
    finally:
        sem.release()


def get_json(url: str, **kwargs):
    from .models import FetchError

    with host_slot(url):
        try:
            r = session().get(url, timeout=config.HTTP_TIMEOUT, **kwargs)
        except requests.RequestException as exc:
            raise FetchError(f"{type(exc).__name__}: {exc}") from exc
    if r.status_code in (404, 410):
        raise FetchError(f"board not found ({r.status_code})", permanent=True, status=r.status_code)
    if r.status_code >= 400:
        raise FetchError(f"HTTP {r.status_code}", status=r.status_code)
    try:
        return r.json()
    except ValueError as exc:
        raise FetchError(f"non-JSON response from {url}") from exc


def get_lines(url: str, **kwargs):
    """Stream a large text response line by line (Common Crawl index pages)."""
    from .models import FetchError

    with host_slot(url):
        try:
            r = session().get(url, timeout=config.HTTP_TIMEOUT, stream=True, **kwargs)
        except requests.RequestException as exc:
            raise FetchError(f"{type(exc).__name__}: {exc}") from exc
        if r.status_code in (404, 410):
            raise FetchError(f"no captures ({r.status_code})", permanent=True, status=r.status_code)
        if r.status_code >= 400:
            raise FetchError(f"HTTP {r.status_code}", status=r.status_code)
        # Streaming failures surface here, not at request time -- a truncated
        # response must fail this one page, not abort the whole source.
        try:
            for line in r.iter_lines(decode_unicode=True):
                if line:
                    yield line
        except requests.RequestException as exc:
            raise FetchError(f"stream interrupted: {type(exc).__name__}: {exc}") from exc
