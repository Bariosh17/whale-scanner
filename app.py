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

CACHE_SECONDS = 900  # refresh underlying data at most every 15 minutes
                      # (bigger watchlist = more API credits per refresh)
_cache = {"timestamp": 0, "data": None}


def get_report_data():
    now = time.time()
    if _cache["data"] is not None and (now - _cache["timestamp"]) < CACHE_SECONDS:
        return _cache["data"]

    watchlist = scanner.DEFAULT_WATCHLIST

    volume_data = scanner.scan_unusual_volume(watchlist)[:20]
    options_data = scanner.scan_unusual_options(watchlist)[:20]

    insider_filings = []
    for ticker in watchlist[:4]:  # keep SEC calls light
        insider_filings.extend(scanner.get_recent_insider_filings(ticker))

    congress = scanner.get_congress_trades()
    earnings_data = scanner.get_upcoming_earnings(watchlist)

    data = {
        "generated_at": datetime.now().strftime("%b %d, %Y — %H:%M"),
        "watchlist": watchlist,
        "volume": volume_data,
        "volume_key_missing": not bool(scanner.TWELVE_DATA_API_KEY),
        "options": options_data,
        "options_key_missing": not bool(scanner.MARKETDATA_API_KEY),
        "insider": insider_filings,
        "congress": congress,
        "earnings": earnings_data,
    }

    _cache["data"] = data
    _cache["timestamp"] = now
    return data


@app.route("/")
def index():
    data = get_report_data()
    return render_template("index.html", data=data)


@app.route("/api/data")
def api_data():
    return jsonify(get_report_data())


@app.route("/api/refresh")
def api_refresh():
    _cache["timestamp"] = 0
    return jsonify(get_report_data())


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
