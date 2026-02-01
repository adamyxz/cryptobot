"""Price Change Trigger

Triggers trader decisions based on significant price changes.
"""

from datetime import datetime
from typing import Dict, Any, Tuple

from .base import BaseTrigger


class PriceTrigger(BaseTrigger):
    """Trigger based on price changes

    Monitors prices of trader's active positions and triggers
    when price changes exceed the configured threshold.
    """

    def __init__(self, price_change_threshold: float = 0.04):
        """Initialize price trigger

        Args:
            price_change_threshold: Price change threshold (default: 4%)
                                   Trigger fires when |current - last| / last >= threshold
        """
        super().__init__()
        self.threshold = price_change_threshold
        self.price_snapshots: Dict[Tuple[str, str], float] = {}  # (trader_id, symbol) -> price

    async def should_trigger(self, trader_id: str, context: Dict[str, Any]) -> bool:
        """Check if price change exceeds threshold

        Args:
            trader_id: Trader ID
            context: Context dict with 'positions' key containing:
                - 'open': List of open position dicts

        Returns:
            True if any position's price changed by >= threshold
        """
        positions_info = context.get('positions', {})
        open_positions = positions_info.get('open', [])

        if not open_positions:
            # No positions, initialize price snapshots for trader's pairs
            self._initialize_snapshots_for_pairs(trader_id, context)
            return False

        triggered = False

        # Check each position's price
        for pos in open_positions:
            # Support both dict and object positions
            if isinstance(pos, dict):
                symbol = pos.get('symbol')
                current_price = pos.get('current_price')
            else:
                # Position object
                symbol = getattr(pos, 'symbol', None)
                current_price = getattr(pos, 'current_price', None)

            if not symbol or not current_price:
                continue

            key = (trader_id, symbol)
            last_price = self.price_snapshots.get(key)

            if last_price is not None:
                # Calculate price change percentage
                change_pct = abs(current_price - last_price) / last_price

                if change_pct >= self.threshold:
                    # Price changed significantly, trigger
                    self.price_snapshots[key] = current_price
                    triggered = True
                # Else: price change not large enough yet
            else:
                # First time seeing this price, initialize snapshot
                self.price_snapshots[key] = current_price

        return triggered

    def _initialize_snapshots_for_pairs(self, trader_id: str, context: Dict[str, Any]):
        """Initialize price snapshots for trader's trading pairs

        Args:
            trader_id: Trader ID
            context: Context dict
        """
        trader = context.get('trader')
        if not trader:
            return

        trading_pairs = trader.get('trading_pairs', [])

        # Initialize snapshots (will be filled on next price update)
        for symbol in trading_pairs:
            key = (trader_id, symbol)
            if key not in self.price_snapshots:
                # Set to None, will be initialized on first price update
                self.price_snapshots[key] = None

    def update_price_snapshot(self, trader_id: str, symbol: str, price: float):
        """Manually update a price snapshot

        Args:
            trader_id: Trader ID
            symbol: Trading pair symbol
            price: Current price
        """
        key = (trader_id, symbol)
        self.price_snapshots[key] = price

    def get_price_snapshot(self, trader_id: str, symbol: str) -> float:
        """Get the stored price snapshot for a trader/symbol pair

        Args:
            trader_id: Trader ID
            symbol: Trading pair symbol

        Returns:
            Stored price or None if not found
        """
        return self.price_snapshots.get((trader_id, symbol))

    def reset_snapshots(self, trader_id: str):
        """Reset all price snapshots for a trader

        Args:
            trader_id: Trader ID
        """
        # Remove all snapshots for this trader
        keys_to_remove = [k for k in self.price_snapshots.keys() if k[0] == trader_id]
        for key in keys_to_remove:
            del self.price_snapshots[key]

    def set_threshold(self, threshold: float):
        """Update the price change threshold

        Args:
            threshold: New threshold (e.g., 0.04 for 4%)
        """
        if threshold <= 0 or threshold > 1:
            raise ValueError(f"Threshold must be between 0 and 1, got {threshold}")
        self.threshold = threshold

    def get_threshold(self) -> float:
        """Get current threshold

        Returns:
            Current threshold as decimal (e.g., 0.04 for 4%)
        """
        return self.threshold
