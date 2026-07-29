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

DEFAULT_WATCHLIST = [
    # mega-cap tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD",
    # index / sector ETFs (highest options volume in the market)
    "SPY", "QQQ", "IWM",
    # popular high-options-volume names
    "PLTR", "COIN", "SOFI", "SNAP", "UBER",
    # large-cap financials / other frequently-active names
    "JPM", "BAC", "DIS", "INTC",
]

# Used to filter the market-wide earnings calendar down to companies people
# actually recognize, instead of every obscure small-cap reporting that week.
POPULAR_TICKERS = {
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA", "AMD", "AVGO",
    "NFLX", "ORCL", "CRM", "ADBE", "INTC", "QCOM", "MU", "CSCO", "IBM", "NOW",
    "SPY", "QQQ", "IWM", "DIA",
    "PLTR", "COIN", "SOFI", "SNAP", "UBER", "LYFT", "SHOP", "PYPL", "SQ", "ABNB",
    "RIVN", "LCID", "F", "GM", "DIS", "NKE", "SBUX", "MCD", "CMG",
    "JPM", "BAC", "WFC", "GS", "MS", "C", "V", "MA", "AXP",
    "XOM", "CVX", "COP", "BA", "CAT", "GE", "LMT", "RTX",
    "WMT", "COST", "TGT", "HD", "LOW",
    "JNJ", "PFE", "UNH", "MRK", "LLY", "ABBV", "CVS",
    "T", "VZ", "TMUS",
    "KO", "PEP", "PG", "MDLZ",
}


# Yahoo Finance (yfinance) blocks/rate-limits requests from cloud server IPs,
# so it fails once deployed even though it works locally. Twelve Data's free
# tier (800 calls/day) is a real API built for server-side use.
# Get a free key at https://twelvedata.com and set it as an environment
# variable called TWELVE_DATA_API_KEY (in Render: Settings > Environment).
TWELVE_DATA_API_KEY = os.environ.get("TWELVE_DATA_API_KEY")

# Miles & Gario's actual holdings, pulled from the "Buy" transaction rows in
# the portfolio export (MSP-Portfolios-2026-07-29.csv). Shares and cost/share
# are exactly as recorded there.
PORTFOLIO_HOLDINGS = [
    {"ticker": "MSFT", "shares": 5.811, "cost_per_share": 430.20},
    {"ticker": "NFLX", "shares": 30.095, "cost_per_share": 83.07},
    {"ticker": "AMZN", "shares": 25.026, "cost_per_share": 199.79},
    {"ticker": "GLD", "shares": 10.427, "cost_per_share": 215.28},
    {"ticker": "IWM", "shares": 11.09, "cost_per_share": 202.88},
    {"ticker": "NVDA", "shares": 37.165, "cost_per_share": 134.54},
    {"ticker": "QQQ", "shares": 6.616, "cost_per_share": 453.38},
    {"ticker": "SPY", "shares": 5.704, "cost_per_share": 525.89},
    {"ticker": "VOO", "shares": 4.568, "cost_per_share": 483.04},
    {"ticker": "VTI", "shares": 8.653, "cost_per_share": 260.02},
    {"ticker": "META", "shares": 2.905, "cost_per_share": 688.39},
    {"ticker": "GOOG", "shares": 5.876, "cost_per_share": 340.35},
    {"ticker": "SMCI", "shares": 67.636, "cost_per_share": 29.57},
    {"ticker": "SPCX", "shares": 24.636, "cost_per_share": 162.36},
    {"ticker": "RDDT", "shares": 15.501, "cost_per_share": 161.27},
    {"ticker": "OTLK", "shares": 14.576993, "cost_per_share": 1.43},
]


def get_portfolio():
    """
    Live valuation of PORTFOLIO_HOLDINGS: pulls current price per ticker from
    Twelve Data's lightweight /price endpoint (1 credit each) and computes
    cost basis, market value, and gain/loss for each position plus totals.
    """
    if not TWELVE_DATA_API_KEY:
        return {"positions": [], "totals": None}

    positions = []
    for h in PORTFOLIO_HOLDINGS:
        ticker = h["ticker"]
        shares = h["shares"]
        cost_per_share = h["cost_per_share"]
        current_price = None
        try:
            url = "https://api.twelvedata.com/price"
            params = {"symbol": ticker, "apikey": TWELVE_DATA_API_KEY}
            resp = requests.get(url, params=params, timeout=10)
            payload = resp.json()
            if "price" in payload:
                current_price = float(payload["price"])
            else:
                print(f"[portfolio] {ticker} error: {payload}")
        except Exception as e:
            print(f"[portfolio] {ticker} exception: {e}")

        cost_basis = shares * cost_per_share
        if current_price is not None:
            market_value = shares * current_price
            gain_loss = market_value - cost_basis
            gain_loss_pct = (gain_loss / cost_basis * 100) if cost_basis else 0
        else:
            market_value = gain_loss = gain_loss_pct = None

        positions.append({
            "ticker": ticker,
            "shares": shares,
            "cost_per_share": cost_per_share,
            "cost_basis": round(cost_basis, 2),
            "current_price": round(current_price, 2) if current_price is not None else None,
            "market_value": round(market_value, 2) if market_value is not None else None,
            "gain_loss": round(gain_loss, 2) if gain_loss is not None else None,
            "gain_loss_pct": round(gain_loss_pct, 2) if gain_loss is not None else None,
        })

    priced = [p for p in positions if p["market_value"] is not None]
    if priced:
        total_cost = sum(p["cost_basis"] for p in priced)
        total_value = sum(p["market_value"] for p in priced)
        total_gain = total_value - total_cost
        totals = {
            "cost_basis": round(total_cost, 2),
            "market_value": round(total_value, 2),
            "gain_loss": round(total_gain, 2),
            "gain_loss_pct": round(total_gain / total_cost * 100, 2) if total_cost else 0,
        }
    else:
        totals = None

    return {"positions": positions, "totals": totals}


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
                print(f"[volume] {ticker} error: {payload}")
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
        except Exception as e:
            print(f"[volume] {ticker} exception: {e}")
            continue

    return sorted(results, key=lambda r: r["ratio"], reverse=True)


# Twelve Data's /earnings_calendar requires a paid Grow-plan-or-higher key
# (confirmed via a 403 in production), so upcoming earnings are pulled from
# Finnhub instead — free tier, no credit card, genuinely includes this data.
# Get a free key at https://finnhub.io, set it as FINNHUB_API_KEY.
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY")


def get_upcoming_earnings(days_ahead=30, limit=40):
    """
    Pulls the market-wide earnings calendar (not filtered to any watchlist)
    from Finnhub's free /calendar/earnings endpoint.
    """
    if not FINNHUB_API_KEY:
        return []

    today = datetime.now().date()
    end = today + timedelta(days=days_ahead)

    try:
        url = "https://finnhub.io/api/v1/calendar/earnings"
        params = {
            "from": today.isoformat(),
            "to": end.isoformat(),
            "token": FINNHUB_API_KEY,
        }
        resp = requests.get(url, params=params, timeout=15)
        payload = resp.json()

        if isinstance(payload, dict) and payload.get("error"):
            print(f"[earnings] error: {payload}")
            return []

        rows = payload.get("earningsCalendar", [])
        results = []
        for row in rows:
            date_str = row.get("date")
            symbol = row.get("symbol")
            if not date_str or not symbol:
                continue
            if symbol.upper() not in POPULAR_TICKERS:
                continue
            try:
                row_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue
            if row_date < today:
                continue
            results.append({
                "ticker": symbol,
                "date": row_date,
                "time": row.get("hour", ""),  # "bmo" / "amc" / "dmh"
                "eps_estimate": row.get("epsEstimate"),
            })

        results.sort(key=lambda r: r["date"])
        for r in results:
            r["date"] = r["date"].strftime("%Y-%m-%d")
        return results[:limit]

    except Exception as e:
        print(f"[earnings] exception: {e}")
        return []


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

# Miles & Gario's actual options positions, tracked live against the real
# market (via Market Data's quote endpoint) rather than estimated.
OPTIONS_POSITIONS = [
    {
        "ticker": "NOW", "side": "call", "strike": 114,
        "expiration": "2026-07-31", "contracts": 1,
        "avg_cost": 1.95, "date_bought": "2026-07-22",
    },
]


def _occ_symbol(ticker, expiration, side, strike):
    """Builds an OCC option symbol, e.g. NOW260731C00114000."""
    exp = datetime.strptime(expiration, "%Y-%m-%d").strftime("%y%m%d")
    side_code = "C" if side.lower() == "call" else "P"
    strike_code = f"{int(round(strike * 1000)):08d}"
    return f"{ticker.upper()}{exp}{side_code}{strike_code}"


def get_options_positions():
    """
    Live valuation of OPTIONS_POSITIONS via Market Data's single-contract
    quote endpoint — real bid/ask/mid pricing, not a theoretical estimate.
    """
    if not MARKETDATA_API_KEY:
        return []

    headers = {"Authorization": f"Bearer {MARKETDATA_API_KEY}"}
    results = []

    for pos in OPTIONS_POSITIONS:
        symbol = _occ_symbol(pos["ticker"], pos["expiration"], pos["side"], pos["strike"])
        entry = {**pos, "symbol": symbol, "current_price": None, "underlying_price": None}

        try:
            url = f"https://api.marketdata.app/v1/options/quotes/{symbol}/"
            resp = requests.get(url, headers=headers, timeout=10)
            payload = resp.json()

            if payload.get("s") != "ok":
                print(f"[options-position] {symbol} error: {payload}")
            else:
                mid = payload.get("mid", [None])[0]
                last = payload.get("last", [None])[0]
                entry["current_price"] = mid if mid is not None else last
                entry["underlying_price"] = payload.get("underlyingPrice", [None])[0]
                entry["delta"] = payload.get("delta", [None])[0]
                entry["iv"] = payload.get("iv", [None])[0]
        except Exception as e:
            print(f"[options-position] {symbol} exception: {e}")

        cost_basis = pos["avg_cost"] * 100 * pos["contracts"]
        if entry["current_price"] is not None:
            market_value = entry["current_price"] * 100 * pos["contracts"]
            gain_loss = market_value - cost_basis
            gain_loss_pct = (gain_loss / cost_basis * 100) if cost_basis else 0
        else:
            market_value = gain_loss = gain_loss_pct = None

        entry["cost_basis"] = round(cost_basis, 2)
        entry["market_value"] = round(market_value, 2) if market_value is not None else None
        entry["gain_loss"] = round(gain_loss, 2) if gain_loss is not None else None
        entry["gain_loss_pct"] = round(gain_loss_pct, 2) if gain_loss is not None else None
        results.append(entry)

    return results


def scan_unusual_options(tickers, volume_oi_ratio=1.0, min_volume=100):
    if not MARKETDATA_API_KEY:
        return []

    headers = {"Authorization": f"Bearer {MARKETDATA_API_KEY}"}
    results = []

    for ticker in tickers:
        try:
            url = f"https://api.marketdata.app/v1/options/chain/{ticker}/"
            params = {"dte": 30, "range": "all", "strikeLimit": 10}
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
                    "price": payload.get("underlyingPrice", [None])[i],
                    "bid": payload.get("bid", [None])[i],
                    "ask": payload.get("ask", [None])[i],
                    "iv": payload.get("iv", [None])[i],
                    "delta": payload.get("delta", [None])[i],
                    "premium": (
                        round(payload.get("mid", [0])[i] * volume * 100, 2)
                        if payload.get("mid", [None])[i] is not None else None
                    ),
                    "updated": (
                        datetime.fromtimestamp(payload["updated"][i]).strftime("%m/%d/%Y")
                        if payload.get("updated", [None])[i] else ""
                    ),
                })
        except Exception:
            continue

    return sorted(results, key=lambda r: r["volume"], reverse=True)
