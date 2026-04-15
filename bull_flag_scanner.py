"""
Bull Flag Scanner  — uses shared data_loader, no direct downloads.
"""
import warnings
warnings.filterwarnings("ignore")
import argparse
import pandas as pd
from data_loader import download_all, INDEX_MAP


def detect_bull_flag(df, ticker):
    try:
        if df is None or len(df) < 60:
            return None

        close  = df["Close"].squeeze()
        volume = df["Volume"].squeeze()
        high   = df["High"].squeeze()
        low    = df["Low"].squeeze()

        avg_vol = volume.rolling(20).mean()
        sma50   = close.rolling(50).mean()

        if float(close.iloc[-1]) < float(sma50.iloc[-1]):
            return None

        # Find pole: 5-15 bar rally of 8-40% on above-avg volume
        pole_found = False
        pole_start = pole_end = -1
        pole_gain  = 0.0

        for pole_len in range(5, 16):
            for end in range(len(close) - 5, max(len(close) - 30, pole_len), -1):
                start = end - pole_len
                if start < 0:
                    continue
                gain     = (float(close.iloc[end]) - float(close.iloc[start])) / float(close.iloc[start]) * 100
                avg_v    = float(avg_vol.iloc[end])
                pole_vol = float(volume.iloc[start:end+1].mean())
                if 8 <= gain <= 40 and pole_vol > avg_v * 1.2:
                    pole_found = True
                    pole_start, pole_end, pole_gain = start, end, gain
                    break
            if pole_found:
                break

        if not pole_found:
            return None

        flag_bars = df.iloc[pole_end:]
        if len(flag_bars) < 5 or len(flag_bars) > 25:
            return None

        flag_close  = flag_bars["Close"].squeeze()
        flag_high   = flag_bars["High"].squeeze()
        flag_volume = flag_bars["Volume"].squeeze()

        flag_high_val  = float(flag_high.max())
        flag_low_val   = float(flag_bars["Low"].squeeze().min())
        flag_range_pct = (flag_high_val - flag_low_val) / flag_high_val * 100

        if flag_range_pct > 10:
            return None

        pole_avg_vol = float(volume.iloc[pole_start:pole_end+1].mean())
        if float(flag_volume.mean()) > pole_avg_vol * 0.9:
            return None

        flag_drift = (float(flag_close.iloc[-1]) - float(flag_close.iloc[0])) / float(flag_close.iloc[0]) * 100
        if flag_drift > 3:
            return None

        today_close   = float(close.iloc[-1])
        today_vol     = float(volume.iloc[-1])
        avg_vol_today = float(avg_vol.iloc[-1])
        vol_ratio     = round(today_vol / avg_vol_today, 1) if avg_vol_today else 0
        breaking_out  = today_close >= flag_high_val * 0.99 and today_vol > avg_vol_today * 1.3

        return {
            "Ticker":       ticker,
            "Close":        round(today_close, 2),
            "Pole Gain %":  round(pole_gain, 1),
            "Flag Bars":    len(flag_bars),
            "Flag Range %": round(flag_range_pct, 1),
            "Flag Drift %": round(flag_drift, 1),
            "Vol Ratio":    vol_ratio,
            "Status":       "BREAKING OUT" if breaking_out else "Forming",
            "Flag High":    round(flag_high_val, 2),
        }
    except Exception:
        return None


def scan(data, index="all", output=None):
    tickers = sorted(set(INDEX_MAP.get(index.lower(), [])))
    print(f"\n{'='*55}")
    print(f"  BULL FLAG SCANNER")
    print(f"{'='*55}")

    results = []
    for i, ticker in enumerate(tickers, 1):
        print(f"  [{i:>3}/{len(tickers)}] {ticker:<8}", end="\r")
        r = detect_bull_flag(data.get(ticker), ticker)
        if r:
            results.append(r)

    print(f"\n  Found {len(results)} bull flag candidate(s).\n")
    if not results:
        print("  No bull flags detected.\n")
        return pd.DataFrame()

    df_out = pd.DataFrame(results).sort_values("Pole Gain %", ascending=False)
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
