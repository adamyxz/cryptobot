"""Fetch open interest data for perpetual futures

Usage:
    python indicators/fetch_open_interest.py --exchange binance --symbol BTCUSDT

Output: CSV format (symbol,open_interest,open_interest_value,timestamp)
"""

import ccxt
import argparse
from typing import List, Tuple
from pathlib import Path


def fetch_open_interest(exchange: str, symbol: str) -> List[Tuple]:
    """
    Fetch open interest data for a perpetual futures symbol

    Args:
        exchange: Exchange name (binance, okx, bybit, bitget)
        symbol: Trading symbol (e.g., BTCUSDT)

    Returns:
        List of tuples (symbol, open_interest, open_interest_value, timestamp)
    """
    exchange_class = getattr(ccxt, exchange.lower())
    exchange_inst = exchange_class({'enableRateLimit': True})

    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from cryptobot.ccxt_adapter import (
            convert_user_symbol_to_ccxt,
        )

        ccxt_symbol = convert_user_symbol_to_ccxt(exchange, symbol)

        # Fetch open interest data
        oi_data = exchange_inst.fetch_open_interest(ccxt_symbol)

        if not oi_data:
            return []

        # Extract data - structure varies by exchange but generally contains:
        # - symbol: trading pair
        # - openInterestAmount: contract amount
        # - openInterestValue: value in quote currency
        # - timestamp: data timestamp
        # Note: Different exchanges return different field names
        oi_amount = oi_data.get('openInterestAmount') or oi_data.get('openInterestAmountUSD') or oi_data.get('amount') or 0
        oi_value = oi_data.get('openInterestValue') or oi_data.get('value') or 0
        timestamp = oi_data.get('timestamp') or oi_data.get('datetime') or 0

        result = []
        result.append((
            oi_data.get('symbol', ccxt_symbol),
            float(oi_amount) if oi_amount else 0,
            float(oi_value) if oi_value else 0,
            timestamp
        ))

        return result

    finally:
        # Close if supported by the exchange
        if hasattr(exchange_inst, 'close'):
            exchange_inst.close()


def main():
    parser = argparse.ArgumentParser(description='Fetch open interest data')
    parser.add_argument('--exchange', required=True, help='Exchange name')
    parser.add_argument('--symbol', required=True, help='Trading symbol')

    args = parser.parse_args()

    try:
        data = fetch_open_interest(args.exchange, args.symbol)

        if not data:
            print("error,no data available")
            return

        # CSV output
        print("symbol,open_interest_amount,open_interest_value,timestamp")
        for row in data:
            print(f"{row[0]},{row[1]},{row[2]},{row[3]}")

    except Exception as e:
        print(f"error,{str(e)}")


if __name__ == '__main__':
    main()
