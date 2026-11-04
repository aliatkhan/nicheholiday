# Niche Holiday Email

Every morning this sends you (and your friends) an email with today's niche holidays, like National Sandwich Day or National Candy Day. It runs for free on GitHub Actions, so your computer doesn't need to be on.

## How it works

- `scrape_holidays.py` reads the monthly holiday pages on nationaltoday.com and saves them to `holidays.csv`. This is your "API".
- `send_email.py` looks up today's date in `holidays.csv` and emails the list through Gmail.
- `.github/workflows/refresh-holidays.yml` re-scrapes on the 25th of every month (this month plus next month) and commits the updated CSV.
- `.github/workflows/daily-email.yml` sends the email every morning around 7am Central.

## Setup (about 10 minutes)

### 1. Make the repo
1. On GitHub, click **New repository**. Name it something like `niche-holidays` and set it to **Private** (this keeps your friends' emails and the holiday list out of public view).
2. Click **uploading an existing file** and drag in everything from this folder, including the `.github` folder.
   - On a Mac, `.github` is hidden. Press `Cmd + Shift + .` in Finder to show it.
3. Commit.

### 2. Get a Gmail app password
Google won't let scripts log in with your normal password, so you make a separate one just for this.
1. Turn on 2-Step Verification for the Gmail account if it isn't already: https://myaccount.google.com/security
2. Go to https://myaccount.google.com/apppasswords, name it "Holiday email", and copy the 16-character password.

Tip: you can use a fresh Gmail account just for this so the emails come from something like `nicheholidays.daily@gmail.com` instead of your personal address.

### 3. Add your secrets
In the repo, go to **Settings > Secrets and variables > Actions > New repository secret** and add three:

| Name | Value |
|---|---|
| `GMAIL_ADDRESS` | the Gmail address that sends the email |
| `GMAIL_APP_PASSWORD` | the 16-character app password (spaces are fine) |
| `RECIPIENTS` | everyone who gets it, separated by commas: `you@gmail.com, friend1@gmail.com, friend2@gmail.com` |

Everyone is BCC'd, so friends won't see each other's addresses.

### 4. Fill the CSV
Go to the **Actions** tab, click **Refresh holidays**, then **Run workflow** (leave "Scrape all 12 months" checked). After a minute, `holidays.csv` in the repo should have a few thousand rows.

### 5. Send a test email
In **Actions**, click **Daily holiday email**, then **Run workflow**. Check your inbox (and spam the first time).

That's it. It will now run on its own every morning.

## Changing things

- **Add or remove friends:** edit the `RECIPIENTS` secret.
- **Change the send time:** edit the `cron` line in `daily-email.yml`. It's in UTC: `47 12 * * *` is 6:47am Central in winter and 7:47am in summer. https://crontab.guru helps.
- **Skip certain kinds of holidays:** in `daily-email.yml`, set `SKIP_CATEGORIES`, for example `"Religious,Federal,Cultural"` to leave out official and religious holidays and keep only the fun ones.
- **Include weeks and months** (like "Polar Bear Week") on the day they start: set `INCLUDE_ONGOING: "true"`.
- **Add your own holidays:** open `holidays.csv` on GitHub, click the pencil, and add a line like `2026-12-12,My Friend's Birthday Day,Fun,day,`. Note the monthly refresh replaces that month's rows when it re-scrapes, so add custom ones after the 25th of the month before, or ask to have a separate `custom_holidays.csv` added.

## If something breaks

- **No email arrived:** open the **Actions** tab and click the latest run of "Daily holiday email" to see the error. A login error almost always means the app password or Gmail address secret is off.
- **Refresh holidays failed or saved very few rows:** nationaltoday.com probably changed its page layout. The scraper refuses to save a month with fewer than 50 entries, so your existing CSV stays intact and the emails keep working from it while the scraper gets fixed.
- **Scheduled runs stopped:** GitHub pauses schedules in repos with no activity for 60 days. The monthly CSV commit normally counts as activity, but if you see a banner in the Actions tab, click **Enable workflow**.

## Running it on your own computer (optional)

```bash
pip install -r requirements.txt
python scrape_holidays.py --all
python send_email.py --dry-run                    # prints today's email and saves preview.html
python send_email.py --dry-run --date 2026-11-04  # preview any date
```
