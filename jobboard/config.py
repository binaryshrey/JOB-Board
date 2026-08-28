"""Central config. Every value is overridable by env var."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("JOBBOARD_DATA", ROOT / "data"))
DB_PATH = Path(os.getenv("JOBBOARD_DB", DATA_DIR / "jobboard.db"))
SEEDS_DIR = DATA_DIR / "seeds"
EVENTS_LOG = Path(os.getenv("JOBBOARD_EVENTS_LOG", DATA_DIR / "events.jsonl"))

USER_AGENT = os.getenv(
    "JOBBOARD_UA",
    "jobboard/0.1 (+https://github.com/binaryshrey/JOB-Board) python-requests",
)
HTTP_TIMEOUT = float(os.getenv("JOBBOARD_HTTP_TIMEOUT", "20"))

# Concurrency is capped per ATS host, not globally: each ATS is a single origin
# and we would rather be a well-behaved client than fast.
PER_HOST_CONCURRENCY = int(os.getenv("JOBBOARD_PER_HOST_CONCURRENCY", "4"))
WORKERS = int(os.getenv("JOBBOARD_WORKERS", "12"))

# Poll cadence per tier, in seconds. Boards start at tier 1 and get demoted
# when they go quiet (see reconcile.retier).
TIER_INTERVALS = {
    1: int(os.getenv("JOBBOARD_TIER1", str(60 * 60))),        # hourly
    2: int(os.getenv("JOBBOARD_TIER2", str(6 * 60 * 60))),    # 6h
    3: int(os.getenv("JOBBOARD_TIER3", str(24 * 60 * 60))),   # daily
}
DEFAULT_TIER = 1
# Demote a board to the next tier after this long with no new postings.
QUIET_DEMOTE_AFTER = int(os.getenv("JOBBOARD_QUIET_DEMOTE_AFTER", str(14 * 86400)))

# A posting is only closed after it is absent from this many *successful*
# consecutive polls. Absence from a full-board endpoint is near-authoritative,
# but a truncated response should never mass-close a board.
CLOSE_GRACE_POLLS = int(os.getenv("JOBBOARD_CLOSE_GRACE_POLLS", "2"))
# Safety valve: if a poll returns 0 jobs for a board that had more than this
# many open jobs, treat it as suspect and skip the close pass.
MASS_CLOSE_GUARD = int(os.getenv("JOBBOARD_MASS_CLOSE_GUARD", "5"))

# Exponential backoff on consecutive board failures.
BACKOFF_BASE = int(os.getenv("JOBBOARD_BACKOFF_BASE", "900"))       # 15 min
BACKOFF_MAX = int(os.getenv("JOBBOARD_BACKOFF_MAX", str(24 * 3600)))
# Boards that fail this many times in a row are parked as 'dead'.
DEAD_AFTER_FAILURES = int(os.getenv("JOBBOARD_DEAD_AFTER_FAILURES", "8"))

SIMPLIFY_REPOS = [
    ("SimplifyJobs/New-Grad-Positions", "dev", ".github/scripts/listings.json", "new_grad"),
    ("SimplifyJobs/Summer2027-Internships", "dev", ".github/scripts/listings.json", "internship"),
]
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
