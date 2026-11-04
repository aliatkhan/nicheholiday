"""
Builds holidays.csv by reading National Today's monthly holiday pages
(https://nationaltoday.com/<month>-holidays/).

Usage:
    python scrape_holidays.py                 # this month + next month
    python scrape_holidays.py --all           # all 12 months
    python scrape_holidays.py --months 11 12  # specific months
    python scrape_holidays.py --from-file page.html --month 11   # parse a saved page (for testing)

The CSV is merged, not overwritten: re-scraping a month replaces only that
month's rows, so older months stay put.
"""

import argparse
import csv
import calendar
import datetime as dt
import os
import re
import sys
import time
from collections import defaultdict
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://nationaltoday.com/"
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "holidays.csv")
FIELDS = ["date", "name", "category", "type", "url"]
USER_AGENT = "niche-holiday-email/1.0 (personal daily reminder, one request per month page)"
MONTHS = [m.lower() for m in calendar.month_name[1:]]  # "january" ... "december"
WEEKDAYS = list(calendar.day_name)                       # "Monday" ... "Sunday"

DAY_LINK = re.compile(r"/([a-z]+)-(\d{1,2})-holidays/?$")


def norm(href: str) -> str:
    """Absolute URL with a trailing slash, no query string or fragment."""
    u = urlparse(urljoin(BASE, href))
    path = u.path if u.path.endswith("/") else u.path + "/"
    return f"{u.scheme}://{u.netloc}{path}"


def is_nationaltoday(url: str) -> bool:
    return urlparse(url).netloc.endswith("nationaltoday.com")


def looks_like_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://")


def classify(name: str, url: str) -> str:
    """'day', 'week' or 'month' so the email can skip ongoing observances."""
    slug = urlparse(url).path.strip("/").lower()
    low = name.lower()
    if slug.endswith("-month") or low.endswith(" month") or low.startswith("no-shave"):
        return "month"
    if slug.endswith("-week") or low.endswith(" week"):
        return "week"
    return "day"


def weekday_near(a) -> str | None:
    """Find the weekday printed next to a date header like 'Nov 4 Wednesday'."""
    texts = []
    sib = a.next_sibling
    for _ in range(3):
        if sib is None:
            break
        texts.append(sib.get_text(" ", strip=True) if hasattr(sib, "get_text") else str(sib))
        sib = sib.next_sibling
    if a.parent is not None:
        texts.append(a.parent.get_text(" ", strip=True)[:60])
    blob = " ".join(texts)
    for wd in WEEKDAYS:
        if wd in blob:
            return wd
    return None


def pick_year(month: int, day: int, weekday: str | None, today: dt.date) -> int:
    """National Today shows one specific year. Use the printed weekday to work out which."""
    candidates = [today.year - 1, today.year, today.year + 1]
    if weekday:
        for y in candidates[1:] + candidates[:1]:  # prefer this year, then next, then last
            try:
                if calendar.day_name[dt.date(y, month, day).weekday()] == weekday:
                    return y
            except ValueError:  # Feb 29
                continue
    # No weekday found: assume the page shows the upcoming instance of that month.
    return today.year + 1 if month < today.month else today.year


def parse_month_page(html: str, month: int, today: dt.date | None = None) -> list[dict]:
    today = today or dt.date.today()
    month_name = MONTHS[month - 1]
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.find_all("a", href=True)

    # Anything linked before the first date header is site navigation. Footers
    # usually repeat it, so we ignore those links everywhere.
    nav = set()
    first_day_idx = None
    for i, a in enumerate(anchors):
        m = DAY_LINK.search(norm(a["href"]))
        if m and m.group(1) == month_name:
            first_day_idx = i
            break
        nav.add(norm(a["href"]))
    if first_day_idx is None:
        raise RuntimeError(f"No date headers found on the {month_name} page. The site layout may have changed.")

    rows = _strategy_paired_links(anchors[first_day_idx:], month, month_name, nav, today)
    if len(rows) < 20:
        # Fallback if the page no longer wraps each holiday in an image link + name link.
        rows = _strategy_unique_links(anchors[first_day_idx:], month, month_name, nav, today)
    return rows


def _walk(anchors, month, month_name, today):
    """Yield (date, anchor, url, text) for every link under a date header."""
    current = None
    for a in anchors:
        url = norm(a["href"])
        m = DAY_LINK.search(url)
        if m:
            if m.group(1) != month_name:
                current = None  # a link to another month's day means we left the list
                continue
            d = int(m.group(2))
            year = pick_year(month, d, weekday_near(a), today)
            try:
                current = dt.date(year, month, d)
            except ValueError:
                current = None
            yield ("HEADER", None, url, "")
            continue
        if current is None or not is_nationaltoday(url):
            continue
        yield (current, a, url, a.get_text(" ", strip=True))


def _strategy_paired_links(anchors, month, month_name, nav, today):
    """Each holiday on the page is an image link followed by a name link to the same URL,
    then a category link (e.g. 'Food & Beverage' -> /food-beverage-holidays/)."""
    rows, seen = [], set()
    prev_url, prev_text, waiting_for_category = None, "", None
    for date, a, url, text in _walk(anchors, month, month_name, today):
        if date == "HEADER":
            prev_url, prev_text, waiting_for_category = None, "", None
            continue
        # Category pages are also in the site menu, so check for one before the nav filter.
        if waiting_for_category is not None and url.endswith("-holidays/") and text:
            waiting_for_category["category"] = text
            waiting_for_category = None
            prev_url, prev_text = url, text
            continue
        if url in nav:
            prev_url, prev_text = url, text
            continue
        if url == prev_url:
            name = text if text and not looks_like_url(text) else prev_text
            if name and not looks_like_url(name) and (date, url) not in seen:
                seen.add((date, url))
                row = {"date": date.isoformat(), "name": name, "category": "",
                       "type": classify(name, url), "url": url}
                rows.append(row)
                waiting_for_category = row
            prev_url, prev_text = None, ""
            continue
        prev_url, prev_text = url, text
    return rows


def _strategy_unique_links(anchors, month, month_name, nav, today):
    """Fallback: holiday pages are linked under exactly one date, while category
    and tag pages (/american/, /food-holidays/) show up under many dates."""
    dates_per_url = defaultdict(set)
    first_seen = {}
    for date, a, url, text in _walk(anchors, month, month_name, today):
        if date == "HEADER" or url in nav or url.endswith("-holidays/"):
            continue
        dates_per_url[url].add(date)
        # A holiday's name link leads its row; tag links come after the category.
        leads_row = a.parent is None or a.parent.find("a", href=True) is a or \
            norm(a.parent.find("a", href=True)["href"]) == url
        if text and not looks_like_url(text) and leads_row:
            first_seen.setdefault(url, (date, text))
    rows = []
    for url, (date, name) in first_seen.items():
        if len(dates_per_url[url]) == 1:
            rows.append({"date": date.isoformat(), "name": name, "category": "",
                         "type": classify(name, url), "url": url})
    return rows


def fetch_month(month: int, session: requests.Session) -> str:
    url = f"{BASE}{MONTHS[month - 1]}-holidays/"
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def load_csv() -> list[dict]:
    if not os.path.exists(CSV_PATH):
        return []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_csv(rows: list[dict]) -> None:
    rows.sort(key=lambda r: (r["date"], r["name"].lower()))
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def merge(existing: list[dict], new_rows: list[dict], month: int) -> list[dict]:
    """Replace rows for the scraped month/year(s), keep everything else."""
    replaced = {r["date"][:7] for r in new_rows}  # e.g. {"2026-11"}
    kept = [r for r in existing if r["date"][:7] not in replaced]
    return kept + new_rows


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--all", action="store_true", help="scrape all 12 months")
    p.add_argument("--months", type=int, nargs="*", help="month numbers to scrape, e.g. 11 12")
    p.add_argument("--from-file", help="parse a saved HTML file instead of downloading")
    p.add_argument("--month", type=int, help="month number for --from-file")
    args = p.parse_args()

    today = dt.date.today()
    rows = load_csv()

    if args.from_file:
        if not args.month:
            p.error("--from-file needs --month")
        with open(args.from_file, encoding="utf-8") as f:
            new = parse_month_page(f.read(), args.month, today)
        print(f"{MONTHS[args.month - 1].title()}: {len(new)} entries")
        save_csv(merge(rows, new, args.month))
        return 0

    if args.all:
        months = list(range(1, 13))
    elif args.months:
        months = args.months
    else:
        months = [today.month, today.month % 12 + 1]

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    failures = 0
    for i, m in enumerate(months):
        if i:
            time.sleep(3)  # be polite
        try:
            new = parse_month_page(fetch_month(m, session), m, today)
        except Exception as e:  # keep going so one bad month doesn't wipe the rest
            print(f"{MONTHS[m - 1].title()}: FAILED ({e})", file=sys.stderr)
            failures += 1
            continue
        if len(new) < 50:
            print(f"{MONTHS[m - 1].title()}: only {len(new)} entries, skipping so we don't save a broken scrape",
                  file=sys.stderr)
            failures += 1
            continue
        print(f"{MONTHS[m - 1].title()}: {len(new)} entries")
        rows = merge(rows, new, m)

    save_csv(rows)
    print(f"holidays.csv now has {len(rows)} rows")
    return 1 if failures == len(months) else 0


if __name__ == "__main__":
    sys.exit(main())
