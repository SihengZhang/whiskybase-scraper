"""Download the Whiskybase whisky sitemaps (whiskies-1.xml .. whiskies-N.xml).

N is not hard-coded: it's discovered from the index sitemap (index/sitemaps.xml, fetched if
absent), which lists every whiskies-{n}.xml sub-sitemap.

Polite + resumable: honours the robots Crawl-delay (>=5 s between requests), skips files
already on disk, retries transient failures, and writes atomically. Uses curl_cffi (Chrome
impersonation) because the host is behind Cloudflare and rejects plain HTTP clients.

Run from the repo root:  python index/download_sitemaps.py
"""

from __future__ import annotations

import random
import re
import time
from pathlib import Path

from curl_cffi import requests

INDEX_DIR = Path("index")
OUT_DIR = INDEX_DIR / "sitemaps"
INDEX_FILE = INDEX_DIR / "sitemaps.xml"
INDEX_URL = "https://www.whiskybase.com/sitemaps/sitemaps.xml"
BASE = "https://www.whiskybase.com/sitemaps/whiskies-{n}.xml"
WHISKY_RE = re.compile(r"whiskies-(\d+)\.xml")
FIRST = 1
LAST_FALLBACK = 290  # used only if the index sitemap can't be read
DELAY_SECONDS = 5.5  # base pace; must stay >= robots Crawl-delay: 5 after jitter
DELAY_JITTER = 0.5  # each wait is DELAY_SECONDS +/- this many seconds (uniform)
HEADERS = {"User-Agent": "WhiskybaseResearchCrawler/1.0 (+https://example.org; contact@example.org)"}


def _pace(delay: float = DELAY_SECONDS, jitter: float = DELAY_JITTER) -> None:
    """Sleep delay +/- jitter seconds, clamped to the robots Crawl-delay floor of 5s."""
    time.sleep(max(5.0, delay + random.uniform(-jitter, jitter)))


def _fetch(url: str) -> bytes | None:
    """GET url with retries + backoff. Returns content bytes, or None after exhausting retries."""
    for attempt in range(1, 4):
        try:
            r = requests.get(url, impersonate="chrome", timeout=60, headers=HEADERS)
        except Exception as exc:  # network/timeout
            print(f"[err] {url} attempt {attempt}: {exc}", flush=True)
            time.sleep(10 * attempt)
            continue
        if r.status_code == 200 and r.content:
            return r.content
        print(f"[bad] {url} status={r.status_code} attempt={attempt}", flush=True)
        time.sleep(10 * attempt)
    return None


def _write_atomic(dest: Path, content: bytes) -> None:
    tmp = dest.parent / (dest.name + ".part")
    tmp.write_bytes(content)
    tmp.replace(dest)  # atomic


def discover_last() -> int:
    """Highest whiskies-{n}.xml number listed in the index sitemap.

    Downloads index/sitemaps.xml if it isn't already on disk. Assumes the whisky sub-sitemaps
    are numbered contiguously 1..N. Falls back to LAST_FALLBACK if the index can't be read.
    """
    if not (INDEX_FILE.exists() and INDEX_FILE.stat().st_size > 0):
        content = _fetch(INDEX_URL)
        if content is None:
            print(f"[warn] could not fetch index sitemap; assuming N={LAST_FALLBACK}", flush=True)
            return LAST_FALLBACK
        _write_atomic(INDEX_FILE, content)
        print(f"[ok] {INDEX_FILE.name} {len(content)} bytes", flush=True)
    nums = [int(m) for m in WHISKY_RE.findall(INDEX_FILE.read_text(encoding="utf-8"))]
    if not nums:
        print(f"[warn] no whisky sitemaps in index; assuming N={LAST_FALLBACK}", flush=True)
        return LAST_FALLBACK
    return max(nums)


def download_one(n: int) -> bool:
    dest = OUT_DIR / f"whiskies-{n}.xml"
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[skip] {dest.name} (already downloaded)", flush=True)
        return False  # no network request made -> caller skips the delay
    content = _fetch(BASE.format(n=n))
    if content is None:
        print(f"[FAIL] {dest.name} after retries", flush=True)
        return True  # a request was attempted -> caller still paces
    _write_atomic(dest, content)
    print(f"[ok] {dest.name} {len(content)} bytes", flush=True)
    return True


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    last = discover_last()
    print(f"Index lists whiskies-{FIRST}..{last}.xml", flush=True)
    for n in range(FIRST, last + 1):
        made_request = download_one(n)
        if made_request:
            _pace()  # pace only after an actual network hit
    have = sum(1 for n in range(FIRST, last + 1) if (OUT_DIR / f"whiskies-{n}.xml").exists())
    print(f"DONE: {have}/{last - FIRST + 1} sitemaps present in {OUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
