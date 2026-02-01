"""Trigger Manager

Manages multiple triggers and coordinates their execution.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from .base import BaseTrigger, TriggerType, TriggerEvent
from .time_trigger import TimeTrigger
from .price_trigger import PriceTrigger


class TriggerManager:
    """Manages and coordinates multiple triggers

    Evaluates all triggers and determines which traders should be triggered.
    """

    def __init__(self, trader_db, price_threshold: float = 0.04):
        """Initialize trigger manager

        Args:
            trader_db: TraderDatabase instance
            price_threshold: Price change threshold for PriceTrigger
        """
        self.trader_db = trader_db
        self.triggers: List[BaseTrigger] = []

        # Initialize default triggers
        self.time_trigger = TimeTrigger(trader_db)
        self.price_trigger = PriceTrigger(price_threshold)

        # Add triggers (time trigger first, then price trigger for priority)
        self.triggers.append(self.time_trigger)
        self.triggers.append(self.price_trigger)

    async def check_traders(
        self,
        trader_ids: List[str],
        context_builder: callable
    ) -> List[TriggerEvent]:
        """Check all traders for trigger conditions

        Args:
            trader_ids: List of trader IDs to check
            context_builder: Function that builds context for a trader:
                async def context_builder(trader_id) -> dict

        Returns:
            List of TriggerEvent objects for triggered traders
        """
        triggered_events = []

        for trader_id in trader_ids:
            # Build context for this trader
            context = await context_builder(trader_id)

            # Check each trigger
            for trigger in self.triggers:
                try:
                    should_fire = await trigger.should_trigger(trader_id, context)

                    if should_fire:
                        # Determine trigger type
                        if isinstance(trigger, TimeTrigger):
                            trigger_type = TriggerType.TIME
                            metadata = {'trigger': 'time', 'timeframes': context.get('trader', {}).get('timeframes', [])}
                        elif isinstance(trigger, PriceTrigger):
                            trigger_type = TriggerType.PRICE
                            metadata = {'trigger': 'price', 'threshold': trigger.get_threshold()}
                        else:
                            trigger_type = TriggerType.MANUAL
                            metadata = {}

                        # Create trigger event
                        event = TriggerEvent(
                            trigger_type=trigger_type,
                            trader_id=trader_id,
                            timestamp=datetime.now(),
                            metadata=metadata
                        )
                        triggered_events.append(event)

                        # Record the trigger
                        trigger.record_trigger(trader_id)

                        # Only fire one trigger per trader per check
                        break

                except Exception as e:
                    # Log error but continue checking other triggers
                    print(f"[TriggerManager] Error checking trigger for {trader_id}: {e}")

        return triggered_events

    def get_time_trigger(self) -> TimeTrigger:
        """Get the time trigger instance

        Returns:
            TimeTrigger instance
        """
        return self.time_trigger

    def get_price_trigger(self) -> PriceTrigger:
        """Get the price trigger instance

        Returns:
            PriceTrigger instance
        """
        return self.price_trigger

    def set_price_threshold(self, threshold: float):
        """Update price trigger threshold

        Args:
            threshold: New threshold (e.g., 0.04 for 4%)
        """
        self.price_trigger.set_threshold(threshold)

    def get_price_threshold(self) -> float:
        """Get current price threshold

        Returns:
            Current threshold
        """
        return self.price_trigger.get_threshold()

    def reset_trigger_times(self, trader_id: str):
        """Reset all trigger times for a trader

        Useful after configuration changes or manual triggers.

        Args:
            trader_id: Trader ID
        """
        for trigger in self.triggers:
            trigger.reset_trigger_time(trader_id)

    def reset_price_snapshots(self, trader_id: str):
        """Reset price snapshots for a trader

        Args:
            trader_id: Trader ID
        """
        self.price_trigger.reset_snapshots(trader_id)
