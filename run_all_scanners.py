"""
Combined Pattern Scanner
========================
Downloads data ONCE then passes it to all three scanners.

Usage:
  python run_all_scanners.py --index nasdaq100
  python run_all_scanners.py --index all
  python run_all_scanners.py --index all --output results.xlsx
  python run_all_scanners.py --index all --chunk-size 5 --delay 5
"""

import argparse
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
from data_loader      import download_all, INDEX_MAP
import breakout_scanner   as bs
import bull_flag_scanner  as bfs
import cup_handle_scanner as chs

DIV = "=" * 60


def run_all(index="all", lookback=20, vol_multiplier=1.5,
            chunk_size=10, delay=3, output=None):

    print(f"\n{'#'*60}")
    print(f"  COMBINED PATTERN SCANNER  |  index={index}")
    print(f"{'#'*60}")

    # ── Download ONCE ────────────────────────────────────────────────────────
    print(f"\n[Step 1/4]  Downloading market data...")
    data = download_all(index, chunk_size=chunk_size, delay=delay)

    if not data:
        print("No data downloaded. Check your internet connection.")
        return

    print(f"  {len(data)} tickers ready.\n")

    # ── Run all three scanners on the shared data ────────────────────────────
    print(f"[Step 2/4]  Running Breakout Scanner...")
    df_breakout = bs.scan(data, index, lookback, vol_multiplier)

    print(f"\n[Step 3/4]  Running Bull Flag Scanner...")
    df_bullflag = bfs.scan(data, index)

    print(f"\n[Step 4/4]  Running Cup & Handle Scanner...")
    df_cuphandle = chs.scan(data, index)

    # ── Summary ──────────────────────────────────────────────────────────────
    n_bo = len(df_breakout)  if df_breakout  is not None else 0
    n_bf = len(df_bullflag)  if df_bullflag  is not None else 0
    n_ch = len(df_cuphandle) if df_cuphandle is not None else 0

    print(f"\n{DIV}")
    print(f"  RESULTS SUMMARY")
    print(f"{DIV}")
    print(f"  Breakout      : {n_bo} candidate(s)")
    print(f"  Bull Flag     : {n_bf} candidate(s)")
    print(f"  Cup & Handle  : {n_ch} candidate(s)")

    # ── Confluence: tickers found by 2 or more scanners ─────────────────────
    sets = []
    if n_bo > 0: sets.append(set(df_breakout["Ticker"]))
    if n_bf > 0: sets.append(set(df_bullflag["Ticker"]))
    if n_ch > 0: sets.append(set(df_cuphandle["Ticker"]))

    confluence = set()
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            confluence |= sets[i] & sets[j]

    if confluence:
        print(f"\n  *** CONFLUENCE — appeared in 2+ scanners (highest conviction) ***")
        for t in sorted(confluence):
            patterns = []
            if n_bo > 0 and t in sets[0]: patterns.append("Breakout")
            if n_bf > 0 and t in (sets[1] if len(sets)>1 else set()): patterns.append("Bull Flag")
            if n_ch > 0 and t in (sets[-1] if sets else set()): patterns.append("Cup&Handle")
            print(f"    {t:<8}  {' + '.join(patterns)}")
    else:
        print(f"\n  No confluence tickers found.")

    print(f"\n{DIV}\n")

    # ── Save to Excel (3 sheets) or CSV ──────────────────────────────────────
    if output:
        if output.endswith(".xlsx"):
            try:
                import openpyxl
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    if n_bo > 0: df_breakout.to_excel(writer,  sheet_name="Breakouts",    index=False)
                    if n_bf > 0: df_bullflag.to_excel(writer,  sheet_name="Bull Flags",   index=False)
                    if n_ch > 0: df_cuphandle.to_excel(writer, sheet_name="Cup & Handle", index=False)
                    if confluence:
                        pd.DataFrame(sorted(confluence), columns=["Ticker"]).to_excel(
                            writer, sheet_name="Confluence", index=False)
                print(f"  Saved to: {output}")
            except ImportError:
                print("  openpyxl not installed. Run: pip install openpyxl")
        else:
            frames = []
            if n_bo > 0: df_breakout["Pattern"]  = "Breakout";  frames.append(df_breakout[["Ticker","Pattern"]])
            if n_bf > 0: df_bullflag["Pattern"]  = "Bull Flag"; frames.append(df_bullflag[["Ticker","Pattern"]])
            if n_ch > 0: df_cuphandle["Pattern"] = "Cup&Handle";frames.append(df_cuphandle[["Ticker","Pattern"]])
            if frames:
                pd.concat(frames).to_csv(output, index=False)
                print(f"  Saved to: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Combined Pattern Scanner")
    parser.add_argument("--index",          default="all", choices=list(INDEX_MAP))
    parser.add_argument("--lookback",       type=int,   default=20,
                        help="Breakout N-day high window (default: 20)")
    parser.add_argument("--vol-multiplier", type=float, default=1.5,
                        help="Breakout volume multiplier (default: 1.5)")
    parser.add_argument("--chunk-size",     type=int,   default=10,
                        help="Tickers per download chunk (default: 10, lower if rate limited)")
    parser.add_argument("--delay",          type=float, default=3,
                        help="Seconds between chunks (default: 3, increase if rate limited)")
    parser.add_argument("--output",         default=None,
                        help="Save to .xlsx (3 sheets) or .csv")
    args = parser.parse_args()

    run_all(
        index          = args.index,
        lookback       = args.lookback,
        vol_multiplier = args.vol_multiplier,
        chunk_size     = args.chunk_size,
        delay          = args.delay,
        output         = args.output,
    )
