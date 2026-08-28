# JOB-Board

An Ashby job aggregator built on a two-tier model: a **registry** of ATS boards,
kept separate from a **feed** of postings.

The split is the whole design. Discovery fills the registry; polling fills the
feed. Neither writes to the other's table, so a noisy discovery source can never
corrupt the job data, and adding a new ATS never means re-running discovery.

```
                weekly                         hourly
  sources ──▶ boards (registry) ──▶ poll ──▶ jobs (feed) ──▶ events
              ats + slug                     ats+slug+external_id
```

## Why discovery is hard

Ashby publishes no sitemap and no enumeration endpoint — `jobs.ashbyhq.com/sitemap.xml`
returns the SPA shell, and `robots.txt` declares nothing. There is no way to ask
"which companies use Ashby?", so every board must be *inferred* from third-party
traces. Completeness is unprovable; the goal is convergence, measured by the
marginal new-board yield of each weekly run.

What makes this tractable: an unknown slug returns a clean `404` and a real one
returns the entire board in a single unauthenticated `GET`. Guessing is cheap,
so discovery sources are tuned for **recall, not precision** — `validate` is the
single place that decides what is real.

## Quick start

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m jobboard init          # create the database
./.venv/bin/python -m jobboard sources       # which sources are ready
./.venv/bin/python -m jobboard discover      # fill the registry
./.venv/bin/python -m jobboard validate      # probe boards, settle status
./.venv/bin/python -m jobboard stats         # what we have
```

## Discovery sources

| Source | Auth | What it reads |
|---|---|---|
| `seedfile` | – | `data/seeds/*.txt`, hand-curated |
| `simplify` | – | SimplifyJobs new-grad + internship `listings.json` (also seeds postings) |
| `hn` | – | Hacker News search via Algolia |
| `hn_hiring` | – | Every "Ask HN: Who is hiring?" thread, read in full |
| `commoncrawl` | – | Common Crawl URL index, N most recent collections |
| `wayback` | – | Wayback Machine CDX (different corpus; rate-limited, so paced) |
| `github` | yes | GitHub code search — borrows `gh auth token`, never stores it |

Sources only ever yield `BoardRef`s. They never validate and never poll.

## Notes that are easy to get wrong

- **Ashby slugs are case-insensitive.** `ramp`, `Ramp` and `RAMP` are one board.
  Slugs are lowercased on parse; skipping this creates duplicate rows that poll
  the same board.
- **HN escapes URLs as HTML entities** (`&#x2F;` for `/`), which silently
  defeats any URL regex. `urls.extract_all` unescapes first — pinned by a test.
- **`content_hash` excludes server timestamps.** Greenhouse bumps `updated_at`
  on no-op republishes; hashing it would mark every job edited on every poll.
- **Rediscovery never resurrects a dead board**, or Common Crawl would revive
  the same dead slugs every month. Only `validate --revalidate-dead` does.
- **Boards for ATSs we cannot poll are still stored.** The URL router recognizes
  Greenhouse, Lever, Workday and others; adding an adapter is a flag flip
  rather than a re-run of discovery.

## Layout

```
jobboard/
  config.py      env-overridable settings
  db.py          schema: boards, board_sources, jobs, events, poll_runs
  models.py      Posting, BoardRef, content_hash
  urls.py        ATS URL router -> (ats, slug, external_id)
  http.py        retrying session, per-host concurrency cap
  registry.py    writes to boards; backoff and tiering
  jobs.py        writes to jobs
  validate.py    probe unvalidated boards
  adapters/      one per ATS (ashby today)
  discovery/     one per source
```
