"""交易所配置 - 使用 CCXT 统一接口

支持多个交易所的永续合约（perpetual futures/swap）K线数据获取
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
# Legacy API - 保持向后兼容
# =============================================================================

def get_exchange_config(exchange: str) -> Dict[str, Any]:
    """获取交易所配置（兼容旧接口）

    Args:
        exchange: 交易所名称（binance, okx, bybit, bitget）

    Returns:
        交易所配置字典（仅用于兼容）

    Note:
        此函数仅为向后兼容保留，新代码应使用 ccxt_adapter 模块
    """
    return {
        'exchange': exchange,
        'note': 'This is a legacy compatibility wrapper. Use ccxt_adapter instead.',
    }


def get_supported_exchanges() -> List[str]:
    """获取支持的交易所列表

    Returns:
        交易所名称列表
    """
    return ccxt_get_supported_exchanges()


def get_rest_endpoint_config(exchange: str) -> dict:
    """获取 REST API 端点配置（兼容旧接口）

    Args:
        exchange: 交易所名称

    Returns:
        REST API 配置字典
    """
    return {
        'rest_url': None,  # CCXT handles URLs internally
        'parse_rest_kline': ccxt_ohlcv_to_standard,
        'rest_interval_map': None,  # CCXT handles interval mapping
    }


def build_rest_params(exchange: str, symbol: str, interval: str, limit: int) -> dict:
    """构建 REST API 请求参数（兼容旧接口）

    Args:
        exchange: 交易所名称
        symbol: 交易对
        interval: K线周期
        limit: 数据条数

    Returns:
        包含参数的字典
    """
    return {
        'exchange': exchange,
        'symbol': symbol,
        'interval': interval,
        'limit': limit,
    }


async def parse_rest_response_async(exchange: str, response: list, symbol: str, interval: str) -> list:
    """解析 REST API 响应（异步版本）

    Args:
        exchange: 交易所名称
        response: CCXT 返回的 OHLCV 数据列表
        symbol: 交易对
        interval: K线周期

    Returns:
        标准化的 K线数据列表
    """
    klines = []
    for ohlcv in response:
        kline = ccxt_ohlcv_to_standard(exchange, symbol, interval, ohlcv)
        if kline:
            klines.append(kline)
    return klines


def parse_rest_response(exchange: str, response: list, symbol: str, interval: str) -> list:
    """解析 REST API 响应（同步版本 - 实际上会被异步调用）

    Args:
        exchange: 交易所名称
        response: CCXT 返回的 OHLCV 数据列表
        symbol: 交易对
        interval: K线周期

    Returns:
        标准化的 K线数据列表
    """
    # This will be replaced by async version in actual usage
    return []


# =============================================================================
# 新的 CCXT 接口
# =============================================================================

async def fetch_klines_ccxt(exchange: str, symbol: str, interval: str, limit: int) -> list:
    """使用 CCXT 获取历史 K线数据

    Args:
        exchange: 交易所名称
        symbol: 交易对（用户输入格式，如 BTCUSDT）
        interval: K线周期（1m, 5m, 1h, 1d 等）
        limit: 获取条数

    Returns:
        标准化的 K线数据列表

    Raises:
        ValueError: 交易所不支持或交易对不存在
        RuntimeError: 获取数据失败
    """
    try:
        klines = await ccxt_fetch_ohlcv(exchange, symbol, interval, limit)
        return klines
    except ValueError as e:
        raise e
    except Exception as e:
        raise RuntimeError(f"获取K线数据失败: {e}")


async def fetch_pairs_ccxt(exchange: str) -> List[Dict]:
    """使用 CCXT 获取交易所的永续合约交易对

    Args:
        exchange: 交易所名称

    Returns:
        交易对信息列表

    Raises:
        ValueError: 交易所不支持
        RuntimeError: 获取数据失败
    """
    try:
        markets = await ccxt_fetch_swap_markets(exchange)
        return markets
    except ValueError as e:
        raise e
    except Exception as e:
        raise RuntimeError(f"获取交易对列表失败: {e}")


# =============================================================================
# 错误提示
# =============================================================================

REGION_ERROR_HINTS = {
    "binance": "Binance 在某些地区可能不可用。您可以尝试其他交易所如 bybit 或 bitget。",
    "okx": "OKX 连接失败。请检查网络或尝试其他交易所。",
    "bybit": "Bybit 连接失败。请检查网络连接。",
    "bitget": "Bitget 连接失败。请检查网络连接。",
}


def get_region_hint(exchange: str, error_code: int = None) -> str:
    """获取地区错误提示

    Args:
        exchange: 交易所名称
        error_code: HTTP 错误码

    Returns:
        提示信息
    """
    exchange = exchange.lower()
    if error_code == 451 and exchange in REGION_ERROR_HINTS:
        return REGION_ERROR_HINTS[exchange]
    return REGION_ERROR_HINTS.get(exchange, "")


# =============================================================================
# 导出符号（保持向后兼容）
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
