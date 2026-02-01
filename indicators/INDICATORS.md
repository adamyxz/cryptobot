# Indicators System

## Overview

The `indicators/` directory contains modular Python scripts for collecting market data. All scripts return CSV format output for efficient token usage and easy parsing by AI systems.

---

## Core Standards

### 1. Output Format

**Must be CSV (comma-separated values)**
- Comma-separated, not tab-separated or other formats
- No extra formatting (no quotes around numbers unless necessary)
- One data row per line

### 2. Column Names

**Use short, descriptive headers**
- Lowercase with underscores: `price`, `volume`, `ask_price`
- Avoid spaces in column names
- Be concise but clear

### 3. Timestamps

**Omit timestamp fields**
- Order implies sequence - first row = earliest
- If timing is critical, add to description/docstring instead
- Reduces token usage significantly

### 4. Error Handling

**Return CSV with single `error` column if failed**
```csv
error
Connection timeout
Invalid symbol
Rate limit exceeded
```

### 5. Data Philosophy

**Raw data only - no analysis**
- Provide raw numbers, not interpretations
- Let AI/LLM calculate trends, patterns, signals
- No " bullish" or "bearish" labels
- No buy/sell recommendations

---

## Script Structure

### Required Elements

```python
"""Brief one-line description of what this indicator does.

More detailed explanation (optional).
Usage:
    python indicators/script_name.py --exchange binance --symbol BTCUSDT
"""

import argparse
from typing import List, Tuple

def fetch_indicator(exchange: str, symbol: str, **kwargs):
    """
    Main function that fetches and processes data.

    Args:
        exchange: Exchange name (binance, okx, bybit, bitget)
        symbol: Trading symbol (e.g., BTCUSDT)
        **kwargs: Additional parameters from command line

    Returns:
        List of tuples or similar structure containing data
    """
    # Implementation here
    pass

def main():
    parser = argparse.ArgumentParser(description='Brief description')
    parser.add_argument('--exchange', required=True, help='Exchange name')
    parser.add_argument('--symbol', required=True, help='Trading symbol')
    # Add more arguments as needed
    args = parser.parse_args()

    try:
        data = fetch_indicator(args.exchange, args.symbol)

        if not data:
            print("error,no data available")
            return

        # Output CSV header
        print("col1,col2,col3")

        # Output data rows
        for row in data:
            print(f"{row[0]},{row[1]},{row[2]}")

    except Exception as e:
        print(f"error,{str(e)}")

if __name__ == '__main__':
    main()
```

---

## Best Practices

### Parameter Naming

**Use standard conventions:**
- `--exchange`: Exchange name (binance, okx, bybit, bitget)
- `--symbol`: Trading symbol (BTCUSDT, ETHUSDT)
- `--interval`: Timeframe (1m, 5m, 1h, 1d)
- `--limit`: Number of records to fetch

### Data Precision

**Use appropriate precision:**
- Prices: 2-8 decimal places depending on symbol
- Percentages: 2 decimal places
- Volume: 2-4 decimal places
- Avoid excessive precision (wastes tokens)

### Rate Limiting

**Be mindful of API limits:**
- Use CCXT's built-in rate limiting: `{'enableRateLimit': True}`
- Cache when possible
- Fetch only what's needed

### Exchange Compatibility

**Handle exchange differences:**
- Use `ccxt_adapter.convert_user_symbol_to_ccxt()` for symbol conversion
- Test on multiple exchanges if claiming compatibility
- Document exchange-specific limitations

---

## Common Patterns

### Pattern 1: Single Value Series

```python
# Output:
# value
# 100.5
# 101.2
# 99.8
print("value")
for val in data:
    print(f"{val}")
```

### Pattern 2: Key-Value Pairs

```python
# Output:
# side,price,volume
# bid,45000.0,10.5
# ask,45001.0,9.8
print("side,price,volume")
for side, price, vol in data:
    print(f"{side},{price},{vol}")
```

### Pattern 3: Multi-Column Time Series

```python
# Output:
# open,high,low,close,volume
# 45000,45500,44800,45200,1500
# 45200,45600,45000,45400,1600
print("open,high,low,close,volume")
for candle in data:
    print(f"{candle[0]},{candle[1]},{candle[2]},{candle[3]},{candle[4]}")
```

---

## Integration Notes

### With /decide Command

When `/decide <trader_id>` is executed:
1. System collects trader profile and position data
2. AI decides if additional data is needed
3. If needed, indicator scripts are executed
4. CSV output is parsed and included in decision context
5. AI makes trading decision based on all available data

### Testing Your Indicator

After creating an indicator:
1. Test with various parameters
2. Verify CSV output format
3. Check error handling
4. Test with invalid inputs
5. Clean up any test files created

---

## File Naming

**Use descriptive, snake_case names:**
- `fetch_orderbook.py` - Fetches order book data
- `market_data.py` - General market data
- `funding_rates.py` - Funding rate history
- `price_comparison.py` - Multi-exchange price comparison

**Avoid:**
- Generic names like `data.py`, `indicator.py`
- CamelCase like `fetchOrderBook.py`

---

## Common Mistakes to Avoid

1. **Including timestamps** - Order is sufficient
2. **Adding analysis** - Let AI interpret raw data
3. **Complex formatting** - Keep CSV simple
4. **Missing error handling** - Always handle exceptions
5. **Inconsistent precision** - Standardize decimal places
6. **Hardcoded symbols** - Use command-line arguments
7. **Verbose output** - Minimize non-CSV messages (use stderr for debug if needed)

---

## Example Indicators

### Order Book Data
```csv
side,price,volume
bid,45000.0,10.5
ask,45001.0,9.8
```

### K-line Data
```csv
open,high,low,close,volume
45000,45500,44800,45200,1500
```

### Funding Rates
```csv
exchange,rate,next_funding_time
binance,0.0001,2024-01-01T00:00:00Z
```

### Price Comparison
```csv
exchange,symbol,price,volume_24h
binance,BTCUSDT,45000.5,1000.5
okx,BTCUSDT,45001.2,950.3
```

### Open Interest
```csv
symbol,open_interest_amount,open_interest_value,timestamp
BTC/USDT:USDT,92422.184,0,1769960888464
```
