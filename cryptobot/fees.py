"""Fee Calculation Module

Provides fee calculation for various cryptocurrency exchanges.
"""

from typing import Dict


# Exchange fee rates (maker/taker)
# Rates are for perpetual futures/swap trading
EXCHANGE_FEES: Dict[str, Dict[str, float]] = {
    'binance': {
        'maker': 0.0002,  # 0.02% maker fee
        'taker': 0.0005,  # 0.05% taker fee
    },
    'bybit': {
        'maker': 0.0001,  # 0.01% maker fee (VIP0)
        'taker': 0.0006,  # 0.06% taker fee (VIP0)
    },
    'okx': {
        'maker': 0.0002,  # 0.02% maker fee (VIP0)
        'taker': 0.0005,  # 0.05% taker fee (VIP0)
    },
    'bitget': {
        'maker': 0.0002,  # 0.02% maker fee (VIP0)
        'taker': 0.0006,  # 0.06% taker fee (VIP0)
    },
}


def calculate_fee(
    exchange: str,
    position_size: float,
    price: float,
    order_type: str = 'taker'
) -> float:
    """Calculate trading fee for a position

    Args:
        exchange: Exchange name (binance, okx, bybit, bitget)
        position_size: Position size in base currency (e.g., BTC amount)
        price: Entry or exit price
        order_type: Order type ('maker' or 'taker', defaults to 'taker')

    Returns:
        Fee amount in USDT

    Raises:
        ValueError: If exchange is not supported or order_type is invalid

    Examples:
        >>> calculate_fee('binance', 0.5, 50000)
        12.5
        >>> calculate_fee('binance', 0.5, 50000, 'maker')
        5.0
    """
    exchange_lower = exchange.lower()

    if exchange_lower not in EXCHANGE_FEES:
        raise ValueError(
            f"不支持的交易所: {exchange}. "
            f"支持的交易所: {', '.join(EXCHANGE_FEES.keys())}"
        )

    if order_type not in ('maker', 'taker'):
        raise ValueError(f"无效的订单类型: {order_type}. 必须是 'maker' 或 'taker'")

    fee_rate = EXCHANGE_FEES[exchange_lower][order_type]

    # Fee = position_size * price * fee_rate
    # This gives us the fee in the quote currency (USDT)
    notional_value = position_size * price
    fee = notional_value * fee_rate

    return fee


def get_exchange_fee(exchange: str, order_type: str = 'taker') -> float:
    """Get the fee rate for an exchange

    Args:
        exchange: Exchange name
        order_type: Order type ('maker' or 'taker')

    Returns:
        Fee rate as a decimal (e.g., 0.0005 for 0.05%)

    Raises:
        ValueError: If exchange or order_type is invalid
    """
    exchange_lower = exchange.lower()

    if exchange_lower not in EXCHANGE_FEES:
        raise ValueError(
            f"不支持的交易所: {exchange}. "
            f"支持的交易所: {', '.join(EXCHANGE_FEES.keys())}"
        )

    if order_type not in ('maker', 'taker'):
        raise ValueError(f"无效的订单类型: {order_type}. 必须是 'maker' 或 'taker'")

    return EXCHANGE_FEES[exchange_lower][order_type]


def format_fee_percentage(fee_rate: float) -> str:
    """Format fee rate as a percentage string

    Args:
        fee_rate: Fee rate as decimal (e.g., 0.0005)

    Returns:
        Formatted percentage string (e.g., "0.05%")
    """
    return f"{fee_rate * 100:.2f}%"
