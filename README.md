# What Day Is It?

A one-page site that shows today's niche holiday (National Candy Day, National Sandwich Day...) on a pixel tear-off calendar, with the day's other holidays listed underneath. Visitors can flip to yesterday or tomorrow, and tap any other holiday to put it on the page.

It's hosted free on GitHub Pages and keeps itself up to date.

## How it works

- `index.html` is the whole site. It reads `holidays.csv` and shows the holidays for the visitor's local date. Each holiday gets a pixel picture based on words in its name (candy, pizza, dog, coffee...) or, failing that, its category.
- `scrape_holidays.py` reads the monthly holiday pages on nationaltoday.com and saves them to `holidays.csv`.
- `.github/workflows/site.yml` re-scrapes on the 25th of every month (this month plus next) and republishes the site. It also republishes whenever you push a change.

## Setup (one time)

1. In the repo, go to **Settings > Pages**. Under **Build and deployment > Source**, pick **GitHub Actions**.
2. Go to the **Actions** tab, click **Update site**, then **Run workflow** (leave "Scrape all 12 months" checked).
3. When it finishes, the site is live at **https://aliatkhan.github.io/nicheholiday/**.

## Sharing a specific day

Flipping days changes the address, e.g. `https://aliatkhan.github.io/nicheholiday/?d=2026-11-04`. Send that link and it opens on that day.

## Changing things

- **Add your own holiday:** open `holidays.csv` on GitHub, click the pencil, and add a line like `2026-12-12,Best Friend Appreciation Day,Fun,day,`. The monthly refresh replaces a month's rows when it re-scrapes it, so add custom ones after the 25th of the month before.
- **Change a picture:** the sprites are 12x12 grids of letters near the top of the script in `index.html`. Each letter is a color from `PALETTE`, and `.` is see-through. `KEYWORDS` decides which picture a holiday gets.

## If something breaks

- **The page says the list is still being filled in:** the first "Update site" run hasn't finished, or it failed. Check the Actions tab.
- **The scrape step failed or saved very few rows:** nationaltoday.com probably changed its layout. The scraper refuses to save a month with fewer than 50 entries, so the existing list stays up while it gets fixed.
- **Scheduled runs stopped:** GitHub pauses schedules in repos with no activity for 60 days. If you see a banner in the Actions tab, click **Enable workflow**.

## Running it locally (optional)

```bash
pip install -r requirements.txt
python scrape_holidays.py --all
python -m http.server 8000   # then open http://localhost:8000
```
