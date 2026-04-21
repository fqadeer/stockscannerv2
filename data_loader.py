"""
data_loader.py
==============
Downloads OHLCV data by calling Yahoo Finance's JSON API directly,
with proper browser headers. No yfinance needed for the actual HTTP call —
we just use yfinance to parse the response.

This bypasses all yfinance session/rate-limit issues at the source.

Install:
  pip install yfinance pandas requests tabulate
"""

import time
import warnings
import datetime
warnings.filterwarnings("ignore")

import requests
import pandas as pd

# ── Index constituents ────────────────────────────────────────────────────────

SP500_SAMPLE = [
    "AAPL","MSFT","AMZN","NVDA","GOOGL","META","TSLA","BRK-B","UNH","LLY",
    "JPM","V","XOM","AVGO","PG","MA","HD","CVX","MRK","ABBV",
    "COST","PEP","KO","ADBE","WMT","BAC","CRM","TMO","ACN","MCD",
    "CSCO","ABT","NKE","DHR","LIN","TXN","NEE","PM","ORCL","AMD",
    "AMGN","RTX","HON","QCOM","UNP","LOW","INTU","SPGI","CAT","AMAT",
]

NASDAQ100_SAMPLE = [
    "AAPL","MSFT","NVDA","AMZN","META","TSLA","GOOGL","GOOG","AVGO","ADBE",
    "COST","CSCO","AMD","INTC","INTU","CMCSA","NFLX","HON","AMAT","PYPL",
    "SBUX","MDLZ","REGN","GILD","LRCX","SNPS","CDNS","PANW","MRVL","ASML",
    "KLAC","ORLY","MNST","FTNT","CHTR","ABNB","DXCM","IDXX","MELI","ILMN",
]

DOW30 = [
    "AAPL","AMGN","AXP","BA","CAT","CRM","CSCO","CVX","DIS","DOW",
    "GS","HD","HON","IBM","INTC","JNJ","JPM","KO","MCD","MMM",
    "MRK","MSFT","NKE","PG","TRV","UNH","V","VZ","WBA","WMT",
]

INDEX_MAP = {
    "sp500":     SP500_SAMPLE,
    "nasdaq100": NASDAQ100_SAMPLE,
    "dow30":     DOW30,
    "all":       list(set(SP500_SAMPLE + NASDAQ100_SAMPLE + DOW30)),
}

# ── Yahoo Finance direct API ──────────────────────────────────────────────────

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin":          "https://finance.yahoo.com",
    "Referer":         "https://finance.yahoo.com/",
    "Sec-Fetch-Dest":  "empty",
    "Sec-Fetch-Mode":  "cors",
    "Sec-Fetch-Site":  "same-site",
}


def _get_crumb(session):
    """Fetch a Yahoo Finance crumb token (required since 2023 API change)."""
    try:
        # First visit the consent/login page to get cookies
        session.get("https://finance.yahoo.com", headers=HEADERS, timeout=10)
        time.sleep(1)
        r = session.get(
            "https://query1.finance.yahoo.com/v1/test/getcrumb",
            headers=HEADERS, timeout=10
        )
        if r.status_code == 200 and r.text and "<" not in r.text:
            return r.text.strip()
    except Exception:
        pass
    return None


def _fetch_ticker(ticker, period_days, session, crumb):
    """
    Fetch OHLCV for one ticker via Yahoo Finance v8 chart API.
    Returns a pd.DataFrame or None.
    """
    end   = int(time.time())
    start = end - (period_days * 86400)

    params = {
        "period1":  start,
        "period2":  end,
        "interval": "1d",
        "events":   "history",
    }
    if crumb:
        params["crumb"] = crumb

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"

    for attempt in range(1, 4):
        try:
            r = session.get(url, params=params, headers=HEADERS, timeout=15)

            if r.status_code == 429:
                wait = 30 * attempt
                print(f"\n    Rate limited. Waiting {wait}s...", flush=True)
                time.sleep(wait)
                continue

            if r.status_code != 200:
                print(f"\n    HTTP {r.status_code} for {ticker}", flush=True)
                return None

            data = r.json()
            result = data.get("chart", {}).get("result")
            if not result:
                return None

            result    = result[0]
            timestamps = result.get("timestamp", [])
            quotes    = result.get("indicators", {}).get("quote", [{}])[0]
            adjclose  = result.get("indicators", {}).get("adjclose", [{}])

            if not timestamps or not quotes.get("close"):
                return None

            closes = adjclose[0].get("adjclose") if adjclose else quotes.get("close")

            df = pd.DataFrame({
                "Open":   quotes.get("open"),
                "High":   quotes.get("high"),
                "Low":    quotes.get("low"),
                "Close":  closes,
                "Volume": quotes.get("volume"),
            }, index=pd.to_datetime(timestamps, unit="s", utc=True).tz_convert("America/New_York"))

            df = df.dropna(how="all")
            if len(df) > 10:
                return df

        except Exception as e:
            print(f"\n    Exception on {ticker}: {str(e)[:80]}", flush=True)
            time.sleep(5 * attempt)

    return None


def download_all(index="all", period="14mo", delay=1.5, chunk_size=None):
    """
    Download OHLCV data for every ticker by calling Yahoo Finance directly.

    Parameters
    ----------
    index      : sp500 / nasdaq100 / dow30 / all
    period     : '14mo', '1y', '6mo', '2y' etc.
    delay      : seconds between requests (default 1.5)
    chunk_size : unused, kept for CLI compatibility

    Returns
    -------
    dict { ticker -> pd.DataFrame }
    """
    # Convert period string to approximate days
    period_days_map = {
        "6mo": 183, "1y": 365, "14mo": 425, "2y": 730, "3y": 1095, "5y": 1825,
    }
    period_days = period_days_map.get(period.lower(), 425)

    tickers = sorted(set(INDEX_MAP.get(index.lower(), [])))
    session = requests.Session()

    print(f"\n  Getting Yahoo Finance auth token...", flush=True)
    crumb = _get_crumb(session)
    if crumb:
        print(f"  Auth token obtained.\n", flush=True)
    else:
        print(f"  No auth token — will try without (may affect some tickers).\n", flush=True)

    est_min = int(len(tickers) * delay / 60) + 1
    print(f"  Fetching {len(tickers)} tickers "
          f"(delay={delay}s, est. ~{est_min} min)...\n")

    data   = {}
    failed = []

    for i, ticker in enumerate(tickers, 1):
        print(f"  [{i:>3}/{len(tickers)}] {ticker:<8}", end=" ", flush=True)
        df = _fetch_ticker(ticker, period_days, session, crumb)
        if df is not None:
            data[ticker] = df
            print("ok", flush=True)
        else:
            failed.append(ticker)
            print("FAILED", flush=True)
        time.sleep(delay)

    # ── Retry failures ───────────────────────────────────────────────────────
    if failed:
        print(f"\n  Retrying {len(failed)} failed ticker(s) after 30s cooldown...\n")
        time.sleep(30)
        # Refresh crumb for retry pass
        crumb = _get_crumb(session) or crumb
        still_failed = []
        for ticker in failed:
            print(f"  Retry  {ticker:<8}", end=" ", flush=True)
            df = _fetch_ticker(ticker, period_days, session, crumb)
            if df is not None:
                data[ticker] = df
                print("ok", flush=True)
            else:
                still_failed.append(ticker)
                print("giving up", flush=True)
            time.sleep(3)

        if still_failed:
            print(f"\n  Could not load: {', '.join(still_failed)}")

    print(f"\n  Done. {len(data)}/{len(tickers)} tickers loaded.\n")
    return data
