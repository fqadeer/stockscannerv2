"""
Breakout Scanner  — uses shared data_loader, no direct downloads.
"""
import warnings
warnings.filterwarnings("ignore")
import argparse
import pandas as pd
from data_loader import download_all, INDEX_MAP


def compute_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def analyze_ticker(df, ticker, lookback, vol_multiplier):
    try:
        if df is None or len(df) < max(lookback + 1, 201):
            return None

        close  = df["Close"].squeeze()
        volume = df["Volume"].squeeze()
        high   = df["High"].squeeze()

        sma50      = close.rolling(50).mean()
        sma200     = close.rolling(200).mean()
        rsi        = compute_rsi(close, 14)
        avg_vol_20 = volume.rolling(20).mean()

        today_close = float(close.iloc[-1])
        today_vol   = float(volume.iloc[-1])
        avg_vol     = float(avg_vol_20.iloc[-1])
        rsi_val     = float(rsi.iloc[-1])
        s50         = float(sma50.iloc[-1])
        s200        = float(sma200.iloc[-1])
        prev_close  = float(close.iloc[-2])
        period_high = float(high.iloc[-(lookback + 1):-1].max())

        if not (
            today_close > period_high and
            prev_close  <= period_high and
            today_vol   > vol_multiplier * avg_vol and
            50 <= rsi_val <= 80 and
            today_close > s50 and
            today_close > s200
        ):
            return None

        return {
            "Ticker":            ticker,
            "Close":             round(today_close, 2),
            "1D Chg %":          round((today_close - prev_close) / prev_close * 100, 2),
            f"{lookback}D High": round(period_high, 2),
            "% Above High":      round((today_close - period_high) / period_high * 100, 2),
            "Vol Ratio":         round(today_vol / avg_vol, 1) if avg_vol else 0,
            "RSI(14)":           round(rsi_val, 1),
            "SMA50":             round(s50, 2),
            "SMA200":            round(s200, 2),
        }
    except Exception:
        return None


def scan(data, index="all", lookback=20, vol_multiplier=1.5, output=None):
    """
    data : dict { ticker -> DataFrame } from data_loader.download_all()
    """
    tickers = sorted(set(INDEX_MAP.get(index.lower(), [])))
    print(f"\n{'='*55}")
    print(f"  BREAKOUT SCANNER  |  lookback={lookback}d  vol={vol_multiplier}x")
    print(f"{'='*55}")

    results = []
    for i, ticker in enumerate(tickers, 1):
        print(f"  [{i:>3}/{len(tickers)}] {ticker:<8}", end="\r")
        r = analyze_ticker(data.get(ticker), ticker, lookback, vol_multiplier)
        if r:
            results.append(r)

    print(f"\n  Found {len(results)} breakout candidate(s).\n")
    if not results:
        print("  No breakouts. Try --lookback 20 or --vol-multiplier 1.2\n")
        return pd.DataFrame()

    df_out = pd.DataFrame(results).sort_values("% Above High", ascending=False)
    try:
        from tabulate import tabulate
        print(tabulate(df_out, headers="keys", tablefmt="rounded_outline",
                       showindex=False, floatfmt=".2f"))
    except ImportError:
        print(df_out.to_string(index=False))

    if output:
        df_out.to_csv(output, index=False)
        print(f"\n  Saved to: {output}")
    return df_out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--index",          default="all", choices=list(INDEX_MAP))
    parser.add_argument("--lookback",       type=int,   default=20)
    parser.add_argument("--vol-multiplier", type=float, default=1.5)
    parser.add_argument("--output",         default=None)
    args = parser.parse_args()

    data = download_all(args.index)
    scan(data, args.index, args.lookback, args.vol_multiplier, args.output)
