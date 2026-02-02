"""Fetch long/short ratio history for perpetual futures.

The long/short ratio shows the proportion of long positions vs short positions,
which can be used as a sentiment indicator.

Usage:
    python indicators/longshortratio.py --exchange binance --symbol BTCUSDT --period 5m --limit 100

Output: CSV format (long_account,short_account,long_position,short_position)
"""

import ccxt
import argparse
from typing import List, Tuple
from pathlib import Path


def fetch_longshortratio(
    exchange: str,
    symbol: str,
    period: str = '5m',
    limit: int = 100
) -> List[Tuple]:
    """
    Fetch long/short ratio history from exchange.

    Args:
        exchange: Exchange name (binance, okx, bybit, bitget)
        symbol: Trading symbol (e.g., BTCUSDT)
        period: Time period for the ratio data (5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d)
        limit: Number of data points to fetch

    Returns:
        List of tuples (long_account, short_account, long_position, short_position)
        - long_account: Ratio of long accounts to total accounts
        - short_account: Ratio of short accounts to total accounts
        - long_position: Ratio of long positions to total positions
        - short_position: Ratio of short positions to total positions
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from cryptobot.ccxt_adapter import (
        EXCHANGE_MAP,
        convert_user_symbol_to_ccxt,
        TIMEFRAME_MAP
    )

    # Use the correct exchange class from EXCHANGE_MAP
    exchange_lower = exchange.lower()
    if exchange_lower not in EXCHANGE_MAP:
        raise ValueError(
            f"Exchange '{exchange}' not supported. "
            f"Supported exchanges: {', '.join(EXCHANGE_MAP.keys())}"
        )

    exchange_class = EXCHANGE_MAP[exchange_lower]
    exchange_inst = exchange_class({'enableRateLimit': True})

    try:
        ccxt_symbol = convert_user_symbol_to_ccxt(exchange, symbol)
        ccxt_period = TIMEFRAME_MAP.get(period, period)

        # Check if exchange supports this method
        if not hasattr(exchange_inst, 'fetch_long_short_ratio_history'):
            raise ValueError(
                f"Exchange '{exchange}' does not support fetch_long_short_ratio_history. "
                f"Supported exchanges: binance, OKX (limited support)"
            )

        # Fetch long/short ratio history
        ratio_data = exchange_inst.fetch_long_short_ratio_history(
            ccxt_symbol,
            timeframe=ccxt_period,
            limit=limit
        )

        if not ratio_data:
            return []

        # Process and return data
        result = []
        for item in ratio_data:
            # Extract data from CCXT response structure
            if isinstance(item, dict):
                # CCXT returns data with 'info' field containing exchange-specific data
                info = item.get('info', {})

                # Binance format
                if 'longAccount' in info:
                    long_account = float(info.get('longAccount', 0))
                    short_account = float(info.get('shortAccount', 0))

                    # For global account ratio, there might not be position data
                    # Try to get position data if available
                    long_position = float(info.get('longPosition', 0))
                    short_position = float(info.get('shortPosition', 0))

                    # If position data is not available (only account ratio),
                    # calculate from longShortRatio if present
                    if long_position == 0 and short_position == 0:
                        ratio = float(info.get('longShortRatio', 0))
                        if ratio > 0:
                            # Approximate position ratio from account ratio
                            # long_position = ratio / (1 + ratio)
                            # short_position = 1 / (1 + ratio)
                            long_position = round(ratio / (1 + ratio), 4)
                            short_position = round(1 / (1 + ratio), 4)
                # Generic format with separate long/short objects
                elif 'long' in item and 'short' in item:
                    long_val = item.get('long', {})
                    short_val = item.get('short', {})
                    long_account = float(long_val.get('account', 0) if isinstance(long_val, dict) else long_val)
                    short_account = float(short_val.get('account', 0) if isinstance(short_val, dict) else short_val)
                    long_position = float(long_val.get('position', 0) if isinstance(long_val, dict) else 0)
                    short_position = float(short_val.get('position', 0) if isinstance(short_val, dict) else 0)
                # Simple ratio values
                else:
                    long_account = float(item.get('long_account', item.get('long_ratio', 0)))
                    short_account = float(item.get('short_account', item.get('short_ratio', 0)))
                    long_position = float(item.get('long_position', item.get('long_position_ratio', 0)))
                    short_position = float(item.get('short_position', item.get('short_position_ratio', 0)))
            else:
                # Handle list/tuple format (fallback)
                long_account = float(item[0]) if len(item) > 0 else 0
                short_account = float(item[1]) if len(item) > 1 else 0
                long_position = float(item[2]) if len(item) > 2 else 0
                short_position = float(item[3]) if len(item) > 3 else 0

            result.append((
                round(long_account, 4),
                round(short_account, 4),
                round(long_position, 4),
                round(short_position, 4),
            ))

        return result

    finally:
        # Note: ccxt sync exchanges don't have a close() method
        # The connection will be cleaned up automatically
        pass


def main():
    parser = argparse.ArgumentParser(
        description='Fetch long/short ratio history from exchange'
    )
    parser.add_argument('--exchange', required=True, help='Exchange name')
    parser.add_argument('--symbol', required=True, help='Trading symbol')
    parser.add_argument(
        '--period',
        default='5m',
        help='Time period (5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='Number of data points to fetch'
    )

    args = parser.parse_args()

    try:
        data = fetch_longshortratio(
            args.exchange,
            args.symbol,
            args.period,
            args.limit
        )

        if not data:
            print("error,no data available")
            return

        # CSV output
        print("long_account,short_account,long_position,short_position")
        for row in data:
            print(f"{row[0]},{row[1]},{row[2]},{row[3]}")

    except Exception as e:
        print(f"error,{str(e)}")


if __name__ == '__main__':
    main()
