"""
scanner.py — data-fetching functions for Whale Scanner.
Same logic as the original CLI script, refactored for use by a Flask app.
"""

import statistics
from datetime import datetime, timedelta

import requests

SEC_HEADERS = {
    "User-Agent": "WhaleScanner research-tool contact@example.com"
}

DEFAULT_WATCHLIST = ["AAPL", "TSLA", "NVDA", "AMD", "META", "MSFT", "GOOGL", "AMZN"]

EODHD_API_KEY = None  # add a key here to activate congress trade tracking


def scan_unusual_volume(tickers, lookback_days=20, volume_multiple=2.5):
    import yfinance as yf

    results = []
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period=f"{lookback_days + 5}d")
            if len(hist) < lookback_days + 1:
                continue

            recent = hist.iloc[-1]
            baseline = hist["Volume"].iloc[-(lookback_days + 1):-1]
            avg_volume = statistics.mean(baseline)
            if avg_volume == 0:
                continue

            ratio = recent["Volume"] / avg_volume
            price_change_pct = (recent["Close"] - recent["Open"]) / recent["Open"] * 100

            results.append({
                "ticker": ticker,
                "volume": int(recent["Volume"]),
                "avg_volume": int(avg_volume),
                "ratio": round(ratio, 2),
                "price": round(float(recent["Close"]), 2),
                "day_change_pct": round(float(price_change_pct), 2),
                "unusual": ratio >= volume_multiple,
            })
        except Exception as e:
            results.append({"ticker": ticker, "error": str(e)})

    return sorted(
        [r for r in results if "error" not in r],
        key=lambda r: r["ratio"],
        reverse=True,
    )


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
