"""Liquidation Monitor Service

Monitors open positions and automatically liquidates positions that hit
their liquidation price.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Set

from .position import Position, PositionStatus
from .position_db import PositionDatabase
from .trader_db import TraderDatabase
from .price_service import get_price_service

# Configure logging - use WARNING to avoid interfering with Rich Console
logging.basicConfig(level=logging.WARNING, format='%(message)s')
logger = logging.getLogger(__name__)


class LiquidationMonitor:
    """Service to monitor positions and handle liquidations"""

    def __init__(self, check_interval: int = 10):
        """Initialize the liquidation monitor

        Args:
            check_interval: Time in seconds between liquidation checks (default: 10)
        """
        self.check_interval = check_interval
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._liquidated_positions: Set[int] = set()  # Track already liquidated positions

    async def check_and_liquidate_positions(self) -> List[Dict]:
        """Check all open positions and liquidate those that hit liquidation price

        Returns:
            List of liquidated position info dictionaries
        """
        pos_db = PositionDatabase()
        pos_db.initialize()

        trader_db = TraderDatabase()
        trader_db.initialize()

        liquidated_positions = []

        try:
            # Get all open positions
            all_positions = pos_db.list_positions(status='open')

            # Group positions by trader for efficient balance updates
            trader_balance_updates: Dict[str, float] = {}

            for position in all_positions:
                # Skip if already processed
                if position.id in self._liquidated_positions:
                    continue

                try:
                    # Fetch current price
                    price_service = get_price_service()
                    current_price = await price_service.fetch_current_price(
                        position.exchange,
                        position.symbol
                    )

                    # Update unrealized PnL first
                    pos_db.update_position_pnl(position.id, current_price)

                    # Reload position to get updated values
                    position = pos_db.get_position(position.id)

                    # Check if position should be liquidated
                    if position.is_liquidated(current_price):
                        logger.info(
                            f"Liquidating position {position.id} "
                            f"(trader: {position.trader_id}, "
                            f"{position.exchange} {position.symbol} "
                            f"{position.position_side.value})"
                        )

                        # Calculate realized PnL on liquidation
                        # The margin was already deducted when opening the position
                        # The actual loss is the unrealized PnL minus entry fee
                        # (which was already deducted from balance)
                        realized_pnl = position.unrealized_pnl - position.entry_fee

                        # Update position status to liquidated
                        pos_db.update_position_status(
                            position.id,
                            PositionStatus.LIQUIDATED,
                            exit_price=current_price,
                            exit_time=datetime.now(),
                            realized_pnl=realized_pnl
                        )

                        # Track balance update for trader
                        # Note: margin was already deducted when opening position
                        # But we need to reflect that the margin is lost (no recovery)
                        # In this system, margin is deducted on open, so we don't deduct again
                        # The loss is already reflected in the unrealized PnL

                        # Store liquidation info
                        liquidated_positions.append({
                            'position_id': position.id,
                            'trader_id': position.trader_id,
                            'exchange': position.exchange,
                            'symbol': position.symbol,
                            'side': position.position_side.value,
                            'entry_price': position.entry_price,
                            'liquidation_price': current_price,
                            'margin': position.margin,
                            'realized_pnl': realized_pnl,
                            'liquidation_time': datetime.now().isoformat()
                        })

                        # Mark as processed
                        self._liquidated_positions.add(position.id)

                        # Queue trader equity update
                        if position.trader_id not in trader_balance_updates:
                            trader_balance_updates[position.trader_id] = 0
                        # The loss is already in unrealized PnL, which will be reflected in equity
                        # But we should update to mark it as realized

                except Exception as e:
                    logger.error(f"Error checking position {position.id}: {e}")
                    continue

            # Update trader equity for all affected traders
            for trader_id in trader_balance_updates.keys():
                try:
                    # Get total unrealized PnL for this trader
                    positions = pos_db.list_positions(trader_id, status='open')
                    total_unrealized_pnl = sum(p.unrealized_pnl for p in positions)

                    # Update equity
                    trader_db.update_equity_with_unrealized_pnl(trader_id, total_unrealized_pnl)
                    logger.info(f"Updated equity for trader {trader_id}")

                except Exception as e:
                    logger.error(f"Error updating equity for trader {trader_id}: {e}")

            return liquidated_positions

        finally:
            pos_db.close()
            trader_db.close()

    async def start(self):
        """Start the liquidation monitor background task"""
        if self.running:
            logger.warning("Liquidation monitor is already running")
            return

        self.running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Liquidation monitor started (check interval: {self.check_interval}s)")

    async def stop(self):
        """Stop the liquidation monitor"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Liquidation monitor stopped")

    async def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                liquidated = await self.check_and_liquidate_positions()

                if liquidated:
                    logger.info(f"Liquidated {len(liquidated)} position(s)")
                    for pos_info in liquidated:
                        logger.info(
                            f"  Position {pos_info['position_id']}: "
                            f"{pos_info['trader_id']} {pos_info['exchange']} "
                            f"{pos_info['symbol']} {pos_info['side']} "
                            f"PnL: {pos_info['realized_pnl']:.2f} USDT"
                        )

            except Exception as e:
                logger.error(f"Error in liquidation monitor loop: {e}")

            # Wait before next check
            await asyncio.sleep(self.check_interval)

    async def check_single_position(self, position_id: int) -> Optional[Dict]:
        """Check a single position for liquidation

        Useful for on-demand checks (e.g., after price updates).

        Args:
            position_id: Position ID to check

        Returns:
            Liquidation info dict if liquidated, None otherwise
        """
        pos_db = PositionDatabase()
        pos_db.initialize()

        try:
            position = pos_db.get_position(position_id)

            if not position or position.status != PositionStatus.OPEN:
                return None

            # Fetch current price
            price_service = get_price_service()
            current_price = await price_service.fetch_current_price(
                position.exchange,
                position.symbol
            )

            # Update unrealized PnL
            pos_db.update_position_pnl(position_id, current_price)
            position = pos_db.get_position(position_id)

            # Check liquidation
            if position.is_liquidated(current_price):
                # Calculate realized PnL
                realized_pnl = position.unrealized_pnl - position.entry_fee

                # Update position
                pos_db.update_position_status(
                    position_id,
                    PositionStatus.LIQUIDATED,
                    exit_price=current_price,
                    exit_time=datetime.now(),
                    realized_pnl=realized_pnl
                )

                return {
                    'position_id': position.id,
                    'trader_id': position.trader_id,
                    'exchange': position.exchange,
                    'symbol': position.symbol,
                    'side': position.position_side.value,
                    'entry_price': position.entry_price,
                    'liquidation_price': current_price,
                    'margin': position.margin,
                    'realized_pnl': realized_pnl,
                    'liquidation_time': datetime.now().isoformat()
                }

            return None

        finally:
            pos_db.close()


# Singleton instance
_default_monitor: Optional[LiquidationMonitor] = None


def get_liquidation_monitor(check_interval: int = 10) -> LiquidationMonitor:
    """Get the default liquidation monitor instance

    Args:
        check_interval: Check interval in seconds (only used on first call)

    Returns:
        LiquidationMonitor instance
    """
    global _default_monitor
    if _default_monitor is None:
        _default_monitor = LiquidationMonitor(check_interval=check_interval)
    return _default_monitor


async def check_liquidation_for_position(position_id: int) -> Optional[Dict]:
    """Convenience function to check a single position for liquidation

    Args:
        position_id: Position ID to check

    Returns:
        Liquidation info if liquidated, None otherwise
    """
    monitor = get_liquidation_monitor()
    return await monitor.check_single_position(position_id)
