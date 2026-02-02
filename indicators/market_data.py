"""Fetch market data snapshot (OHLCV)

Usage:
    python indicators/market_data.py --exchange binance --symbol BTCUSDT --interval 1h

Output: CSV format (open,high,low,close,volume)
"""

import ccxt
import argparse
from typing import List, Tuple
from pathlib import Path


def fetch_market_snapshot(exchange: str, symbol: str, interval: str = '1h', limit: int = 100) -> List[Tuple]:
    """
    Fetch market data snapshot (OHLCV)

    Args:
        exchange: Exchange name
        symbol: Trading symbol
        interval: Timeframe
        limit: Number of candles

    Returns:
        List of tuples (open, high, low, close, volume)
    """
    exchange_class = getattr(ccxt, exchange.lower())
    exchange_inst = exchange_class({'enableRateLimit': True})

    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from cryptobot.ccxt_adapter import (
            convert_user_symbol_to_ccxt,
            TIMEFRAME_MAP
        )

        ccxt_symbol = convert_user_symbol_to_ccxt(exchange, symbol)
        ccxt_interval = TIMEFRAME_MAP.get(interval, interval)

        ohlcv = exchange_inst.fetch_ohlcv(ccxt_symbol, ccxt_interval, limit=limit)

        if not ohlcv:
            return []

        # Return OHLCV data
        result = []
        for candle in ohlcv[-limit:]:
            result.append((
                round(candle[1], 2),  # open
                round(candle[2], 2),  # high
                round(candle[3], 2),  # low
                round(candle[4], 2),  # close
                round(candle[5], 2),  # volume
            ))

        return result

    finally:
        # Note: ccxt sync exchanges don't have a close() method
        # The connection will be cleaned up automatically
        pass


def main():
    parser = argparse.ArgumentParser(description='Fetch market data snapshot')
    parser.add_argument('--exchange', required=True, help='Exchange name')
    parser.add_argument('--symbol', required=True, help='Trading symbol')
    parser.add_argument('--interval', default='1h', help='Timeframe')
    parser.add_argument('--limit', type=int, default=100, help='Number of candles')

    args = parser.parse_args()

    try:
        data = fetch_market_snapshot(args.exchange, args.symbol, args.interval, args.limit)

        if not data:
            print("error,no data available")
            return

        # CSV output
        print("open,high,low,close,volume")
        for row in data:
            print(f"{row[0]},{row[1]},{row[2]},{row[3]},{row[4]}")

    except Exception as e:
        print(f"error,{str(e)}")


if __name__ == '__main__':
    main()
