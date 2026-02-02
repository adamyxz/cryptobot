"""Trader Scheduler

Core scheduling engine for continuous trading operations.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from .trader_db import TraderDatabase
from .position_db import PositionDatabase
from .price_service import get_price_service
from .priority_queue import TraderPriorityQueue, PriorityTask
from .triggers import TriggerManager, TriggerEvent, TriggerType
from .scheduler_config import get_scheduler_config
from .scheduler_dashboard import SchedulerDashboard


class TraderScheduler:
    """Continuous operation scheduler for traders

    Monitors trader positions and market data, triggering decide/optimize
    operations based on configured conditions.
    """

    def __init__(self, cryptobot_instance, trader_db, position_db):
        """Initialize the scheduler

        Args:
            cryptobot_instance: CryptoBot instance for executing decisions
            trader_db: Initialized TraderDatabase instance
            position_db: Initialized PositionDatabase instance
        """
        self.cryptobot = cryptobot_instance
        self.trader_db = trader_db
        self.position_db = position_db
        self.price_service = get_price_service()
        # Use the same console as CryptoBot
        self.console = cryptobot_instance.console

        # Load configuration
        self.config = get_scheduler_config()

        # Priority queue for tasks
        self.priority_queue = TraderPriorityQueue()

        # Trigger manager
        price_threshold = self.config.get_float('trigger.price.change_threshold', 0.04)
        self.trigger_manager = TriggerManager(trader_db, price_threshold)

        # State
        self.running = False
        self.tasks: Dict[str, Dict] = {}  # trader_id -> task_info
        self.last_optimize_times: Dict[str, datetime] = {}
        self.schedule_task: Optional[asyncio.Task] = None

        # Dashboard
        self.dashboard = SchedulerDashboard(trader_db, position_db)

    async def start(self, trader_ids: List[str] = None):
        """Start the scheduler

        Args:
            trader_ids: List of trader IDs to schedule. None = all active traders.
        """
        if self.running:
            self.console.print("Scheduler is already running", style="yellow")
            return

        self.running = True

        # Load traders to schedule
        if trader_ids is None:
            # Get all traders
            all_traders = self.trader_db.list_traders()
            trader_ids = [t['id'] for t in all_traders]

        # Initialize task tracking
        for trader_id in trader_ids:
            trader = self.trader_db.get_trader(trader_id)
            if trader:
                self.tasks[trader_id] = {
                    'trader_id': trader_id,
                    'enabled': True,
                    'last_trigger': None,
                    'total_triggers': 0,
                    'last_decide': None,
                    'last_optimize': self.last_optimize_times.get(trader_id),
                }

        active_count = len(self.tasks)

        # Configure and start dashboard
        self.dashboard.set_monitored_traders(list(self.tasks.keys()))

        # Start schedule loop and dashboard in parallel
        self.schedule_task = asyncio.create_task(self._schedule_loop())
        dashboard_task = asyncio.create_task(self.dashboard.start())

        # Wait for dashboard to exit (Ctrl+C)
        await dashboard_task

        # Dashboard stopped, stop scheduler
        await self.stop()

    async def stop(self):
        """Stop the scheduler"""
        if not self.running:
            return

        self.dashboard.log("Stopping scheduler...", "warning")
        self.running = False

        # Stop dashboard
        self.dashboard.stop()

        # Cancel schedule task
        if self.schedule_task:
            self.schedule_task.cancel()
            try:
                await self.schedule_task
            except asyncio.CancelledError:
                pass

        # Wait for queue to empty (optional)
        timeout = 30
        start = datetime.now()
        while not self.priority_queue.is_empty() and (datetime.now() - start).total_seconds() < timeout:
            await asyncio.sleep(0.5)

        self.console.print("⏹ Scheduler stopped", style="yellow")

    async def _schedule_loop(self):
        """Main scheduling loop

        Runs continuously while scheduler is active.
        """
        check_interval = self.config.get_int('scheduler.check_interval', 30)

        while self.running:
            try:
                # 1. Update prices for all traders
                await self._update_all_prices()

                # 2. Check triggers and add tasks to queue
                await self._check_triggers()

                # 3. Process tasks from queue
                await self._process_tasks()

                # 4. Update dashboard task tracking
                self.dashboard.update_scheduler_tasks(self.tasks)

                # 5. Sleep until next check
                await asyncio.sleep(check_interval)

            except asyncio.CancelledError:
                # Scheduler is being stopped
                break
            except Exception as e:
                self.dashboard.log(f"Scheduler loop error: {e}", "error")
                # Sleep longer after error
                await asyncio.sleep(check_interval * 2)

    async def _update_all_prices(self):
        """Update position prices for all monitored traders"""
        for trader_id in self.tasks.keys():
            if not self.tasks[trader_id]['enabled']:
                continue

            try:
                await self.price_service.update_trader_positions(
                    trader_id, self.position_db
                )
            except Exception as e:
                # Log but continue with other traders (silent)
                pass

    async def _check_triggers(self):
        """Check trigger conditions for all traders"""
        # Build context builder function
        async def build_context(trader_id: str) -> Dict[str, Any]:
            trader = self.trader_db.get_trader(trader_id)
            positions = self.position_db.list_positions(trader_id, status='open')
            summary = self.position_db.get_trader_positions_summary(trader_id)

            return {
                'trader': trader,
                'positions': {
                    'open': positions,
                    'summary': summary
                }
            }

        # Check triggers for all enabled traders
        enabled_trader_ids = [
            tid for tid, info in self.tasks.items()
            if info['enabled']
        ]

        triggered_events = await self.trigger_manager.check_traders(
            enabled_trader_ids,
            build_context
        )

        # Add triggered tasks to queue
        for event in triggered_events:
            trader_id = event.trader_id

            # Determine priority based on trigger type
            if event.trigger_type == TriggerType.PRICE:
                priority = 3  # High priority for price triggers
                trigger_name = "price"
            else:
                priority = 5  # Normal priority for time triggers
                trigger_name = "time"

            self.priority_queue.add_task(
                trader_id=trader_id,
                action='decide',
                priority=priority,
                metadata=event.metadata
            )

            # Update task tracking
            self.tasks[trader_id]['last_trigger'] = event.timestamp
            self.tasks[trader_id]['total_triggers'] += 1

            # Log to dashboard
            self.dashboard.log(f"{trader_id} triggered decide ({trigger_name})", "trigger")

        # Check for optimization triggers
        for trader_id in enabled_trader_ids:
            if await self._should_optimize(trader_id):
                self.priority_queue.add_task(
                    trader_id=trader_id,
                    action='optimize',
                    priority=8  # Lower priority than decide
                )

    async def _process_tasks(self):
        """Process tasks from the priority queue

        Executes tasks in priority order.
        """
        max_concurrent = self.config.get_int('scheduler.max_concurrent_tasks', 3)

        while not self.priority_queue.is_empty():
            # Check concurrency limit
            running_count = sum(
                1 for info in self.tasks.values()
                if info.get('processing', False)
            )

            if running_count >= max_concurrent:
                # Too many tasks running, wait
                break

            # Get next task
            task = self.priority_queue.get_next_task()
            if task is None:
                break

            # Mark as processing
            trader_id = task.trader_id
            self.tasks[trader_id]['processing'] = True

            # Execute task (non-blocking)
            asyncio.create_task(self._execute_task(task))

    async def _execute_task(self, task: PriorityTask):
        """Execute a single task

        Args:
            task: PriorityTask to execute
        """
        trader_id = task.trader_id
        action = task.action
        metadata = task.metadata

        try:
            trigger_type = metadata.get('trigger', 'unknown')

            if action == 'decide':
                # Log to dashboard
                self.dashboard.log(f"{trader_id} deciding...", "decide")

                # Update dashboard task tracking
                self.dashboard.update_scheduler_tasks(self.tasks)

                # Execute decision (will be implemented with DecisionEngine)
                decision_summary = await self._execute_decision(trader_id, metadata)

                # Update tracking
                self.tasks[trader_id]['last_decide'] = datetime.now()

                # Update dashboard with decision result
                self.dashboard.update_decision_result(trader_id, decision_summary, "decide")

                # Log based on result
                if "failed" in decision_summary.lower() or "error" in decision_summary.lower():
                    self.dashboard.log(f"{trader_id} decision failed: {decision_summary}", "error")
                else:
                    self.dashboard.log(f"{trader_id} decision complete: {decision_summary}", "success")

            elif action == 'optimize':
                # Log to dashboard
                self.dashboard.log(f"{trader_id} optimizing...", "optimize")

                # Update dashboard task tracking
                self.dashboard.update_scheduler_tasks(self.tasks)

                # Execute optimization (will be implemented with DecisionEngine)
                await self._execute_optimization(trader_id)

                # Update tracking
                self.tasks[trader_id]['last_optimize'] = datetime.now()
                self.last_optimize_times[trader_id] = datetime.now()

                # Update dashboard with optimization result
                self.dashboard.update_decision_result(trader_id, "optimized", "optimize")
                self.dashboard.log(f"{trader_id} optimization complete", "success")

        except Exception as e:
            self.dashboard.log(f"Task execution failed ({trader_id} {action}): {e}", "error")
        finally:
            # Clear processing flag
            self.tasks[trader_id]['processing'] = False
            # Update dashboard task tracking
            self.dashboard.update_scheduler_tasks(self.tasks)

    async def _execute_decision(self, trader_id: str, metadata: Dict[str, Any]) -> str:
        """Execute a decision for a trader

        Args:
            trader_id: Trader ID
            metadata: Task metadata

        Returns:
            Decision result string
        """
        # Call CryptoBot's existing decision method with verbose=False
        decision_result = await self.cryptobot._execute_decision_process(trader_id, verbose=False)

        # Parse decision for display
        if decision_result and decision_result != "ERROR":
            parts = decision_result.split()
            action = parts[0] if parts else "UNKNOWN"

            # Format decision summary
            if action == "OPEN_LONG":
                if len(parts) >= 4:
                    summary = f"open {parts[2]} long"
                else:
                    summary = f"open long"
            elif action == "OPEN_SHORT":
                if len(parts) >= 4:
                    summary = f"open {parts[2]} short"
                else:
                    summary = f"open short"
            elif action == "CLOSE_POSITION":
                summary = f"close #{parts[1] if len(parts) > 1 else ''}"
            elif action == "CLOSE_ALL":
                summary = "close all"
            elif action == "HOLD":
                summary = "hold"
            else:
                summary = action
        else:
            summary = "decision failed" if decision_result == "ERROR" else "unknown"

        return summary

    async def _execute_optimization(self, trader_id: str):
        """Execute an optimization for a trader

        Args:
            trader_id: Trader ID
        """
        # Optimization command - let it handle its own output for now
        await self.cryptobot._handle_optimize_command([trader_id])

    async def _should_optimize(self, trader_id: str) -> bool:
        """Check if optimization should be triggered

        Args:
            trader_id: Trader ID

        Returns:
            True if optimization should run
        """
        if not self.config.get_bool('optimize.enabled', True):
            return False

        # Get last optimization time
        last_optimize = self.last_optimize_times.get(trader_id)

        if last_optimize is None:
            # Never optimized, check if enough trading history
            summary = self.position_db.get_trader_positions_summary(trader_id)
            min_positions = self.config.get_int('optimize.min_positions', 5)
            return summary['total_positions'] >= min_positions

        # Check if interval has passed
        interval_hours = self.config.get_int('optimize.interval_hours', 24)
        hours_since_last = (datetime.now() - last_optimize).total_seconds() / 3600

        return hours_since_last >= interval_hours

    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status

        Returns:
            Status dictionary with statistics
        """
        trader_statuses = []
        for trader_id, info in self.tasks.items():
            status = {
                'trader_id': trader_id,
                'enabled': info['enabled'],
                'last_trigger': info['last_trigger'],
                'last_decide': info['last_decide'],
                'last_optimize': info['last_optimize'],
                'total_triggers': info['total_triggers'],
                'processing': info.get('processing', False)
            }
            trader_statuses.append(status)

        return {
            'running': self.running,
            'total_traders': len(self.tasks),
            'enabled_traders': sum(1 for t in self.tasks.values() if t['enabled']),
            'queue_size': self.priority_queue.size(),
            'queue_summary': self.priority_queue.get_queue_summary(),
            'traders': trader_statuses
        }

    def enable_trader(self, trader_id: str):
        """Enable scheduling for a trader

        Args:
            trader_id: Trader ID
        """
        if trader_id in self.tasks:
            self.tasks[trader_id]['enabled'] = True

    def disable_trader(self, trader_id: str):
        """Disable scheduling for a trader

        Args:
            trader_id: Trader ID
        """
        if trader_id in self.tasks:
            self.tasks[trader_id]['enabled'] = False
            # Remove any pending tasks for this trader
            self.priority_queue.remove_trader_tasks(trader_id)
