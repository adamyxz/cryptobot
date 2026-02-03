"""Scheduler Dashboard

Live dashboard for monitoring trader operations with a fixed window display.
Shows trader status table at the top and continuous log stream below.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import deque

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.layout import Layout


class LogEntry:
    """A single log entry with support for detailed multi-line content"""

    def __init__(self, message: str, level: str = "info", timestamp: datetime = None,
                 detail_lines: List[str] = None, trader_id: str = None):
        self.message = message
        self.level = level  # info, warning, error, success, decide, optimize, trigger, thinking
        self.timestamp = timestamp or datetime.now()
        self.detail_lines = detail_lines or []  # Additional detail lines for complex entries
        self.trader_id = trader_id  # Optional trader ID for filtering

    def to_rich_text(self) -> Text:
        """Convert to Rich Text with styling"""
        time_str = self.timestamp.strftime("%H:%M:%S")

        style_map = {
            "info": "dim cyan",
            "warning": "yellow",
            "error": "red",
            "success": "green",
            "decide": "bold blue",
            "optimize": "bold magenta",
            "trigger": "dim yellow",
            "thinking": "dim white",
            "indicator": "cyan",
            "analysis": "blue"
        }

        style = style_map.get(self.level, "white")

        # Format: [HH:MM:SS] message
        text = Text()
        text.append(f"[{time_str}] ", style="dim")
        text.append(self.message, style=style)

        # Add detail lines with indentation
        for line in self.detail_lines:
            text.append("\n    ")
            # Use different styling for different types of details
            if line.startswith("•") or line.startswith("-"):
                text.append(line, style="dim")
            elif ":" in line and not line.startswith(" "):
                # Field-style lines (e.g., "RSI: 45.2")
                text.append(line, style="cyan")
            else:
                text.append(line, style="dim white")

        return text


class SchedulerDashboard:
    """Live dashboard for scheduler monitoring

    Features:
    - Fixed window with trader status table
    - Auto-refresh
    - Can be embedded in a larger layout
    - Supports paused/running state
    """

    def __init__(self, trader_db, position_db):
        """Initialize the dashboard

        Args:
            trader_db: TraderDatabase instance
            position_db: PositionDatabase instance
        """
        self.trader_db = trader_db
        self.position_db = position_db
        self.console = Console()

        # Decision results storage (trader_id -> last result)
        self.decision_results: Dict[str, Dict[str, Any]] = {}

        # Optimization time tracking (trader_id -> last optimize time)
        self.last_optimize_times: Dict[str, datetime] = {}

        # Trader IDs being monitored
        self.monitored_trader_ids: List[str] = []

        # Task tracking (shared with scheduler)
        self.scheduler_tasks: Dict[str, Dict] = {}

        # Scheduler running state
        self.scheduler_running = False

    def set_scheduler_running(self, running: bool):
        """Set the scheduler running state

        Args:
            running: True if scheduler is running, False otherwise
        """
        self.scheduler_running = running

    def set_monitored_traders(self, trader_ids: List[str]):
        """Set the list of traders to monitor

        Args:
            trader_ids: List of trader IDs
        """
        self.monitored_trader_ids = trader_ids

        # Initialize decision results for new traders
        for trader_id in trader_ids:
            if trader_id not in self.decision_results:
                self.decision_results[trader_id] = {
                    'last_decision': None,
                    'last_decision_time': None,
                    'decision_summary': 'none'
                }
            if trader_id not in self.last_optimize_times:
                self.last_optimize_times[trader_id] = None

    def update_decision_result(self, trader_id: str, result: str, action: str):
        """Update the last decision result for a trader

        Args:
            trader_id: Trader ID
            result: Decision result summary (e.g., "open BTCUSDT long")
            action: Action type (decide, optimize)
        """
        if action == 'optimize':
            # Track optimize time separately
            self.last_optimize_times[trader_id] = datetime.now()
        else:
            # Track decide result
            self.decision_results[trader_id] = {
                'last_decision': result,
                'last_decision_time': datetime.now(),
                'action': action
            }

    def update_scheduler_tasks(self, tasks: Dict[str, Dict]):
        """Update scheduler task tracking

        Args:
            tasks: Dictionary of trader_id -> task_info
        """
        self.scheduler_tasks = tasks

    def _build_status_table(self) -> Table:
        """Build the trader status table

        Returns:
            Rich Table object
        """
        table = Table(title="", show_header=True, header_style="bold cyan", expand=True)
        table.add_column("Trader ID", style="cyan", width=20)
        table.add_column("Last Decision", style="yellow", width=25)
        table.add_column("Time Ago", justify="center", style="dim", width=10)
        table.add_column("Last Optimize", justify="center", style="magenta", width=10)
        table.add_column("Positions", justify="center", style="white", width=8)
        table.add_column("Total PnL", justify="right", style="bold", width=12)

        # If no traders, show a message
        if not self.monitored_trader_ids:
            table.add_row(
                "[dim]No traders[/dim]",
                "[dim]Use /start to begin[/dim]",
                "",
                "",
                "",
                ""
            )
            return table

        for trader_id in self.monitored_trader_ids:
            # Get decision result
            decision_info = self.decision_results.get(trader_id, {})
            last_decision = decision_info.get('last_decision', 'none')
            last_decision_time = decision_info.get('last_decision_time')

            # Format time ago
            if last_decision_time:
                time_ago = datetime.now() - last_decision_time
                if time_ago < timedelta(minutes=1):
                    time_str = f"{time_ago.seconds}s ago"
                elif time_ago < timedelta(hours=1):
                    time_str = f"{time_ago.seconds // 60}m ago"
                elif time_ago < timedelta(days=1):
                    time_str = f"{time_ago.seconds // 3600}h ago"
                else:
                    time_str = f"{time_ago.days}d ago"
            else:
                time_str = "-"

            # Get and format last optimize time
            last_optimize_time = self.last_optimize_times.get(trader_id)
            if last_optimize_time:
                optimize_ago = datetime.now() - last_optimize_time
                if optimize_ago < timedelta(minutes=1):
                    optimize_str = f"{optimize_ago.seconds}s"
                elif optimize_ago < timedelta(hours=1):
                    optimize_str = f"{optimize_ago.seconds // 60}m"
                elif optimize_ago < timedelta(days=1):
                    optimize_str = f"{optimize_ago.seconds // 3600}h"
                else:
                    optimize_str = f"{optimize_ago.days}d"
            else:
                optimize_str = "[dim]-[/dim]"

            # Get position summary
            summary = self.position_db.get_trader_positions_summary(trader_id)
            position_count = summary['open_positions']

            # Calculate total PnL
            total_unrealized_pnl = summary['total_unrealized_pnl']
            total_realized_pnl = summary['total_realized_pnl']
            total_pnl = total_unrealized_pnl + total_realized_pnl

            # Format PnL with color
            if total_pnl > 0:
                pnl_str = f"+${total_pnl:.2f}"
                pnl_style = "green"
            elif total_pnl < 0:
                pnl_str = f"-${abs(total_pnl):.2f}"
                pnl_style = "red"
            else:
                pnl_str = "$0.00"
                pnl_style = "dim"

            # Get processing status
            task_info = self.scheduler_tasks.get(trader_id, {})
            is_processing = task_info.get('processing', False)

            # Add processing indicator
            trader_display = f"{'[yellow]⟳[/yellow] ' if is_processing else ''}{trader_id}"

            # Format decision result
            if last_decision == 'none':
                decision_display = "[dim]none[/dim]"
            else:
                decision_display = last_decision

            table.add_row(
                trader_display,
                decision_display,
                time_str,
                optimize_str,
                str(position_count),
                f"[{pnl_style}]{pnl_str}[/{pnl_style}]"
            )

        return table

    def render(self) -> Panel:
        """Render the dashboard as a Panel

        Returns:
            Rich Panel with trader status table
        """
        # Add status indicator to title
        if self.scheduler_running:
            status_text = "[green]●[/green] Running"
        else:
            status_text = "[dim]○[/dim] Stopped"

        title = f"[bold cyan]Trader Monitor[/bold cyan] {status_text}"

        return Panel(
            self._build_status_table(),
            title=title,
            border_style="cyan"
        )
