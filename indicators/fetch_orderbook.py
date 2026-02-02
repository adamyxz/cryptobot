"""Fetch order book snapshot

Usage:
    python indicators/fetch_orderbook.py --exchange binance --symbol BTCUSDT --limit 20

Output: CSV format (side,price,volume)
"""

import ccxt
import argparse
from typing import List, Tuple
from pathlib import Path


def fetch_orderbook(exchange: str, symbol: str, limit: int = 20) -> List[Tuple[str, float, float]]:
    """
    Fetch order book snapshot

    Args:
        exchange: Exchange name (binance, okx, bybit, bitget)
        symbol: Trading symbol (e.g., BTCUSDT)
        limit: Order book depth

    Returns:
        List of tuples (side, price, volume)
    """
    exchange_class = getattr(ccxt, exchange.lower())
    exchange_inst = exchange_class({'enableRateLimit': True})

    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from cryptobot.ccxt_adapter import convert_user_symbol_to_ccxt

        ccxt_symbol = convert_user_symbol_to_ccxt(exchange, symbol)
        orderbook = exchange_inst.fetch_order_book(ccxt_symbol, limit)

        bids = orderbook['bids'][:limit]
        asks = orderbook['asks'][:limit]

        if not bids or not asks:
            return []

        # Convert to (side, price, volume) format
        result = []
        for price, volume in bids:
            result.append(('bid', price, volume))
        for price, volume in asks:
            result.append(('ask', price, volume))

        return result

    finally:
        # Note: ccxt sync exchanges don't have a close() method
        # The connection will be cleaned up automatically
        pass


def main():
    parser = argparse.ArgumentParser(description='Fetch order book snapshot')
    parser.add_argument('--exchange', required=True, help='Exchange name')
    parser.add_argument('--symbol', required=True, help='Trading symbol')
    parser.add_argument('--limit', type=int, default=20, help='Order book depth')

    args = parser.parse_args()

    try:
        data = fetch_orderbook(args.exchange, args.symbol, args.limit)

        if not data:
            print("error,no data available")
            return

        # CSV output
        print("side,price,volume")
        for side, price, volume in data:
            print(f"{side},{price},{volume}")

    except Exception as e:
        print(f"error,{str(e)}")


if __name__ == '__main__':
    main()
