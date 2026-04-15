"""
Cup & Handle Scanner  — uses shared data_loader, no direct downloads.
"""
import warnings
warnings.filterwarnings("ignore")
import argparse
import pandas as pd
from data_loader import download_all, INDEX_MAP


def is_rounded_bottom(prices):
    n = len(prices)
    if n < 10:
        return False
    mid      = n // 2
    left_avg = float(prices.iloc[:mid].mean())
    right_avg= float(prices.iloc[mid:].mean())
    bottom   = float(prices.min())
    top_avg  = (left_avg + right_avg) / 2
    return (top_avg - bottom) / top_avg > 0.04


def detect_cup_handle(df, ticker):
    try:
        if df is None or len(df) < 60:
            return None

        close   = df["Close"].squeeze()
        volume  = df["Volume"].squeeze()
        avg_vol = volume.rolling(20).mean()
        sma200  = close.rolling(200).mean()

        if float(close.iloc[-1]) < float(sma200.iloc[-1]):
            return None

        total_bars = len(close)
        best = None

        for cup_len in range(20, min(131, total_bars - 10)):
            cup_end   = total_bars - 10
            cup_start = cup_end - cup_len
            if cup_start < 5:
                continue

            cup_slice = close.iloc[cup_start:cup_end + 1]
            left_lip  = float(cup_slice.iloc[0])
            right_lip = float(cup_slice.iloc[-1])
            cup_low   = float(cup_slice.min())

            if abs(right_lip - left_lip) / left_lip * 100 > 5:
                continue

            cup_depth = (left_lip - cup_low) / left_lip * 100
            if not (12 <= cup_depth <= 40):
                continue

            if not is_rounded_bottom(cup_slice):
                continue

            for handle_len in range(5, 26):
                h_start = cup_end
                h_end   = h_start + handle_len
                if h_end >= total_bars:
                    continue

                handle_slice  = close.iloc[h_start:h_end + 1]
                handle_low    = float(handle_slice.min())
                handle_high   = float(handle_slice.max())
                handle_pullbk = (right_lip - handle_low) / right_lip * 100

                if not (3 <= handle_pullbk <= 15):
                    continue
                if handle_high > left_lip * 1.02:
                    continue

                cup_vol_avg    = float(volume.iloc[cup_start:cup_end].mean())
                handle_vol_avg = float(volume.iloc[h_start:h_end].mean())
                if handle_vol_avg > cup_vol_avg * 0.9:
                    continue

                today_close   = float(close.iloc[-1])
                pivot         = max(left_lip, right_lip)
                dist_to_pivot = (pivot - today_close) / pivot * 100

                if dist_to_pivot < -2:
                    continue

                today_vol     = float(volume.iloc[-1])
                avg_vol_today = float(avg_vol.iloc[-1])
                vol_ratio     = round(today_vol / avg_vol_today, 1) if avg_vol_today else 0
                breaking_out  = today_close >= pivot * 0.99 and today_vol > avg_vol_today * 1.2

                candidate = {
                    "Ticker":          ticker,
                    "Close":           round(today_close, 2),
                    "Pivot (Buy Pt)":  round(pivot, 2),
                    "Dist to Pivot %": round(dist_to_pivot, 1),
                    "Cup Depth %":     round(cup_depth, 1),
                    "Cup Bars":        cup_len,
                    "Handle Bars":     handle_len,
                    "Handle Pullbk %": round(handle_pullbk, 1),
                    "Vol Ratio":       vol_ratio,
                    "Status":          "BREAKING OUT" if breaking_out else "Forming",
                }
                if best is None or dist_to_pivot < best["Dist to Pivot %"]:
                    best = candidate

        return best
    except Exception:
        return None


def scan(data, index="all", output=None):
    tickers = sorted(set(INDEX_MAP.get(index.lower(), [])))
    print(f"\n{'='*55}")
    print(f"  CUP & HANDLE SCANNER")
    print(f"{'='*55}")

    results = []
    for i, ticker in enumerate(tickers, 1):
        print(f"  [{i:>3}/{len(tickers)}] {ticker:<8}", end="\r")
        r = detect_cup_handle(data.get(ticker), ticker)
        if r:
            results.append(r)

    print(f"\n  Found {len(results)} cup & handle candidate(s).\n")
    if not results:
        print("  No cup & handle patterns detected.\n")
        return pd.DataFrame()

    df_out = pd.DataFrame(results).sort_values("Dist to Pivot %")
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
    parser.add_argument("--index",  default="all", choices=list(INDEX_MAP))
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    data = download_all(args.index)
    scan(data, args.index, args.output)
