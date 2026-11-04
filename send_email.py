"""
Emails today's niche holidays from holidays.csv.

Settings come from environment variables (GitHub Actions secrets):
    GMAIL_ADDRESS       the Gmail account that sends the email
    GMAIL_APP_PASSWORD  a Google app password for that account (not your normal password)
    RECIPIENTS          comma-separated list of everyone who should get it

Optional:
    TIMEZONE            defaults to America/Chicago
    INCLUDE_ONGOING     "true" to also list weeks and months that start today
    SKIP_CATEGORIES     comma-separated categories to leave out, e.g. "Religious,Federal"
    MAX_HOLIDAYS        cap the list length (default 25)

Test locally without sending:
    python send_email.py --dry-run
    python send_email.py --dry-run --date 2026-11-04
"""

import argparse
import csv
import datetime as dt
import html
import os
import smtplib
import sys
from collections import OrderedDict
from email.message import EmailMessage
from zoneinfo import ZoneInfo

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "holidays.csv")

# Fun, food and quirky days first, serious and official ones last.
CATEGORY_ORDER = ["Food & Beverage", "Fun", "Special Interest", "Animal", "Arts & Entertainment",
                  "Relationship", "Appreciation", "Health", "Cause", "Cultural", "Religious", "Federal"]


def env_list(name: str) -> list[str]:
    return [x.strip() for x in os.environ.get(name, "").split(",") if x.strip()]


def todays_holidays(day: dt.date) -> list[dict]:
    if not os.path.exists(CSV_PATH):
        sys.exit("holidays.csv is missing. Run the 'Refresh holidays' workflow first.")
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["date"] == day.isoformat()]

    if os.environ.get("INCLUDE_ONGOING", "").lower() != "true":
        rows = [r for r in rows if r.get("type", "day") == "day"]
    skip = {c.lower() for c in env_list("SKIP_CATEGORIES")}
    rows = [r for r in rows if r.get("category", "").lower() not in skip]

    def sort_key(r):
        cat = r.get("category", "")
        rank = CATEGORY_ORDER.index(cat) if cat in CATEGORY_ORDER else len(CATEGORY_ORDER)
        national_first = 0 if r["name"].lower().startswith("national ") else 1
        return (rank, national_first, r["name"].lower())

    rows.sort(key=sort_key)
    return rows[: int(os.environ.get("MAX_HOLIDAYS", "25"))]


def headline(rows: list[dict]) -> str:
    """The one to put in the subject line: the first 'National ... Day' if there is one."""
    for r in rows:
        if r["name"].lower().startswith("national "):
            return r["name"]
    return rows[0]["name"]


def build_message(day: dt.date, rows: list[dict]) -> tuple[str, str, str]:
    pretty_date = f"{day:%A, %B} {day.day}"
    top = headline(rows)
    others = len(rows) - 1
    subject = f"Today is {top}" + (f" (+{others} more)" if others else "")

    grouped: "OrderedDict[str, list[dict]]" = OrderedDict()
    for r in rows:
        grouped.setdefault(r.get("category") or "Other", []).append(r)

    # Plain text version
    lines = [pretty_date, "", f"Today is {top}.", ""]
    if others:
        lines.append("Also today:")
        for r in rows:
            if r["name"] != top:
                lines.append(f"  - {r['name']}")
    lines += ["", "Source: nationaltoday.com"]
    text = "\n".join(lines)

    # HTML version
    parts = [
        '<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;'
        'max-width:520px;margin:0 auto;color:#222;line-height:1.5">',
        f'<p style="color:#888;font-size:13px;margin:0 0 4px">{html.escape(pretty_date)}</p>',
        f'<h1 style="font-size:24px;margin:0 0 20px">Today is {html.escape(top)}</h1>',
    ]
    for cat, items in grouped.items():
        parts.append(f'<p style="font-size:12px;letter-spacing:.06em;text-transform:uppercase;'
                     f'color:#888;margin:18px 0 6px">{html.escape(cat)}</p>')
        parts.append('<ul style="padding-left:18px;margin:0">')
        for r in items:
            parts.append(f'<li style="margin:3px 0"><a href="{html.escape(r["url"])}" '
                         f'style="color:#222">{html.escape(r["name"])}</a></li>')
        parts.append("</ul>")
    parts.append('<p style="color:#aaa;font-size:12px;margin-top:28px">'
                 'Holiday list from nationaltoday.com</p></div>')
    return subject, text, "".join(parts)


def send(subject: str, text: str, html_body: str) -> None:
    sender = os.environ["GMAIL_ADDRESS"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    recipients = env_list("RECIPIENTS") or [sender]

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"Niche Holidays <{sender}>"
    msg["To"] = sender                 # everyone else is BCC'd so friends can't see each other's emails
    msg["Bcc"] = ", ".join(recipients)
    msg.set_content(text)
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)
    print(f"Sent '{subject}' to {len(recipients)} recipient(s)")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="print the email instead of sending it")
    p.add_argument("--date", help="pretend today is YYYY-MM-DD")
    args = p.parse_args()

    tz = ZoneInfo(os.environ.get("TIMEZONE", "America/Chicago"))
    day = dt.date.fromisoformat(args.date) if args.date else dt.datetime.now(tz).date()

    rows = todays_holidays(day)
    if not rows:
        print(f"No holidays found for {day}. Nothing sent.")
        return 0

    subject, text, html_body = build_message(day, rows)
    if args.dry_run:
        print("SUBJECT:", subject)
        print(text)
        out = os.path.join(os.path.dirname(CSV_PATH), "preview.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(html_body)
        print(f"\nHTML preview written to {out}")
        return 0

    send(subject, text, html_body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
