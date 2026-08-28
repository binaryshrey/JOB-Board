"""Router tests use URLs observed in real data, not invented ones."""
from jobboard.core.urls import parse, extract_all

CASES = [
    # (url, expected ats, expected slug, expected external_id)
    ("https://jobs.ashbyhq.com/ramp/34413f8d-26bf-4bbc-8ade-eb309a0e2245",
     "ashby", "ramp", "34413f8d-26bf-4bbc-8ade-eb309a0e2245"),
    ("https://jobs.ashbyhq.com/mechanize/1ef28bb2-6251-4da6-a590-a4a7606368cb/application",
     "ashby", "mechanize", "1ef28bb2-6251-4da6-a590-a4a7606368cb"),
    # observed in Common Crawl: tracking params must not leak into the slug
    ("https://jobs.ashbyhq.com/0g/d35c9785-1912-4c23-8d09-dbbe353d4733?utm_source=Longhash+job+board",
     "ashby", "0g", "d35c9785-1912-4c23-8d09-dbbe353d4733"),
    ("https://jobs.ashbyhq.com/Ramp", "ashby", "ramp", None),          # case-insensitive
    ("https://jobs.ashbyhq.com/zip/", "ashby", "zip", None),
    ("https://job-boards.greenhouse.io/trueanomalyinc/jobs/4501234",
     "greenhouse", "trueanomalyinc", "4501234"),
    ("https://boards.greenhouse.io/embed/job_board?for=stripe", "greenhouse", "stripe", None),
    ("https://jobs.lever.co/palantir/ac978161-6f46-4f6b-ad9e-a258e642751c",
     "lever", "palantir", "ac978161-6f46-4f6b-ad9e-a258e642751c"),
    ("https://jobs.lever.co/palantir/ac978161-6f46-4f6b-ad9e-a258e642751c/apply",
     "lever", "palantir", "ac978161-6f46-4f6b-ad9e-a258e642751c"),
    ("https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/x",
     "workday", "nvidia.wd5/nvidiaexternalcareersite", None),
    ("https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs",
     "workday", "nvidia.wd5/nvidiaexternalcareersite", None),
    ("https://apply.workable.com/acmeco/j/ABC123/", "workable", "acmeco", "ABC123"),
    ("https://someco.recruitee.com/o/engineer", "recruitee", "someco", None),
]

REJECT = [
    "https://jobs.ashbyhq.com/",
    "https://jobs.ashbyhq.com/meeting/abc",       # robots-disallowed app route
    "https://jobs.ashbyhq.com/api/whatever",
    "https://example.com/careers",
    "https://stripe.com/jobs/search?gh_jid=7532733",   # no slug recoverable
    "https://www.recruitee.com/pricing",
    "not a url at all",
]


def test_parses_real_urls():
    for url, ats, slug, ext in CASES:
        got = parse(url)
        assert got is not None, f"failed to parse {url}"
        assert (got.ats, got.slug) == (ats, slug), f"{url} -> {got}"
        assert got.external_id == ext, f"{url} -> {got.external_id!r} != {ext!r}"


def test_rejects_non_boards():
    for url in REJECT:
        assert parse(url) is None, f"should not have parsed {url}"


def test_extract_from_text_dedupes():
    text = (
        "we use https://jobs.ashbyhq.com/ramp/abc and also "
        "<a href='https://jobs.ashbyhq.com/ramp'>x</a> plus "
        "https://jobs.lever.co/palantir)."
    )
    refs = extract_all(text)
    assert {(r.ats, r.slug) for r in refs} == {("ashby", "ramp"), ("lever", "palantir")}


def test_extracts_from_html_escaped_text():
    """HN serves comment bodies with &#x2F; for '/'; regressing this silently
    drops ~200 boards per page, so it is pinned."""
    hn = ('due to it `<a href="https:&#x2F;&#x2F;jobs.ashbyhq.com&#x2F;permitflow">'
          'link</a>` and &#x2F;&#x2F;jobs.lever.co&#x2F;palantir too')
    refs = extract_all(hn)
    assert ("ashby", "permitflow") in {(r.ats, r.slug) for r in refs}
