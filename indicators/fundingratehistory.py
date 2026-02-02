"""Fetch funding rate history for perpetual futures

Usage:
    python indicators/fundingratehistory.py --exchange binance --symbol BTCUSDT --limit 100

Output: CSV format (timestamp,funding_rate)
"""

import ccxt
import argparse
from typing import List, Tuple
from pathlib import Path


def fetch_funding_rate_history(exchange: str, symbol: str, limit: int = 100, since: int = None) -> List[Tuple]:
    """
    Fetch funding rate history for perpetual futures

    Args:
        exchange: Exchange name (binance, okx, bybit, bitget)
        symbol: Trading symbol (e.g., BTCUSDT)
        limit: Number of funding rate records to fetch
        since: Timestamp in milliseconds for earliest record

    Returns:
        List of tuples (timestamp, funding_rate)
    """
    exchange_class = getattr(ccxt, exchange.lower())
    exchange_inst = exchange_class({'enableRateLimit': True})

    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from cryptobot.ccxt_adapter import convert_user_symbol_to_ccxt

        ccxt_symbol = convert_user_symbol_to_ccxt(exchange, symbol)

        # Fetch funding rate history
        funding_history = exchange_inst.fetch_funding_rate_history(ccxt_symbol, since=since, limit=limit)

        if not funding_history:
            return []

        # Convert to (timestamp, funding_rate) format
        result = []
        for entry in funding_history:
            timestamp = entry.get('timestamp', 0)
            funding_rate = entry.get('fundingRate', None)

            # Convert to percentage and round
            if funding_rate is not None:
                funding_rate = round(funding_rate * 100, 6)

            result.append((
                timestamp,
                funding_rate
            ))

        return result

    finally:
        # Note: ccxt sync exchanges don't have a close() method
        # The connection will be cleaned up automatically
        pass


def main():
    parser = argparse.ArgumentParser(description='Fetch funding rate history')
    parser.add_argument('--exchange', required=True, help='Exchange name')
    parser.add_argument('--symbol', required=True, help='Trading symbol')
    parser.add_argument('--limit', type=int, default=100, help='Number of records')
    parser.add_argument('--since', type=int, help='Timestamp in milliseconds for earliest record')

    args = parser.parse_args()

    try:
        data = fetch_funding_rate_history(args.exchange, args.symbol, args.limit, args.since)

        if not data:
            print("error,no data available")
            return

        # CSV output
        print("timestamp,funding_rate")
        for timestamp, funding_rate in data:
            print(f"{timestamp},{funding_rate}")

    except Exception as e:
        print(f"error,{str(e)}")


if __name__ == '__main__':
    main()
