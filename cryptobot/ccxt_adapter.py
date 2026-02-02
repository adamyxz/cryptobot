"""CCXT Adapter for Perpetual Futures Trading

Provides unified interface to multiple exchanges for perpetual swap (futures) data.
"""

import ccxt
from typing import Dict, List, Optional, Any
import asyncio
from datetime import datetime


# Exchange class mapping for perpetual futures
EXCHANGE_MAP = {
    'binance': ccxt.binanceusdm,      # Binance USDT-M perpetual futures
    'okx': ccxt.okx,                  # OKX futures/swap
    'bybit': ccxt.bybit,              # Bybit derivatives
    'bitget': ccxt.bitget,            # Bitget futures
}


# Timeframe mapping (user-friendly to CCXT format)
TIMEFRAME_MAP = {
    '1m': '1m',
    '3m': '3m',
    '5m': '5m',
    '15m': '15m',
    '30m': '30m',
    '1h': '1h',
    '2h': '2h',
    '4h': '4h',
    '6h': '6h',
    '12h': '12h',
    '1d': '1d',
    '1w': '1w',
    '1M': '1M',
}


def convert_user_symbol_to_ccxt(exchange: str, user_symbol: str) -> str:
    """Convert user input symbol to CCXT perpetual futures format

    Args:
        exchange: Exchange name (binance, okx, bybit, bitget)
        user_symbol: User input symbol (e.g., BTCUSDT)

    Returns:
        CCXT format symbol for the exchange

    Examples:
        >>> convert_user_symbol_to_ccxt('binance', 'BTCUSDT')
        'BTC/USDT:USDT'
        >>> convert_user_symbol_to_ccxt('okx', 'BTCUSDT')
        'BTC-USDT-SWAP'
        >>> convert_user_symbol_to_ccxt('bybit', 'BTCUSDT')
        'BTCUSDT'
    """
    exchange_lower = exchange.lower()

    # Bybit and Bitget use the same format as user input
    if exchange_lower in ['bybit', 'bitget']:
        return user_symbol.upper()

    # Binance perpetual futures: BTCUSDT -> BTC/USDT:USDT
    if exchange_lower == 'binance':
        if user_symbol.endswith('USDT'):
            base = user_symbol[:-4]
            return f"{base}/USDT:USDT"
        return user_symbol

    # OKX perpetual futures: BTCUSDT -> BTC-USDT-SWAP
    if exchange_lower == 'okx':
        if user_symbol.endswith('USDT'):
            base = user_symbol[:-4]
            return f"{base}-USDT-SWAP"
        return user_symbol

    return user_symbol


def _find_matching_swap_market_sync(exchange, user_symbol: str) -> str:
    """Synchronous version of find_matching_swap_market

    Args:
        exchange: Sync CCXT exchange instance
        user_symbol: User input symbol (e.g., BTCUSDT)

    Returns:
        Matched CCXT symbol

    Raises:
        ValueError: If no matching perpetual futures market found
    """
    # Load markets (synchronous)
    markets = exchange.load_markets()

    # Normalize the user symbol by removing common quote currencies
    normalized_user = user_symbol.upper()

    # Try to convert to CCXT format first
    exchange_name = exchange.id.lower()

    # Try different conversions based on exchange
    possible_formats = [user_symbol]

    if exchange_name == 'binance':
        # Binance USD-M: BTCUSDT -> BTC/USDT:USDT
        if user_symbol.endswith('USDT'):
            base = user_symbol[:-4]
            possible_formats.append(f"{base}/USDT:USDT")
            # Also try without the suffix
            possible_formats.append(base)
    elif exchange_name == 'okx':
        # OKX: BTCUSDT -> BTC-USDT-SWAP or BTC/USDT:USDT
        if user_symbol.endswith('USDT'):
            base = user_symbol[:-4]
            possible_formats.append(f"{base}/USDT:USDT")
            possible_formats.append(f"{base}-USDT-SWAP")

    # Try each format
    for fmt in possible_formats:
        if fmt in markets:
            market = markets[fmt]
            if market.get('type') == 'swap':
                return fmt

    # Strategy 1: Extract base currency from user symbol
    # Common quote currencies
    quote_currencies = ['USDT', 'USDC', 'USD', 'BTC', 'ETH']
    base_currency = None
    quote_currency = None

    for quote in quote_currencies:
        if user_symbol.endswith(quote):
            base_currency = user_symbol[:-len(quote)]
            quote_currency = quote
            break

    if base_currency and quote_currency:
        # Search for matching swap market
        for symbol, market in markets.items():
            if market.get('type') == 'swap':
                m_base = market.get('base', '').upper()
                m_quote = market.get('quote', '').upper()
                m_settle = market.get('settle', '').upper()

                # Match base and quote
                if m_base == base_currency and m_quote == quote_currency:
                    return symbol

    # Strategy 2: Try substring matching (less precise but fallback)
    normalized_user_simple = user_symbol.replace('/', '').replace('-', '').replace(':', '').replace('SWAP', '')
    for symbol, market in markets.items():
        if market.get('type') == 'swap':
            normalized_symbol = symbol.replace('/', '').replace('-', '').replace(':', '').replace('SWAP', '')
            # Remove duplicate settle currency (e.g., USDT:USDT -> USDT)
            # This is tricky, so let's just do a prefix match
            if normalized_symbol.startswith(normalized_user_simple[:6]):  # First 6 chars should match
                return symbol

    raise ValueError(f"Perpetual futures trading pair not found: {user_symbol}")


async def find_matching_swap_market(exchange, user_symbol: str) -> str:
    """Find matching perpetual futures market in exchange (async version)

    Args:
        exchange: CCXT exchange instance (sync or async)
        user_symbol: User input symbol (e.g., BTCUSDT)

    Returns:
        Matched CCXT symbol

    Raises:
        ValueError: If no matching perpetual futures market found
    """
    # Load markets (works for both sync and async exchanges)
    markets = await exchange.load_markets()

    # Normalize the user symbol by removing common quote currencies
    normalized_user = user_symbol.upper()

    # Try to convert to CCXT format first
    exchange_name = exchange.id.lower()

    # Try different conversions based on exchange
    possible_formats = [user_symbol]

    if exchange_name == 'binance':
        # Binance USD-M: BTCUSDT -> BTC/USDT:USDT
        if user_symbol.endswith('USDT'):
            base = user_symbol[:-4]
            possible_formats.append(f"{base}/USDT:USDT")
            # Also try without the suffix
            possible_formats.append(base)
    elif exchange_name == 'okx':
        # OKX: BTCUSDT -> BTC-USDT-SWAP or BTC/USDT:USDT
        if user_symbol.endswith('USDT'):
            base = user_symbol[:-4]
            possible_formats.append(f"{base}/USDT:USDT")
            possible_formats.append(f"{base}-USDT-SWAP")

    # Try each format
    for fmt in possible_formats:
        if fmt in markets:
            market = markets[fmt]
            if market.get('type') == 'swap':
                return fmt

    # Try to find by normalizing symbol (remove ALL separators including colons)
    # This handles: BTC/USDT:USDT -> BTCUSDTUSDT
    # And: BTC-USDT-SWAP -> BTCUSDTSWAP
    # So we need to be smarter about it

    # Strategy 1: Extract base currency from user symbol
    # Common quote currencies
    quote_currencies = ['USDT', 'USDC', 'USD', 'BTC', 'ETH']
    base_currency = None
    quote_currency = None

    for quote in quote_currencies:
        if user_symbol.endswith(quote):
            base_currency = user_symbol[:-len(quote)]
            quote_currency = quote
            break

    if base_currency and quote_currency:
        # Search for matching swap market
        for symbol, market in markets.items():
            if market.get('type') == 'swap':
                m_base = market.get('base', '').upper()
                m_quote = market.get('quote', '').upper()
                m_settle = market.get('settle', '').upper()

                # Match base and quote
                if m_base == base_currency and m_quote == quote_currency:
                    return symbol

    # Strategy 2: Try substring matching (less precise but fallback)
    normalized_user_simple = user_symbol.replace('/', '').replace('-', '').replace(':', '').replace('SWAP', '')
    for symbol, market in markets.items():
        if market.get('type') == 'swap':
            normalized_symbol = symbol.replace('/', '').replace('-', '').replace(':', '').replace('SWAP', '')
            # Remove duplicate settle currency (e.g., USDT:USDT -> USDT)
            # This is tricky, so let's just do a prefix match
            if normalized_symbol.startswith(normalized_user_simple[:6]):  # First 6 chars should match
                return symbol

    raise ValueError(f"Perpetual futures trading pair not found: {user_symbol}")


def create_exchange_instance(exchange: str, config: Optional[Dict] = None) -> ccxt.Exchange:
    """Create CCXT exchange instance configured for perpetual futures

    Args:
        exchange: Exchange name (binance, okx, bybit, bitget)
        config: Optional additional configuration

    Returns:
        Configured CCXT exchange instance

    Raises:
        ValueError: If exchange is not supported
    """
    exchange_lower = exchange.lower()

    if exchange_lower not in EXCHANGE_MAP:
        raise ValueError(
            f"Unsupported exchange: {exchange}. "
            f"Supported exchanges: {', '.join(EXCHANGE_MAP.keys())}"
        )

    exchange_class = EXCHANGE_MAP[exchange_lower]

    # Base configuration for perpetual futures
    base_config = {
        'options': {
            'defaultType': 'swap',  # Use perpetual futures/swap markets
        },
        'enableRateLimit': True,
    }

    # Merge with user config
    if config:
        base_config.update(config)

    return exchange_class(base_config)


def ccxt_ohlcv_to_standard(exchange: str, symbol: str, interval: str, ohlcv: list) -> Dict:
    """Convert CCXT OHLCV data to standard format

    Args:
        exchange: Exchange name
        symbol: Trading symbol
        interval: Time interval
        ohlcv: CCXT OHLCV data [timestamp, open, high, low, close, volume]

    Returns:
        Standardized K-line data dictionary
    """
    if len(ohlcv) < 6:
        return {}

    timestamp, open_price, high, low, close, volume = ohlcv[:6]

    return {
        "exchange": exchange,
        "symbol": symbol,
        "timestamp": timestamp,
        "open": float(open_price),
        "high": float(high),
        "low": float(low),
        "close": float(close),
        "volume": float(volume),
        "is_closed": True,  # REST API data is always closed
        "interval": interval,
    }


async def fetch_ohlcv(
    exchange: str,
    symbol: str,
    interval: str,
    limit: int = 100,
) -> List[Dict]:
    """Fetch historical OHLCV data using CCXT

    Args:
        exchange: Exchange name
        symbol: Trading symbol (user format)
        interval: Time interval
        limit: Number of candles to fetch

    Returns:
        List of standardized K-line dictionaries

    Raises:
        ValueError: If exchange not supported or symbol not found
    """
    # Create exchange instance
    exchange_instance = create_exchange_instance(exchange)

    # Convert symbol and find matching market (use sync version)
    try:
        ccxt_symbol = _find_matching_swap_market_sync(exchange_instance, symbol)
    except ValueError as e:
        raise ValueError(str(e))

    # Convert interval
    ccxt_interval = TIMEFRAME_MAP.get(interval, interval)

    # Fetch OHLCV data (CCXT fetch_ohlcv is synchronous, so run in executor)
    try:
        loop = asyncio.get_event_loop()
        ohlcv = await loop.run_in_executor(
            None,
            lambda: exchange_instance.fetch_ohlcv(
                ccxt_symbol,
                timeframe=ccxt_interval,
                limit=limit,
            )
        )
    except Exception as e:
        raise RuntimeError(f"Failed to fetch data: {e}")

    # Convert to standard format
    klines = []
    for candle in ohlcv:
        kline = ccxt_ohlcv_to_standard(exchange, symbol, interval, candle)
        if kline:
            klines.append(kline)

    return klines


async def fetch_swap_markets(exchange: str) -> List[Dict]:
    """Fetch all perpetual futures markets from exchange

    Args:
        exchange: Exchange name

    Returns:
        List of market info dictionaries with symbol, volume, etc.

    Raises:
        ValueError: If exchange not supported
    """
    # Create exchange instance
    exchange_instance = create_exchange_instance(exchange)

    # Load markets (synchronous in CCXT)
    try:
        markets = exchange_instance.load_markets()
    except Exception as e:
        raise RuntimeError(f"Failed to load market data: {e}")

    # Filter only swap (perpetual) markets
    swap_markets = []
    for symbol, market in markets.items():
        if market.get('type') == 'swap':
            swap_markets.append({
                'symbol': symbol,
                'base': market.get('base'),
                'quote': market.get('quote'),
                'settle': market.get('settle'),
                'active': market.get('active', True),
                'contract': True,  # It's a perpetual futures contract
            })

    return swap_markets


def get_supported_exchanges() -> List[str]:
    """Get list of supported exchanges

    Returns:
        List of exchange names
    """
    return list(EXCHANGE_MAP.keys())


def get_supported_timeframes() -> Dict[str, str]:
    """Get mapping of supported timeframes

    Returns:
        Dictionary mapping user-friendly format to CCXT format
    """
    return TIMEFRAME_MAP.copy()
