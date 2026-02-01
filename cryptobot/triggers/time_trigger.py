"""Time-Based Trigger

Triggers trader decisions based on configured timeframes.
"""

from datetime import datetime, timedelta
from typing import Dict, Any

from .base import BaseTrigger


class TimeTrigger(BaseTrigger):
    """Trigger based on trader's configured timeframes

    Checks if enough time has passed since the last trigger
    based on the trader's configured timeframes (e.g., '1h', '4h', '1d').
    """

    # Timeframe to seconds mapping
    TIMEFRAME_SECONDS = {
        '1m': 60,
        '3m': 180,
        '5m': 300,
        '15m': 900,
        '30m': 1800,
        '1h': 3600,
        '2h': 7200,
        '4h': 14400,
        '6h': 21600,
        '12h': 43200,
        '1d': 86400,
        '3d': 259200,
        '1w': 604800,
        '1M': 2592000,  # 30 days
    }

    def __init__(self, trader_db):
        """Initialize time trigger

        Args:
            trader_db: TraderDatabase instance
        """
        super().__init__()
        self.trader_db = trader_db

    async def should_trigger(self, trader_id: str, context: Dict[str, Any]) -> bool:
        """Check if any timeframe is due for triggering

        Args:
            trader_id: Trader ID
            context: Context dict with 'trader' key

        Returns:
            True if any configured timeframe has elapsed
        """
        trader = context.get('trader')
        if not trader:
            return False

        timeframes = trader.get('timeframes', [])
        if not timeframes:
            return False

        # Check if any timeframe is due
        for tf in timeframes:
            if self._is_timeframe_due(trader_id, tf):
                return True

        return False

    def _is_timeframe_due(self, trader_id: str, timeframe: str) -> bool:
        """Check if a specific timeframe is due

        Args:
            trader_id: Trader ID
            timeframe: Timeframe string (e.g., '1h', '4h')

        Returns:
            True if timeframe interval has elapsed since last trigger
        """
        # Get seconds for this timeframe
        interval_seconds = self.TIMEFRAME_SECONDS.get(timeframe)
        if interval_seconds is None:
            # Unknown timeframe, default to 1 hour
            interval_seconds = 3600

        # Get last trigger time
        last_trigger = self.get_last_trigger_time(trader_id)

        if last_trigger is None:
            # Never triggered, should trigger now
            return True

        # Check if interval has elapsed
        elapsed = (datetime.now() - last_trigger).total_seconds()
        return elapsed >= interval_seconds

    def get_next_trigger_time(self, trader_id: str) -> datetime:
        """Get the next scheduled trigger time

        Args:
            trader_id: Trader ID

        Returns:
            Next trigger datetime or None if no timeframes configured
        """
        trader = self.trader_db.get_trader(trader_id)
        if not trader:
            return None

        timeframes = trader.get('timeframes', [])
        if not timeframes:
            return None

        # Find the minimum timeframe (most frequent trigger)
        min_seconds = min(
            (self.TIMEFRAME_SECONDS.get(tf, 3600) for tf in timeframes),
            default=None
        )

        if min_seconds is None:
            return None

        last_trigger = self.get_last_trigger_time(trader_id)
        if last_trigger is None:
            return datetime.now()

        return last_trigger + timedelta(seconds=min_seconds)

    def timeframe_to_seconds(self, timeframe: str) -> int:
        """Convert timeframe string to seconds

        Args:
            timeframe: Timeframe string (e.g., '1h', '4h')

        Returns:
            Number of seconds
        """
        return self.TIMEFRAME_SECONDS.get(timeframe, 3600)
