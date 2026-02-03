"""Price Update Service

Fetches current prices from exchanges and updates position PnL.
"""

import asyncio
import time
from typing import Dict, Optional, List
from datetime import datetime

import ccxt

from .ccxt_adapter import create_exchange_instance, convert_user_symbol_to_ccxt
from .position_db import PositionDatabase
from .position import Position


class PriceUpdateService:
    """Service for fetching current prices and updating positions"""

    def __init__(self, cache_ttl: int = 5):
        """Initialize the price update service

        Args:
            cache_ttl: Cache time-to-live in seconds (default: 5)
        """
        self.cache_ttl = cache_ttl
        self.price_cache: Dict[str, tuple[float, float]] = {}  # key: (price, timestamp)

    def _make_cache_key(self, exchange: str, symbol: str) -> str:
        """Create a cache key for the exchange/symbol pair

        Args:
            exchange: Exchange name
            symbol: Trading symbol (user format, e.g., BTCUSDT)

        Returns:
            Cache key string
        """
        return f"{exchange.lower()}:{symbol.upper()}"

    async def fetch_current_price(self, exchange: str, symbol: str) -> float:
        """Fetch current price from exchange with caching

        Args:
            exchange: Exchange name (binance, okx, bybit, bitget)
            symbol: Trading symbol (user format, e.g., BTCUSDT)

        Returns:
            Current price

        Raises:
            ValueError: If exchange not supported or symbol not found
            RuntimeError: If fetching price fails
        """
        cache_key = self._make_cache_key(exchange, symbol)

        # Check cache
        if cache_key in self.price_cache:
            cached_price, cached_time = self.price_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return cached_price

        # Create exchange instance
        exchange_instance = create_exchange_instance(exchange)

        # Convert symbol to CCXT format
        ccxt_symbol = convert_user_symbol_to_ccxt(exchange, symbol)

        # Fetch ticker
        try:
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(
                None,
                lambda: exchange_instance.fetch_ticker(ccxt_symbol)
            )
        except Exception as e:
            raise RuntimeError(f"Failed to fetch price {exchange} {symbol}: {e}")

        current_price = ticker.get('last')
        if current_price is None or current_price <= 0:
            raise RuntimeError(f"Invalid price: {current_price}")

        # Update cache
        self.price_cache[cache_key] = (float(current_price), time.time())

        return float(current_price)

    async def update_trader_positions(self, trader_id: str, db: PositionDatabase) -> List[Position]:
        """Update all open positions for a trader with current prices

        Args:
            trader_id: Trader ID
            db: PositionDatabase instance

        Returns:
            List of updated Position objects

        Raises:
            RuntimeError: If fetching prices or updating fails
        """
        # Get configured exchange from config
        from .scheduler_config import get_scheduler_config
        config = get_scheduler_config()
        configured_exchange = config.get_string('indicator.exchange', 'okx')

        # Get all open positions for the trader
        positions = db.list_positions(trader_id, status='open')

        if not positions:
            return []

        updated_positions = []

        # Group positions by exchange and symbol to minimize API calls
        price_cache: Dict[tuple, float] = {}

        for position in positions:
            # Use configured exchange instead of position's saved exchange
            cache_key = (configured_exchange, position.symbol)

            # Fetch price if not already cached
            if cache_key not in price_cache:
                try:
                    current_price = await self.fetch_current_price(
                        configured_exchange,
                        position.symbol
                    )
                    price_cache[cache_key] = current_price
                except Exception as e:
                    # Log error but continue with other positions
                    print(f"Warning: Failed to fetch price for {configured_exchange} {position.symbol}: {e}")
                    continue

            current_price = price_cache[cache_key]

            # Update position PnL
            success = db.update_position_pnl(position.id, current_price)

            if success:
                # Reload position to get updated values
                updated_position = db.get_position(position.id)
                if updated_position:
                    updated_positions.append(updated_position)

                    # Check for liquidation after price update
                    if updated_position.is_liquidated(current_price):
                        from .liquidation_monitor import check_liquidation_for_position
                        await check_liquidation_for_position(position.id)
                        print(f"[red]Position {position.id} has been liquidated at {current_price}[/red]")

        return updated_positions

    async def update_single_position(self, position_id: int, db: PositionDatabase) -> Optional[Position]:
        """Update a single position with current price

        Args:
            position_id: Position ID
            db: PositionDatabase instance

        Returns:
            Updated Position object or None if failed
        """
        # Get configured exchange from config
        from .scheduler_config import get_scheduler_config
        config = get_scheduler_config()
        configured_exchange = config.get_string('indicator.exchange', 'okx')

        position = db.get_position(position_id)

        if not position or position.status != 'open':
            return None

        try:
            current_price = await self.fetch_current_price(
                configured_exchange,
                position.symbol
            )

            success = db.update_position_pnl(position_id, current_price)

            if success:
                updated_position = db.get_position(position_id)

                # Check for liquidation after price update
                if updated_position and updated_position.is_liquidated(current_price):
                    from .liquidation_monitor import check_liquidation_for_position
                    await check_liquidation_for_position(position_id)
                    print(f"[red]Position {position_id} has been liquidated at {current_price}[/red]")
                    return None  # Position was liquidated

                return updated_position

        except Exception as e:
            print(f"Warning: Failed to update position {position_id}: {e}")

        return None

    def clear_cache(self):
        """Clear the price cache"""
        self.price_cache.clear()

    def get_cached_price(self, exchange: str, symbol: str) -> Optional[float]:
        """Get cached price if available and not expired

        Args:
            exchange: Exchange name
            symbol: Trading symbol

        Returns:
            Cached price or None if not available/expired
        """
        cache_key = self._make_cache_key(exchange, symbol)

        if cache_key in self.price_cache:
            cached_price, cached_time = self.price_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return cached_price

        return None

    async def fetch_multiple_prices(self, exchange_symbol_pairs: List[tuple]) -> Dict[tuple, float]:
        """Fetch prices for multiple exchange/symbol pairs in parallel

        Args:
            exchange_symbol_pairs: List of (exchange, symbol) tuples

        Returns:
            Dictionary mapping (exchange, symbol) to price
        """
        results = {}

        # Create tasks for parallel fetching
        tasks = []
        for exchange, symbol in exchange_symbol_pairs:
            task = self.fetch_current_price(exchange, symbol)
            tasks.append(((exchange, symbol), task))

        # Execute all tasks concurrently
        completed = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)

        # Collect results
        for ((exchange, symbol), result) in zip([item for item, _ in tasks], completed):
            if isinstance(result, Exception):
                print(f"Warning: Failed to fetch price for {exchange} {symbol}: {result}")
            else:
                results[(exchange, symbol)] = result

        return results


# Singleton instance for convenient access
_default_service: Optional[PriceUpdateService] = None


def get_price_service(cache_ttl: int = 5) -> PriceUpdateService:
    """Get the default price update service instance

    Args:
        cache_ttl: Cache time-to-live in seconds (only used on first call)

    Returns:
        PriceUpdateService instance
    """
    global _default_service
    if _default_service is None:
        _default_service = PriceUpdateService(cache_ttl=cache_ttl)
    return _default_service
