#!/usr/bin/env python3
"""
Job scraper for architecture firms.

Given a text file with firm home‑page URLs (one per line), the script:

1. Finds pages that look like “Careers”, “Jobs”, etc.
2. Searches those pages for job links and titles.
3. Saves results to openings.csv    firm_url,opening_title,job_link
"""

import concurrent.futures
import csv
import re
import sys
import urllib.parse
from pathlib import Path
from typing import List, Dict, Any

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0"}
# words that hint at jobs
KEYWORDS = [
    "career", "careers", "job", "jobs", "vacancy", "vacancies",
    "join us", "work with us", "opportunities", "employment",
]
# simple pattern that looks like a job title
TITLE_RE = re.compile(r"\b(architect|designer|manager|coordinator|intern|assistant|director|drafter)\b",
                      re.IGNORECASE)


def fetch(url: str, timeout: int = 10) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception:
        return None


def find_career_pages(root_url: str, html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []

    for a in soup.find_all("a", href=True):
        text = (a.get_text() or "").lower()
        href = a["href"].lower()
        if any(kw in text or kw in href for kw in KEYWORDS):
            full = urllib.parse.urljoin(root_url, a["href"])
            links.append(full)

    # drop duplicates while keeping order
    seen = set()
    clean = []
    for link in links:
        if link not in seen:
            seen.add(link)
            clean.append(link)
    return clean


def extract_openings(career_url: str) -> List[Dict[str, str]]:
    """
    From a careers page, try to pull individual job links + titles.
    Fallback: if we can’t find links, use the page title as one opening.
    """
    html = fetch(career_url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    # first: look for links that seem like individual jobs
    for a in soup.find_all("a", href=True):
        text = (a.get_text() or "").strip()
        if len(text) > 4 and TITLE_RE.search(text):
            job_link = urllib.parse.urljoin(career_url, a["href"])
            jobs.append({"opening_title": text, "job_link": job_link})

    # if none found, use H1/H2 or the <title> tag as a guess
    if not jobs:
        heading = soup.find(["h1", "h2"])
        guess = heading.get_text(strip=True) if heading else soup.title.string if soup.title else ""
        if guess:
            jobs.append({"opening_title": guess, "job_link": career_url})

    return jobs


def process_firm(url: str) -> List[Dict[str, str]]:
    root_html = fetch(url)
    if not root_html:
        return []

    career_pages = find_career_pages(url, root_html) or [url]
    all_jobs = []

    for page in career_pages:
        jobs = extract_openings(page)
        for job in jobs:
            all_jobs.append({
                "firm_url": url,
                "opening_title": job["opening_title"],
                "job_link": job["job_link"],
            })

    return all_jobs


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scraper.py firms.txt")
        sys.exit(1)

    list_file = Path(sys.argv[1])
    if not list_file.is_file():
        print(f"No such file: {list_file}")
        sys.exit(1)

    firms = [l.strip() for l in list_file.read_text(encoding="utf-8").splitlines() if l.strip()]

    # scrape in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        results = ex.map(process_firm, firms)

    # flatten
    rows = [row for firm_rows in results for row in firm_rows]

    if not rows:
        print("No openings found.")
        return

    outfile = Path("openings.csv")
    with outfile.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["firm_url", "opening_title", "job_link"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved {len(rows)} openings to {outfile}")


if __name__ == "__main__":
    main()
