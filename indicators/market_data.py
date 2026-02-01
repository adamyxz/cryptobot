"""Fetch market data snapshot with technical indicators

Usage:
    python indicators/market_data.py --exchange binance --symbol BTCUSDT --interval 1h

Output: CSV format (open,high,low,close,volume,rsi,trend,support,resistance)
"""

import ccxt
import argparse
from typing import List, Tuple
from pathlib import Path
import statistics


def calculate_rsi(prices: List[float], period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0

    gains = []
    losses = []

    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = statistics.mean(gains[-period:]) if len(gains) >= period else 0
    avg_loss = statistics.mean(losses[-period:]) if len(losses) >= period else 0

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)


def detect_trend(prices: List[float]) -> str:
    if len(prices) < 5:
        return 'unknown'

    recent = prices[-5:]
    if all(recent[i] <= recent[i + 1] for i in range(len(recent) - 1)):
        return 'uptrend'
    elif all(recent[i] >= recent[i + 1] for i in range(len(recent) - 1)):
        return 'downtrend'
    else:
        return 'sideways'


def find_support_resistance(prices: List[float], current_price: float) -> Tuple[float, float]:
    if len(prices) < 10:
        return 0, 0

    local_mins = []
    local_maxs = []

    for i in range(2, len(prices) - 2):
        if (prices[i] < prices[i - 1] and prices[i] < prices[i + 1] and
            prices[i] < prices[i - 2] and prices[i] < prices[i + 2]):
            if prices[i] < current_price:
                local_mins.append(prices[i])

        if (prices[i] > prices[i - 1] and prices[i] > prices[i + 1] and
            prices[i] > prices[i - 2] and prices[i] > prices[i + 2]):
            if prices[i] > current_price:
                local_maxs.append(prices[i])

    support = max(local_mins) if local_mins else 0
    resistance = min(local_maxs) if local_maxs else 0

    return round(support, 2), round(resistance, 2)


def fetch_market_snapshot(exchange: str, symbol: str, interval: str = '1h', limit: int = 100) -> List[Tuple]:
    """
    Fetch market data snapshot

    Args:
        exchange: Exchange name
        symbol: Trading symbol
        interval: Timeframe
        limit: Number of candles

    Returns:
        List of tuples (open, high, low, close, volume, rsi, trend, support, resistance)
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

        close_prices = [candle[4] for candle in ohlcv]
        current_price = close_prices[-1]

        # Calculate indicators based on all data
        rsi = calculate_rsi(close_prices)
        trend = detect_trend(close_prices)
        support, resistance = find_support_resistance(close_prices, current_price)

        # Return last N candles with indicators
        result = []
        for candle in ohlcv[-limit:]:
            result.append((
                round(candle[1], 2),  # open
                round(candle[2], 2),  # high
                round(candle[3], 2),  # low
                round(candle[4], 2),  # close
                round(candle[5], 2),  # volume
                rsi,
                trend,
                support,
                resistance
            ))

        return result

    finally:
        exchange_inst.close()


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
        print("open,high,low,close,volume,rsi,trend,support,resistance")
        for row in data:
            print(f"{row[0]},{row[1]},{row[2]},{row[3]},{row[4]},{row[5]},{row[6]},{row[7]},{row[8]}")

    except Exception as e:
        print(f"error,{str(e)}")


if __name__ == '__main__':
    main()
