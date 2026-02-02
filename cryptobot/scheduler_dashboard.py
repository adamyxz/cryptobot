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
    - Fixed window with trader status table at top
    - Continuous log stream below
    - Auto-refresh
    - Ctrl+C to exit
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

        # Log storage (keep last 100 entries)
        self.logs: deque[LogEntry] = deque(maxlen=100)

        # Decision results storage (trader_id -> last result)
        self.decision_results: Dict[str, Dict[str, Any]] = {}

        # Optimization time tracking (trader_id -> last optimize time)
        self.last_optimize_times: Dict[str, datetime] = {}

        # Running state
        self.running = False
        self.live: Optional[Live] = None

        # Trader IDs being monitored
        self.monitored_trader_ids: List[str] = []

        # Task tracking (shared with scheduler)
        self.scheduler_tasks: Dict[str, Dict] = {}

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

    def log(self, message: str, level: str = "info", detail_lines: List[str] = None, trader_id: str = None):
        """Add a log entry

        Args:
            message: Log message
            level: Log level (info, warning, error, success, decide, optimize, trigger, thinking)
            detail_lines: Optional list of detail lines to display
            trader_id: Optional trader ID for filtering
        """
        self.logs.append(LogEntry(message, level, detail_lines=detail_lines, trader_id=trader_id))

    def log_decision_start(self, trader_id: str, trigger_type: str = "manual"):
        """Log the start of a decision process

        Args:
            trader_id: Trader ID
            trigger_type: What triggered this decision (manual, scheduler, trigger)
        """
        self.log(f"{trader_id} deciding...", "decide", trader_id=trader_id)

    def log_decision_thinking(self, trader_id: str, phase1_thinking: str = None,
                             phase2_thinking: str = None, indicator_data: Dict = None,
                             market_context: Dict = None):
        """Log detailed decision thinking process

        Args:
            trader_id: Trader ID
            phase1_thinking: Phase 1 thinking (initial analysis)
            phase2_thinking: Phase 2 thinking (final decision analysis)
            indicator_data: Technical indicators used
            market_context: Market context data
        """
        detail_lines = []

        # Add indicators summary
        if indicator_data:
            detail_lines.append("[cyan]Indicators:[/cyan]")
            for key, value in indicator_data.items():
                if isinstance(value, dict):
                    # Handle nested indicator data
                    value_str = ", ".join(f"{k}: {v}" for k, v in value.items())
                    detail_lines.append(f"  • {key}: {value_str}")
                else:
                    detail_lines.append(f"  • {key}: {value}")

        # Add market context summary
        if market_context:
            if 'price' in market_context:
                detail_lines.append(f"[cyan]Price:[/cyan] ${market_context.get('price', 'N/A')}")
            if 'volume_24h' in market_context:
                detail_lines.append(f"[cyan]Volume (24h):[/cyan] ${market_context.get('volume_24h', 'N/A')}")

        # Add phase 1 thinking (truncated for readability)
        if phase1_thinking:
            thinking_preview = self._truncate_text(phase1_thinking, max_lines=3, max_chars=200)
            detail_lines.append(f"[blue]Initial Analysis:[/blue]")
            detail_lines.append(f"  {thinking_preview}")

        # Add phase 2 thinking (truncated for readability)
        if phase2_thinking:
            thinking_preview = self._truncate_text(phase2_thinking, max_lines=3, max_chars=200)
            detail_lines.append(f"[blue]Decision Analysis:[/blue]")
            detail_lines.append(f"  {thinking_preview}")

        if detail_lines:
            self.log(f"{trader_id} AI thinking process", "thinking", detail_lines=detail_lines, trader_id=trader_id)

    def log_decision_complete(self, trader_id: str, decision: str, phase1_thinking: str = None,
                             phase2_thinking: str = None):
        """Log the completion of a decision

        Args:
            trader_id: Trader ID
            decision: The final decision
            phase1_thinking: Phase 1 thinking (for summary)
            phase2_thinking: Phase 2 thinking (for summary)
        """
        self.log(f"{trader_id} decision complete: {decision}", "success", trader_id=trader_id)

    def _truncate_text(self, text: str, max_lines: int = 3, max_chars: int = 200) -> str:
        """Truncate text to specified limits

        Args:
            text: Text to truncate
            max_lines: Maximum number of lines
            max_chars: Maximum number of characters

        Returns:
            Truncated text with ellipsis if needed
        """
        if not text:
            return ""

        # Split into lines
        lines = text.split('\n')

        # Take first N lines
        truncated = '\n'.join(lines[:max_lines])

        # Truncate by character count if still too long
        if len(truncated) > max_chars:
            truncated = truncated[:max_chars] + "..."

        # Add ellipsis if we truncated lines
        if len(lines) > max_lines:
            truncated = truncated.rstrip() + "\n  ..."

        return truncated.strip()

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

    def _build_log_panel(self) -> Panel:
        """Build the log panel

        Returns:
            Rich Panel with log entries
        """
        if not self.logs:
            log_text = Text("[dim]Waiting for logs...[/dim]", style="dim")
        else:
            log_text = Text()
            for entry in self.logs:
                log_text.append(entry.to_rich_text())
                log_text.append("\n")

        return Panel(
            log_text,
            title="[bold]Activity Log[/bold]",
            border_style="dim",
            height=15  # Fixed height for log area
        )

    def _generate_layout(self) -> Layout:
        """Generate the main layout

        Returns:
            Rich Layout with table and logs
        """
        layout = Layout()

        # Split vertically: table on top, logs on bottom
        layout.split_column(
            Layout(name="table", ratio=2),
            Layout(name="logs", ratio=1)
        )

        # Add table
        layout["table"].update(Panel(
            self._build_status_table(),
            title="[bold cyan]Trader Monitor[/bold cyan]",
            border_style="cyan"
        ))

        # Add logs
        layout["logs"].update(self._build_log_panel())

        return layout

    async def start(self, refresh_interval: float = 1.0):
        """Start the live dashboard

        Args:
            refresh_interval: Refresh interval in seconds
        """
        self.running = True

        # Initial log
        self.log("Dashboard started", "success")
        self.log(f"Monitoring {len(self.monitored_trader_ids)} trader(s)", "info")
        self.log("Press Ctrl+C to exit", "dim")

        try:
            with Live(
                self._generate_layout(),
                console=self.console,
                refresh_per_second=1 / refresh_interval,
                screen=False
            ) as live:
                self.live = live

                while self.running:
                    # Update the display
                    live.update(self._generate_layout())

                    # Wait for next refresh
                    await asyncio.sleep(refresh_interval)

        except KeyboardInterrupt:
            self.log("\nReceived exit signal, stopping...", "warning")
        finally:
            self.running = False
            self.live = None

    def stop(self):
        """Stop the dashboard"""
        self.running = False
        if self.live:
            self.live.stop()
