# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An **authorized** research crawler for whiskybase.com. The site owner approved the crawl on the
condition that `robots.txt` is honoured (`Crawl-delay: 5`). This is not evasion — keep the polite
posture in all code: pace requests ≥5s, be resumable, identify the crawler in the User-Agent.

## Commands

Scripts are stdlib-only except `download_sitemaps.py`, which needs `curl_cffi`. There is no
requirements file or test suite yet.

```bash
pip install curl_cffi                 # only dependency, for the sitemap downloader
python index/download_sitemaps.py     # step 1: fetch whiskies-1..290.xml into index/sitemaps/
python index/extract_to_csv.py        # step 2: flatten sitemaps -> index/whiskies.csv
```

Run both from the **repo root** — paths in the scripts are relative to it.

## Architecture

The pipeline is **sitemap-driven ID discovery**, not blind `1..N` iteration:

1. **`index/download_sitemaps.py`** — downloads the 290 `whiskies-{n}.xml` sitemaps. Polite +
   resumable by design: skips files already on disk (and skips the delay when no request was made),
   retries transient failures with backoff, writes atomically via a `.part` temp file. Uses
   `curl_cffi` with `impersonate="chrome"` because the host is behind Cloudflare and rejects plain
   HTTP clients.
2. **`index/extract_to_csv.py`** — parses every sitemap and emits `index/whiskies.csv` with columns
   `ID, URL, last modified, image asset URL, image caption`. ID is parsed from the page URL
   (`/whiskies/whisky/{ID}/...`). Namespace-agnostic (`_local()` strips XML namespaces).

The resulting `whiskies.csv` (~290K rows) is the work-list for a future detail-page scraper, which
does not exist yet.

## Client strategy (Cloudflare)

- **Primary:** `curl_cffi` with Chrome TLS impersonation.
- **Fallback:** Playwright/Chromium (not yet in the repo).
- Owner-side WAF "Skip" allowlist (IP + secret header) is available as a lever if datacenter-IP
  challenges persist.

## Data scope (when building the detail-page scraper)

**In scope:** detail-page spec fields + rating; **all reviews with community data** (reviewer user
id, level, rating) + nose/taste/finish/text/date; market **average shop price only**; all photos
per whisky at highest resolution.

**Explicitly out of scope — do not add:** wishlist/collection data, shop/auction links.

Parser selectors for rating/reviews/market are best-effort pending a live-HTML spike from the deploy
host; mark unverified selectors with `# SPIKE`.
