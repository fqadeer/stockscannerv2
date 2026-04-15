"""
data_loader.py
==============
Downloads ticker data using curl_cffi to impersonate a real Chrome browser,
which bypasses Yahoo Finance rate limiting reliably.

Install:
  pip install yfinance curl_cffi pandas
"""

import time
import warnings
warnings.filterwarnings("ignore")

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


def _make_session():
    """
    Create a curl_cffi session that impersonates Chrome.
    Falls back to a plain requests session if curl_cffi is not installed.
    """
    try:
        from curl_cffi import requests as cffi_requests
        session = cffi_requests.Session(impersonate="chrome120")
        print("  [info] Using curl_cffi Chrome impersonation (best rate-limit bypass).")
        return session
    except ImportError:
        print("  [warn] curl_cffi not found — falling back to requests.")
        print("         For best results: pip install curl_cffi")
        import requests
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        })
        return session


def _fetch_ticker(ticker, period, session):
    """Fetch a single ticker via yfinance using the provided session."""
    import yfinance as yf
    for attempt in range(1, 4):
        try:
            df = yf.download(
                ticker,
                period=period,
                interval="1d",
                auto_adjust=True,
                progress=False,
                threads=False,
                session=session,
            )
            if df is not None and len(df) > 10:
                # Flatten MultiIndex if present
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                return df.dropna(how="all")
        except Exception as e:
            err = str(e)
            if "Rate" in err or "429" in err:
                wait = 15 * attempt
                print(f"\n    Rate limit hit for {ticker}. Waiting {wait}s...")
                time.sleep(wait)
            else:
                break  # non-rate-limit error, skip
    return None


def download_all(index="all", period="14mo", delay=1.5, chunk_size=None):
    """
    Download all tickers one at a time using a Chrome-impersonating session.
    One-at-a-time is slower but far more reliable than batch for Yahoo Finance.

    Parameters
    ----------
    index      : sp500 / nasdaq100 / dow30 / all
    period     : yfinance period string
    delay      : seconds between each ticker request (1-2s is safe)
    chunk_size : ignored (kept for backward compatibility)

    Returns
    -------
    dict { ticker -> pd.DataFrame }
    """
    tickers = sorted(set(INDEX_MAP.get(index.lower(), [])))
    session = _make_session()
    data    = {}

    print(f"\n  Fetching {len(tickers)} tickers one-by-one "
          f"(delay={delay}s between each)...")
    print(f"  Estimated time: ~{int(len(tickers) * delay / 60) + 1} minute(s)\n")

    failed = []
    for i, ticker in enumerate(tickers, 1):
        print(f"  [{i:>3}/{len(tickers)}] {ticker:<8}", end=" ")
        df = _fetch_ticker(ticker, period, session)
        if df is not None:
            data[ticker] = df
            print("ok")
        else:
            failed.append(ticker)
            print("FAILED")
        time.sleep(delay)

    # ── One retry pass for failures ──────────────────────────────────────────
    if failed:
        print(f"\n  Retrying {len(failed)} failed ticker(s) after 15s cooldown...")
        time.sleep(15)
        for ticker in failed:
            print(f"  Retry {ticker:<8}", end=" ")
            df = _fetch_ticker(ticker, period, session)
            if df is not None:
                data[ticker] = df
                print("ok")
            else:
                print("still failed — skipping")
            time.sleep(3)

    print(f"\n  Done. {len(data)}/{len(tickers)} tickers loaded.\n")
    return data
