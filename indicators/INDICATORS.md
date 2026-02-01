# Indicators System

## Overview

The `indicators/` directory contains modular Python scripts for collecting market data. All scripts return CSV format output for efficient token usage.

## Available Indicators

### 1. fetch_orderbook.py

Fetches order book depth snapshot.

**Usage:**
```bash
python indicators/fetch_orderbook.py --exchange binance --symbol BTCUSDT --limit 20
```

**Parameters:**
- `--exchange`: Exchange name (binance, okx, bybit, bitget)
- `--symbol`: Trading symbol (e.g., BTCUSDT, ETHUSDT)
- `--limit`: Order book depth (default: 20)

**Output Format (CSV):**
```csv
side,price,volume
bid,45000.0,10.5
bid,44999.0,8.2
ask,45001.0,9.8
ask,45002.0,7.5
```

**Notes:**
- Bids first, then asks
- Sorted by price proximity to mid
- No timestamps - order preserved

---

### 2. market_data.py

Fetches K-line data with technical analysis.

**Usage:**
```bash
python indicators/market_data.py --exchange binance --symbol BTCUSDT --interval 1h
```

**Parameters:**
- `--exchange`: Exchange name
- `--symbol`: Trading symbol
- `--interval`: Timeframe (default: 1h)
- `--limit`: Number of candles (default: 100)

**Output Format (CSV):**
```csv
open,high,low,close,volume,rsi,trend,support,resistance
45000,45500,44800,45200,1500,65.5,uptrend,44500,45600
45200,45600,45000,45400,1600,68.2,uptrend,44800,45800
```

**Supported Intervals:**
1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d, 1w

---

## Integration with /decide Command

When `/decide <trader_id>` is executed:
1. System collects trader profile and position data
2. AI decides if additional data is needed
3. If needed, indicator scripts are executed
4. CSV output is parsed and included in decision context
5. AI makes trading decision based on all available data

---

## Adding New Indicators

When creating new indicators:

1. **Output Format**: Must be CSV (comma-separated values)
2. **No Timestamps**: Omit timestamp fields - order implies sequence
3. **Minimal Headers**: Use short, descriptive column names
4. **No Analysis**: Only provide raw data - let LLM interpret
5. **Error Handling**: Return CSV with single `error` column if failed

**Template:**

```python
import argparse
import sys

def fetch_indicator(exchange: str, symbol: str, **kwargs):
    # Fetch data
    data = [...]  # Your data

    # Output CSV
    print("col1,col2,col3")
    for row in data:
        print(f"{row[0]},{row[1]},{row[2]}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exchange', required=True)
    parser.add_argument('--symbol', required=True)
    args = parser.parse_args()

    fetch_indicator(args.exchange, args.symbol)

if __name__ == '__main__':
    main()
```

---

## Notes

- All indicators use standard libraries where possible
- Exchange-specific adapters handled internally
- CSV format optimized for LLM consumption
- No interpretive guidance provided - analysis delegated to AI
