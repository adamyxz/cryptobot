"""Exchange Configuration - Using CCXT Unified Interface

Supports K-line data retrieval for perpetual futures/swap from multiple exchanges
"""

from typing import Callable, Dict, Any, List
from .ccxt_adapter import (
    get_supported_exchanges as ccxt_get_supported_exchanges,
    create_exchange_instance,
    convert_user_symbol_to_ccxt,
    find_matching_swap_market,
    ccxt_ohlcv_to_standard,
    fetch_ohlcv as ccxt_fetch_ohlcv,
    fetch_swap_markets as ccxt_fetch_swap_markets,
    get_supported_timeframes,
)


# =============================================================================
# Legacy API - Maintain backward compatibility
# =============================================================================

def get_exchange_config(exchange: str) -> Dict[str, Any]:
    """Get exchange configuration (compatible with old interface)

    Args:
        exchange: Exchange name (binance, okx, bybit, bitget)

    Returns:
        Exchange configuration dictionary (for compatibility only)

    Note:
        This function is kept for backward compatibility only.
        New code should use the ccxt_adapter module
    """
    return {
        'exchange': exchange,
        'note': 'This is a legacy compatibility wrapper. Use ccxt_adapter instead.',
    }


def get_supported_exchanges() -> List[str]:
    """Get list of supported exchanges

    Returns:
        List of exchange names
    """
    return ccxt_get_supported_exchanges()


def get_rest_endpoint_config(exchange: str) -> dict:
    """Get REST API endpoint configuration (compatible with old interface)

    Args:
        exchange: Exchange name

    Returns:
        REST API configuration dictionary
    """
    return {
        'rest_url': None,  # CCXT handles URLs internally
        'parse_rest_kline': ccxt_ohlcv_to_standard,
        'rest_interval_map': None,  # CCXT handles interval mapping
    }


def build_rest_params(exchange: str, symbol: str, interval: str, limit: int) -> dict:
    """Build REST API request parameters (compatible with old interface)

    Args:
        exchange: Exchange name
        symbol: Trading pair
        interval: K-line interval
        limit: Number of records

    Returns:
        Dictionary containing parameters
    """
    return {
        'exchange': exchange,
        'symbol': symbol,
        'interval': interval,
        'limit': limit,
    }


async def parse_rest_response_async(exchange: str, response: list, symbol: str, interval: str) -> list:
    """Parse REST API response (async version)

    Args:
        exchange: Exchange name
        response: OHLCV data list returned by CCXT
        symbol: Trading pair
        interval: K-line interval

    Returns:
        Standardized K-line data list
    """
    klines = []
    for ohlcv in response:
        kline = ccxt_ohlcv_to_standard(exchange, symbol, interval, ohlcv)
        if kline:
            klines.append(kline)
    return klines


def parse_rest_response(exchange: str, response: list, symbol: str, interval: str) -> list:
    """Parse REST API response (sync version - will be called asynchronously)

    Args:
        exchange: Exchange name
        response: OHLCV data list returned by CCXT
        symbol: Trading pair
        interval: K-line interval

    Returns:
        Standardized K-line data list
    """
    # This will be replaced by async version in actual usage
    return []


# =============================================================================
# New CCXT Interface
# =============================================================================

async def fetch_klines_ccxt(exchange: str, symbol: str, interval: str, limit: int) -> list:
    """Fetch historical K-line data using CCXT

    Args:
        exchange: Exchange name
        symbol: Trading pair (user input format, e.g., BTCUSDT)
        interval: K-line interval (1m, 5m, 1h, 1d, etc.)
        limit: Number of records to fetch

    Returns:
        Standardized K-line data list

    Raises:
        ValueError: Exchange not supported or trading pair doesn't exist
        RuntimeError: Failed to fetch data
    """
    try:
        klines = await ccxt_fetch_ohlcv(exchange, symbol, interval, limit)
        return klines
    except ValueError as e:
        raise e
    except Exception as e:
        raise RuntimeError(f"Failed to fetch K-line data: {e}")


async def fetch_pairs_ccxt(exchange: str) -> List[Dict]:
    """Fetch perpetual futures trading pairs from exchange using CCXT

    Args:
        exchange: Exchange name

    Returns:
        Trading pair information list

    Raises:
        ValueError: Exchange not supported
        RuntimeError: Failed to fetch data
    """
    try:
        markets = await ccxt_fetch_swap_markets(exchange)
        return markets
    except ValueError as e:
        raise e
    except Exception as e:
        raise RuntimeError(f"Failed to fetch trading pairs list: {e}")


# =============================================================================
# Error Messages
# =============================================================================

REGION_ERROR_HINTS = {
    "binance": "Binance may not be available in certain regions. You can try other exchanges like bybit or bitget.",
    "okx": "OKX connection failed. Please check your network or try other exchanges.",
    "bybit": "Bybit connection failed. Please check your network connection.",
    "bitget": "Bitget connection failed. Please check your network connection.",
}


def get_region_hint(exchange: str, error_code: int = None) -> str:
    """Get region error hint

    Args:
        exchange: Exchange name
        error_code: HTTP error code

    Returns:
        Hint message
    """
    exchange = exchange.lower()
    if error_code == 451 and exchange in REGION_ERROR_HINTS:
        return REGION_ERROR_HINTS[exchange]
    return REGION_ERROR_HINTS.get(exchange, "")


# =============================================================================
# Exported Symbols (maintain backward compatibility)
# =============================================================================

__all__ = [
    # Legacy compatibility
    'get_exchange_config',
    'get_supported_exchanges',
    'get_rest_endpoint_config',
    'build_rest_params',
    'parse_rest_response',
    'parse_rest_response_async',
    'get_region_hint',

    # New CCXT interface
    'fetch_klines_ccxt',
    'fetch_pairs_ccxt',
]
