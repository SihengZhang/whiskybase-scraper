"""Extract the downloaded Whiskybase sitemaps into a single CSV.

Reads every index/sitemaps/whiskies-*.xml and writes index/whiskies.csv with columns:

    ID              - whisky id parsed from the page URL (/whiskies/whisky/{ID}/...)
    URL             - the page <loc>
    last modified   - <lastmod>
    image asset URL - the <image><loc> (bottle photo on static.whiskybase.com)
    image caption   - the <image><caption>

`changefreq` and `priority` are intentionally ignored. Stdlib only — run with:
    python index/extract_to_csv.py
"""

from __future__ import annotations

import csv
import glob
import os
import re
import xml.etree.ElementTree as ET

SITEMAP_DIR = "index/sitemaps"
OUT_CSV = "index/whiskies.csv"
ID_RE = re.compile(r"/whiskies/whisky/(\d+)")


def _local(tag: str) -> str:
    """Namespace-stripped tag name ('{ns}loc' -> 'loc')."""
    return tag.rsplit("}", 1)[-1]


def _sitemap_files() -> list[str]:
    files = glob.glob(os.path.join(SITEMAP_DIR, "whiskies-*.xml"))
    return sorted(files, key=lambda p: int(re.search(r"whiskies-(\d+)\.xml", p).group(1)))


def main() -> None:
    files = _sitemap_files()
    if not files:
        raise SystemExit(f"No sitemaps found in {SITEMAP_DIR}/ — run download_sitemaps.py first.")

    rows = 0
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ID", "URL", "last modified", "image asset URL", "image caption"])
        for path in files:
            try:
                root = ET.parse(path).getroot()
            except ET.ParseError as exc:
                print(f"[skip] {path}: parse error {exc}")
                continue
            for url_el in root:
                if _local(url_el.tag) != "url":
                    continue
                page_url = last_mod = image_url = caption = ""
                for child in url_el:
                    name = _local(child.tag)
                    if name == "loc" and not page_url:  # page loc (direct child of <url>)
                        page_url = (child.text or "").strip()
                    elif name == "lastmod":
                        last_mod = (child.text or "").strip()
                    elif name == "image":  # nested <image><loc>/<caption>
                        for img_child in child:
                            iname = _local(img_child.tag)
                            if iname == "loc":
                                image_url = (img_child.text or "").strip()
                            elif iname == "caption":
                                caption = (img_child.text or "").strip()
                m = ID_RE.search(page_url)
                if not m:
                    continue
                writer.writerow([int(m.group(1)), page_url, last_mod, image_url, caption])
                rows += 1
            print(f"[done] {os.path.basename(path)} (running total: {rows} rows)")

    print(f"\nWrote {rows} rows to {OUT_CSV}")


if __name__ == "__main__":
    main()
