"""
scanner.py — data-fetching functions for Whale Scanner.
Same logic as the original CLI script, refactored for use by a Flask app.
"""

import os
import statistics
from datetime import datetime, timedelta

import requests

SEC_HEADERS = {
    "User-Agent": "WhaleScanner research-tool contact@example.com"
}

DEFAULT_WATCHLIST = ["AAPL", "TSLA", "NVDA", "AMD", "META", "MSFT", "GOOGL", "AMZN"]

EODHD_API_KEY = None  # add a key here to activate congress trade tracking

# Yahoo Finance (yfinance) blocks/rate-limits requests from cloud server IPs,
# so it fails once deployed even though it works locally. Twelve Data's free
# tier (800 calls/day) is a real API built for server-side use.
# Get a free key at https://twelvedata.com and set it as an environment
# variable called TWELVE_DATA_API_KEY (in Render: Settings > Environment).
TWELVE_DATA_API_KEY = os.environ.get("TWELVE_DATA_API_KEY")


def scan_unusual_volume(tickers, lookback_days=20, volume_multiple=2.5):
    if not TWELVE_DATA_API_KEY:
        return []

    results = []
    for ticker in tickers:
        try:
            url = "https://api.twelvedata.com/time_series"
            params = {
                "symbol": ticker,
                "interval": "1day",
                "outputsize": lookback_days + 5,
                "apikey": TWELVE_DATA_API_KEY,
            }
            resp = requests.get(url, params=params, timeout=10)
            payload = resp.json()

            if payload.get("status") == "error" or "values" not in payload:
                continue

            # Twelve Data returns newest first
            bars = payload["values"]
            if len(bars) < lookback_days + 1:
                continue

            recent = bars[0]
            baseline_volumes = [float(b["volume"]) for b in bars[1:lookback_days + 1]]
            avg_volume = statistics.mean(baseline_volumes)
            if avg_volume == 0:
                continue

            recent_volume = float(recent["volume"])
            recent_open = float(recent["open"])
            recent_close = float(recent["close"])

            ratio = recent_volume / avg_volume
            price_change_pct = (recent_close - recent_open) / recent_open * 100

            results.append({
                "ticker": ticker,
                "volume": int(recent_volume),
                "avg_volume": int(avg_volume),
                "ratio": round(ratio, 2),
                "price": round(recent_close, 2),
                "day_change_pct": round(price_change_pct, 2),
                "unusual": ratio >= volume_multiple,
            })
        except Exception:
            continue

    return sorted(results, key=lambda r: r["ratio"], reverse=True)


_cik_cache = None

def get_cik_for_ticker(ticker):
    global _cik_cache
    if _cik_cache is None:
        url = "https://www.sec.gov/files/company_tickers.json"
        resp = requests.get(url, headers=SEC_HEADERS, timeout=10)
        resp.raise_for_status()
        _cik_cache = resp.json()

    for entry in _cik_cache.values():
        if entry["ticker"].upper() == ticker.upper():
            return str(entry["cik_str"]).zfill(10)
    return None


def get_recent_insider_filings(ticker, days_back=30, limit=5):
    cik = get_cik_for_ticker(ticker)
    if not cik:
        return []

    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    resp = requests.get(url, headers=SEC_HEADERS, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])

    cutoff = datetime.now() - timedelta(days=days_back)
    filings = []
    for form, date, accession in zip(forms, dates, accessions):
        if form != "4":
            continue
        filing_date = datetime.strptime(date, "%Y-%m-%d")
        if filing_date < cutoff:
            continue
        acc_nodash = accession.replace("-", "")
        filing_url = (
            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
            f"{acc_nodash}/{accession}-index.htm"
        )
        filings.append({"ticker": ticker, "date": date, "url": filing_url})
        if len(filings) >= limit:
            break

    return filings


def get_congress_trades(ticker=None, limit=20):
    if not EODHD_API_KEY:
        return {"active": False, "trades": []}

    url = "https://eodhd.com/api/congressional-trades"
    params = {"api_token": EODHD_API_KEY, "limit": limit}
    if ticker:
        params["symbol"] = ticker

    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return {"active": True, "trades": resp.json().get("data", [])}


# ---------------------------------------------------------------------------
# UNUSUAL OPTIONS ACTIVITY (calls vs puts) — Market Data (marketdata.app)
# ---------------------------------------------------------------------------
# Free 30-day trial, real OPRA-sourced data. Get a token at marketdata.app,
# set it as an environment variable called MARKETDATA_API_KEY.
#
# Each contract returned costs 1 credit on a real-time/delayed plan, so this
# deliberately limits each request to ~20 strikes near the money on the
# nearest ~30-day expiration to keep credit usage low.

MARKETDATA_API_KEY = os.environ.get("MARKETDATA_API_KEY")


def scan_unusual_options(tickers, volume_oi_ratio=1.0, min_volume=100):
    if not MARKETDATA_API_KEY:
        return []

    headers = {"Authorization": f"Bearer {MARKETDATA_API_KEY}"}
    results = []

    for ticker in tickers:
        try:
            url = f"https://api.marketdata.app/v1/options/chain/{ticker}/"
            params = {"dte": 30, "range": "all", "strikeLimit": 20}
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            payload = resp.json()

            if payload.get("s") != "ok":
                continue

            for i in range(len(payload.get("optionSymbol", []))):
                volume = payload["volume"][i] or 0
                open_interest = payload["openInterest"][i] or 0

                if volume < min_volume:
                    continue
                if open_interest > 0 and (volume / open_interest) < volume_oi_ratio:
                    continue

                results.append({
                    "ticker": ticker,
                    "side": payload["side"][i],  # "call" or "put"
                    "strike": payload["strike"][i],
                    "dte": payload["dte"][i],
                    "volume": int(volume),
                    "open_interest": int(open_interest),
                    "ratio": round(volume / open_interest, 2) if open_interest else None,
                    "expiration": datetime.fromtimestamp(
                        payload["expiration"][i]
                    ).strftime("%Y-%m-%d"),
                })
        except Exception:
            continue

    return sorted(results, key=lambda r: r["volume"], reverse=True)
