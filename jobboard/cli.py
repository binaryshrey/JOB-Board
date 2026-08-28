"""Command line entry point:  python -m jobboard <command>"""
from __future__ import annotations

import argparse
import sys
import time

from . import adapters, config, db, discovery, jobs, registry, validate as validate_mod
from .models import BoardRef


def _fmt(n) -> str:
    return "-" if n is None else f"{n:,}"


# ---------------------------------------------------------------- init -----
def cmd_init(args) -> int:
    conn = db.init_db()
    tables = [r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    print(f"initialized {config.DB_PATH}")
    print("tables:", ", ".join(t for t in tables if not t.startswith("sqlite_")))
    return 0


# ------------------------------------------------------------ discover -----
def cmd_discover(args) -> int:
    conn = db.init_db()
    names = args.source or list(discovery.DEFAULT_ORDER)
    from .discovery.commoncrawl import ALL_HOSTS
    kwargs_for = {
        "commoncrawl": {"crawls": args.crawls,
                        "hosts": ALL_HOSTS if args.all_hosts else None},
    }
    grand = {"boards": 0, "links": 0, "postings": 0}
    for name in names:
        if name not in discovery.SOURCES:
            print(f"! unknown source {name!r}", file=sys.stderr)
            continue
        src = discovery.build(name, **kwargs_for.get(name, {}))
        ok, why = src.available()
        if not ok:
            print(f"~ {name:12} skipped -- {why}", flush=True)
            continue
        t0 = time.time()
        refs: list[BoardRef] = []
        postings = []
        try:
            for ref in src.discover():
                refs.append(ref)
                if ref.posting is not None:
                    postings.append(ref.posting)
                if args.limit and len(refs) >= args.limit:
                    break
        except Exception as exc:
            # A failing source must not kill the run, and whatever it yielded
            # before dying is still worth keeping.
            print(f"! {name:12} failed -- {type(exc).__name__}: {exc}", file=sys.stderr)
            if not refs:
                continue
        if args.dry_run:
            uniq = {(r.ats, r.slug) for r in refs}
            print(f"  {name:12} {len(refs):>7} refs  {len(uniq):>7} unique  "
                  f"{len(postings):>7} postings  ({time.time()-t0:.1f}s)  [dry run]", flush=True)
            continue
        res = registry.add_boards(conn, refs, source=name)
        seeded = jobs.seed(conn, postings, source=name) if postings else 0
        grand["boards"] += res["new_boards"]
        grand["links"] += res["new_links"]
        grand["postings"] += seeded
        print(f"  {name:12} {res['seen']:>7} refs  {res['new_boards']:>7} new boards  "
              f"{seeded:>7} seed postings  ({time.time()-t0:.1f}s)", flush=True)
    if not args.dry_run:
        print(f"\ntotal: {_fmt(grand['boards'])} new boards, "
              f"{_fmt(grand['postings'])} seed postings")
    return 0


# ------------------------------------------------------------ validate -----
def cmd_validate(args) -> int:
    conn = db.connect()
    t0 = time.time()
    res = validate_mod.run(conn, args.ats, limit=args.limit, workers=args.workers,
                           revalidate=args.revalidate_dead)
    if not res.checked:
        print("nothing to validate")
        return 0
    print(f"{res.line()}  in {time.time()-t0:.0f}s")
    live = res.active + res.empty
    print(f"  -> {live:,} live boards ({live/res.checked:.0%} of probed)")
    return 0


# --------------------------------------------------------------- stats -----
def cmd_stats(args) -> int:
    conn = db.connect()
    print("boards by ats/status")
    pollable = set(adapters.supported())
    for r in registry.counts_by_ats(conn):
        mark = " " if r["ats"] in pollable else "*"
        print(f"  {mark}{r['ats']:<16} {r['status']:<12} {_fmt(r['n']):>9}")
    print("  (* = recognized and stored, no adapter yet -- not polled)")

    rows = registry.counts_by_source(conn)
    if rows:
        print("\nboards by discovery source")
        for r in rows:
            print(f"   {r['source']:<16} total {_fmt(r['boards']):>8}   "
                  f"active {_fmt(r['active']):>8}   dead {_fmt(r['dead']):>8}")

    j = conn.execute(
        """SELECT status, COUNT(*) n, COUNT(DISTINCT ats||'/'||slug) boards
           FROM jobs GROUP BY status"""
    ).fetchall()
    if j:
        print("\njobs")
        for r in j:
            print(f"   {r['status']:<16} {_fmt(r['n']):>9} across {_fmt(r['boards'])} boards")
    ev = conn.execute(
        "SELECT type, COUNT(*) n FROM events GROUP BY type ORDER BY n DESC").fetchall()
    if ev:
        print("\nevents")
        for r in ev:
            print(f"   {r['type']:<16} {_fmt(r['n']):>9}")
    return 0


# -------------------------------------------------------------- sources ----
def cmd_sources(args) -> int:
    print(f"{'source':<14}{'auth':<7}{'status'}")
    for name in discovery.DEFAULT_ORDER:
        src = discovery.build(name)
        ok, why = src.available()
        print(f"{name:<14}{'yes' if src.needs_auth else 'no':<7}"
              f"{'ready' if ok else 'unavailable -- ' + why}")
    print(f"\npollable ATSs: {', '.join(adapters.supported())}")
    print(f"stored-only  : {', '.join(adapters.PLANNED)}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="jobboard", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create the database").set_defaults(fn=cmd_init)

    d = sub.add_parser("discover", help="fill the board registry from all sources")
    d.add_argument("-s", "--source", action="append", choices=list(discovery.SOURCES),
                   help="run only this source (repeatable)")
    d.add_argument("--crawls", type=int, default=12,
                   help="how many Common Crawl collections to sweep (default 12 of 127)")
    d.add_argument("--all-hosts", action="store_true",
                   help="sweep every known ATS host, not just Ashby")
    d.add_argument("--limit", type=int, help="stop each source after N refs")
    d.add_argument("--dry-run", action="store_true", help="count without writing")
    d.set_defaults(fn=cmd_discover)

    v = sub.add_parser("validate", help="probe unvalidated boards, settle their status")
    v.add_argument("--ats", default="ashby", help="which ATS to probe (default ashby)")
    v.add_argument("--limit", type=int, help="probe at most N boards")
    v.add_argument("--workers", type=int, help=f"concurrency (default {config.WORKERS})")
    v.add_argument("--revalidate-dead", action="store_true",
                   help="re-probe boards previously marked dead (companies adopt Ashby later)")
    v.set_defaults(fn=cmd_validate)

    sub.add_parser("stats", help="registry and feed summary").set_defaults(fn=cmd_stats)
    sub.add_parser("sources", help="list discovery sources and readiness").set_defaults(fn=cmd_sources)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
