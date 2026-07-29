"""
Whale Scanner — Flask web app.

Run locally:
    pip install -r requirements.txt
    python app.py
Then open http://localhost:5000
"""

import time
from datetime import datetime

from flask import Flask, jsonify, render_template

import scanner

app = Flask(__name__)

# Twelve Data's free tier caps out at 800 calls/day. Volume + earnings scans
# each cost ~1 call per ticker (20 tickers = 20 calls per scan). Earnings
# dates barely change day to day, so they're cached far longer than price
# data to leave room in the daily quota.
VOLUME_CACHE_SECONDS = 60 * 60        # 1 hour  (~20 calls x ~24/day = 480/day)
OPTIONS_CACHE_SECONDS = 60 * 60       # 1 hour  (separate provider/quota)
EARNINGS_CACHE_SECONDS = 24 * 60 * 60  # 1 day   (~20 calls/day)
INSIDER_CACHE_SECONDS = 60 * 60 * 4   # 4 hours (SEC, no quota, just politeness)

_cache = {}  # key -> {"timestamp": float, "data": ...}


def _cached(key, ttl_seconds, fetch_fn):
    now = time.time()
    entry = _cache.get(key)
    if entry is not None and (now - entry["timestamp"]) < ttl_seconds:
        return entry["data"]
    data = fetch_fn()
    _cache[key] = {"timestamp": now, "data": data}
    return data


def get_report_data():
    watchlist = scanner.DEFAULT_WATCHLIST

    volume_data = _cached(
        "volume", VOLUME_CACHE_SECONDS,
        lambda: scanner.scan_unusual_volume(watchlist)[:20],
    )
    options_data = _cached(
        "options", OPTIONS_CACHE_SECONDS,
        lambda: scanner.scan_unusual_options(watchlist)[:20],
    )
    earnings_data = _cached(
        "earnings", EARNINGS_CACHE_SECONDS,
        lambda: scanner.get_upcoming_earnings(),
    )

    def _fetch_insider():
        filings = []
        for ticker in watchlist[:4]:  # keep SEC calls light
            filings.extend(scanner.get_recent_insider_filings(ticker))
        return filings

    insider_filings = _cached("insider", INSIDER_CACHE_SECONDS, _fetch_insider)
    congress = scanner.get_congress_trades()  # no-op / instant until a key is added

    # One-off test: does the free Finnhub key unlock congressional trading?
    # Cached for a day so it only actually calls Finnhub once — check Render
    # logs for a line starting with [congress-finnhub] to see the result.
    _cached("congress_finnhub_test", 24 * 60 * 60,
            lambda: scanner.get_congress_trades_finnhub())

    return {
        "generated_at": datetime.now().strftime("%b %d, %Y — %H:%M"),
        "watchlist": watchlist,
        "volume": volume_data,
        "volume_key_missing": not bool(scanner.TWELVE_DATA_API_KEY),
        "options": options_data,
        "options_key_missing": not bool(scanner.MARKETDATA_API_KEY),
        "insider": insider_filings,
        "congress": congress,
        "earnings": earnings_data,
        "earnings_key_missing": not bool(scanner.FINNHUB_API_KEY),
    }


@app.route("/")
def index():
    data = get_report_data()
    return render_template("index.html", data=data)


@app.route("/api/data")
def api_data():
    return jsonify(get_report_data())


@app.route("/api/refresh")
def api_refresh():
    _cache.clear()
    return jsonify(get_report_data())


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
