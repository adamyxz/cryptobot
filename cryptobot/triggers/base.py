"""Base Trigger Classes

Defines the abstract interface for trigger implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Any


class TriggerType(Enum):
    """Types of triggers"""
    TIME = "time"          # Time-based trigger (timeframes)
    PRICE = "price"        # Price change trigger
    MANUAL = "manual"      # Manual trigger


@dataclass
class TriggerEvent:
    """Trigger event data

    Attributes:
        trigger_type: Type of trigger that fired
        trader_id: Trader ID being triggered
        timestamp: When the trigger occurred
        metadata: Additional information about the trigger
    """
    trigger_type: TriggerType
    trader_id: str
    timestamp: datetime
    metadata: Dict[str, Any]

    def __repr__(self) -> str:
        return (f"TriggerEvent(type={self.trigger_type.value}, "
                f"trader={self.trader_id}, "
                f"time={self.timestamp.strftime('%H:%M:%S')})")


class BaseTrigger(ABC):
    """Base class for trigger implementations

    Subclasses must implement should_trigger() to determine when
    a trader should be triggered for decision making.
    """

    def __init__(self):
        """Initialize the trigger"""
        self.last_trigger_times = {}  # trader_id -> datetime

    @abstractmethod
    async def should_trigger(self, trader_id: str, context: Dict[str, Any]) -> bool:
        """Check if trigger condition is met

        Args:
            trader_id: Trader ID to check
            context: Context information including:
                - 'trader': Trader database record
                - 'positions': Position information
                - 'prices': Current prices

        Returns:
            True if trigger should fire
        """
        pass

    def record_trigger(self, trader_id: str):
        """Record that a trigger fired for this trader

        Args:
            trader_id: Trader ID
        """
        import asyncio
        # Run synchronously in async context
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context
            self.last_trigger_times[trader_id] = datetime.now()
        else:
            # Set directly
            self.last_trigger_times[trader_id] = datetime.now()

    def get_last_trigger_time(self, trader_id: str) -> datetime:
        """Get last trigger time for a trader

        Args:
            trader_id: Trader ID

        Returns:
            Last trigger datetime or None if never triggered
        """
        return self.last_trigger_times.get(trader_id)

    def reset_trigger_time(self, trader_id: str):
        """Reset trigger time for a trader (e.g., after config change)

        Args:
            trader_id: Trader ID
        """
        if trader_id in self.last_trigger_times:
            del self.last_trigger_times[trader_id]
