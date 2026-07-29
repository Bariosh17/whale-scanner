# Whale Scanner — Web App

A small Flask dashboard: unusual volume (Yahoo Finance), insider Form 4 filings
(SEC EDGAR), and a congress-trades panel (needs a paid API key, see `scanner.py`).

## Run locally

```
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000

## Deploy with your own domain (Render — free tier)

1. Push this folder to a GitHub repo.
2. Go to render.com → New → Web Service → connect the repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Deploy. Render gives you a URL like `whale-scanner.onrender.com`.
6. In Render's dashboard: Settings → Custom Domain → add your domain
   (e.g. `scanner.yourdomain.com`).
7. In your domain registrar's DNS settings, add the CNAME record Render
   shows you, pointing your domain/subdomain at the Render URL.
8. DNS can take a few minutes to a few hours to propagate.

Railway and PythonAnywhere work the same way — connect repo, set start
command to `gunicorn app:app`, then add a custom domain via CNAME.

## Notes

- Data refreshes at most every 5 minutes (in-memory cache in `app.py`) to
  avoid hammering Yahoo Finance / SEC with requests on every page load.
- The watchlist lives in `scanner.py` (`DEFAULT_WATCHLIST`) — edit it there.
- Congress trades panel is inactive until you add a paid API key
  (EODHD is the cheapest option as of mid-2026) to `EODHD_API_KEY` in
  `scanner.py`.
- Unusual volume needs a free `TWELVE_DATA_API_KEY` environment variable
  (twelvedata.com — 800 free calls/day).
- Unusual options (calls/puts) needs a `MARKETDATA_API_KEY` environment
  variable (marketdata.app — free 30-day trial, no card required). Each
  request is filtered to ~20 near-the-money strikes on the nearest ~30-day
  expiration to conserve credits.
- SEC requires a descriptive User-Agent on requests — already set in
  `scanner.py`, but update the contact email if you plan to run this
  regularly, per SEC's fair-access guidelines.
- **Never commit API keys to GitHub.** Always set them as environment
  variables in Render's dashboard (Settings → Environment), not in the code.
