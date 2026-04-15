# Stock Pattern Scanner

A Python-based stock scanner that detects high-probability chart patterns across S&P 500, NASDAQ 100, and Dow Jones 30 constituents. Downloads market data once and passes it to three independent pattern scanners — avoiding redundant requests and Yahoo Finance rate limits.

## Patterns Detected

| Scanner | Pattern | Typical Win Rate | Avg Gain |
|---|---|---|---|
| `breakout_scanner.py` | Price breakout above N-day high on volume surge | 65–70% | 10–20% |
| `bull_flag_scanner.py` | Strong pole + tight low-volume consolidation | 65–70% | 15–25% |
| `cup_handle_scanner.py` | U-shaped base + handle near prior high (pivot) | 60–65% | 20–30% |

The combined runner flags **confluence tickers** — stocks appearing in two or more scanners simultaneously, which represent the highest-conviction setups.

---

## Project Structure

```
stock-scanner/
├── data_loader.py          # Downloads market data once, shared by all scanners
├── breakout_scanner.py     # Breakout pattern detection
├── bull_flag_scanner.py    # Bull flag pattern detection
├── cup_handle_scanner.py   # Cup & handle pattern detection
└── run_all_scanners.py     # Runs all three scanners in one command
```

---

## Requirements

- Python 3.9+
- Dependencies:

```bash
pip install yfinance pandas tabulate curl_cffi openpyxl
```

> `curl_cffi` is the key dependency for bypassing Yahoo Finance rate limits. It impersonates a real Chrome browser at the TLS level, which standard `requests` cannot do.

---

## Usage

### Run all three scanners at once

```bash
python run_all_scanners.py --index all
```

### Scan a specific index

```bash
python run_all_scanners.py --index nasdaq100
python run_all_scanners.py --index sp500
python run_all_scanners.py --index dow30
```

### Save results to Excel (one sheet per pattern)

```bash
python run_all_scanners.py --index all --output results.xlsx
```

### Save results to CSV

```bash
python run_all_scanners.py --index all --output results.csv
```

### Tune the breakout scanner parameters

```bash
# 20-day breakout window, volume must be 1.2x average
python run_all_scanners.py --index all --lookback 20 --vol-multiplier 1.2
```

### Run individual scanners

```bash
python breakout_scanner.py   --index nasdaq100 --lookback 20
python bull_flag_scanner.py  --index all
python cup_handle_scanner.py --index sp500
```

---

## How It Works

### Data loading (`data_loader.py`)

Data is downloaded **once** using a `curl_cffi` Chrome-impersonating session, then passed as a shared `dict` to each scanner. This avoids redundant downloads and rate limiting.

Tickers are fetched one at a time with a short delay between requests (~1.5s). For 86 tickers this takes roughly 2 minutes.

### Breakout Scanner

Flags stocks closing above their N-day high on a volume surge. All four conditions must be true simultaneously:

1. Close above the N-day high (default: 20-day)
2. Previous close was at or below that high (confirms new breakout, not a stale one)
3. Today's volume exceeds 1.5× the 20-day average
4. Price is above both the 50-day and 200-day SMA

### Bull Flag Scanner

Looks for a two-part structure:

1. **Pole** — a sharp rally of 8–40% over 5–15 bars on above-average volume
2. **Flag** — a tight consolidation (range < 10%) over 5–25 bars on declining volume, with a slight downward or flat drift

Marks setups as `BREAKING OUT` when price is at or above the flag high with volume confirmation.

### Cup & Handle Scanner

Looks for a three-part structure:

1. **Cup** — a U-shaped decline and recovery of 12–40% depth over 20–130 bars, with left and right lips within 5% of each other
2. **Handle** — a 3–15% pullback from the right lip over 5–25 bars on lighter volume than the cup
3. **Pivot point** — the buy point is the high of the cup (right lip). Sorts results by distance to pivot so the closest setups appear first.

### Confluence

Any ticker appearing in two or more scanners is highlighted as a high-conviction setup. For example, a stock forming a cup & handle *and* triggering a breakout signal on the same day is a much stronger candidate than either signal alone.

---

## CLI Reference

### `run_all_scanners.py`

| Argument | Default | Description |
|---|---|---|
| `--index` | `all` | Index to scan: `sp500`, `nasdaq100`, `dow30`, `all` |
| `--lookback` | `20` | N-day high window for breakout scanner |
| `--vol-multiplier` | `1.5` | Volume vs 20-day average threshold for breakout scanner |
| `--output` | None | Save path — `.xlsx` for Excel (3 sheets), `.csv` for flat file |

### `breakout_scanner.py`

| Argument | Default | Description |
|---|---|---|
| `--index` | `all` | Index to scan |
| `--lookback` | `20` | N-day high breakout window |
| `--vol-multiplier` | `1.5` | Volume multiplier threshold |
| `--output` | None | Optional CSV output path |

### `bull_flag_scanner.py` / `cup_handle_scanner.py`

| Argument | Default | Description |
|---|---|---|
| `--index` | `all` | Index to scan |
| `--output` | None | Optional CSV output path |

---

## Index Coverage

The scanner uses curated samples of the most liquid constituents from each index. For a production system, replace these lists with a live source or a CSV file of full index membership.

| Index | Tickers included |
|---|---|
| S&P 500 | 50 large-cap stocks |
| NASDAQ 100 | 40 tech-heavy stocks |
| Dow Jones 30 | All 30 components |
| All (combined) | ~86 unique tickers |

---

## Disclaimer

This tool is for **educational and research purposes only**. It does not constitute financial advice. Past pattern performance does not guarantee future results. Always do your own research and manage risk appropriately before placing any trade.

---

## License

MIT
