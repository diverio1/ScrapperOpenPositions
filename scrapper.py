#!/usr/bin/env python3
"""
Job scraper for architecture firms.

Given a text file that lists firm home‑page URLs (one per line),
the program prints a line for each firm telling you whether any
openings were found and, when possible, the page that mentions them.
"""

import concurrent.futures
import re
import sys
import urllib.parse
from pathlib import Path
from typing import List, Dict, Any

import requests
from bs4 import BeautifulSoup


HEADERS = {"User-Agent": "Mozilla/5.0"}
KEYWORDS = [
    "career",
    "careers",
    "job",
    "jobs",
    "vacancy",
    "vacancies",
    "join us",
    "work with us",
    "opportunities",
    "employment",
]


def fetch(url: str, timeout: int = 10) -> str | None:
    """Download a page and return its HTML, or None on error."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None


def find_job_pages(root_url: str, html: str) -> List[str]:
    """
    Look for links on the root page whose text or href
    contains a job‑related keyword.
    """
    soup = BeautifulSoup(html, "html.parser")
    links: List[str] = []

    for a in soup.find_all("a", href=True):
        text = (a.get_text() or "").lower()
        href = a["href"].lower()
        for kw in KEYWORDS:
            if kw in text or kw in href:
                full = urllib.parse.urljoin(root_url, a["href"])
                links.append(full)
                break

    # Remove duplicates while keeping order
    seen: set[str] = set()
    clean: List[str] = []
    for link in links:
        if link not in seen:
            seen.add(link)
            clean.append(link)
    return clean


def page_has_jobs(url: str) -> bool:
    """Return True if any keyword is present in the page body."""
    html = fetch(url)
    if not html:
        return False
    text = html.lower()
    return any(kw in text for kw in KEYWORDS)


def check_firm(url: str) -> Dict[str, Any]:
    """Scan one firm and report job status."""
    root_html = fetch(url)
    if not root_html:
        return {"firm": url, "jobs": False, "note": "could not reach site"}

    links = find_job_pages(url, root_html)
    pages_to_scan = links or [url]

    job_pages = [p for p in pages_to_scan if page_has_jobs(p)]

    return {
        "firm": url,
        "jobs": bool(job_pages),
        "pages": job_pages,
    }


def scan_all(firm_urls: List[str], workers: int = 8) -> List[Dict[str, Any]]:
    """Run checks in parallel."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(check_firm, firm_urls))


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scraper.py firms.txt")
        sys.exit(1)

    list_file = Path(sys.argv[1])
    if not list_file.is_file():
        print(f"File not found: {list_file}")
        sys.exit(1)

    firms = [l.strip() for l in list_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    results = scan_all(firms)

    for res in results:
        if res["jobs"]:
            pages = ", ".join(res["pages"])
            print(f"{res['firm']}: openings found → {pages}")
        else:
            note = res.get("note", "no openings found")
            print(f"{res['firm']}: {note}")


if __name__ == "__main__":
    main()
