"""CLI UI Components

Split-screen UI with dashboard and command output
"""

from typing import List, Dict, Any
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.columns import Columns


class CLIInterface:
    """Manages the CLI interface with split-screen layout"""

    def __init__(self, trader_db, position_db):
        """Initialize CLI interface

        Args:
            trader_db: TraderDatabase instance
            position_db: PositionDatabase instance
        """
        self.trader_db = trader_db
        self.position_db = position_db
        self.console = Console()

        # Dashboard data
        self.monitored_trader_ids: List[str] = []
        self.decision_results: Dict[str, Dict[str, Any]] = {}
        self.last_optimize_times: Dict[str, datetime] = {}
        self.scheduler_tasks: Dict[str, Dict] = {}
        self.scheduler_running = False

        # Output history
        self.output_history: List[Dict[str, Any]] = []

    def set_scheduler_running(self, running: bool):
        """Set scheduler running state"""
        self.scheduler_running = running

    def set_monitored_traders(self, trader_ids: List[str]):
        """Set monitored traders"""
        self.monitored_trader_ids = trader_ids
        for trader_id in trader_ids:
            if trader_id not in self.decision_results:
                self.decision_results[trader_id] = {
                    'last_decision': None,
                    'last_decision_time': None,
                }
            if trader_id not in self.last_optimize_times:
                self.last_optimize_times[trader_id] = None

    def update_decision_result(self, trader_id: str, result: str, action: str):
        """Update decision result"""
        if action == 'optimize':
            self.last_optimize_times[trader_id] = datetime.now()
        else:
            self.decision_results[trader_id] = {
                'last_decision': result,
                'last_decision_time': datetime.now(),
            }

    def update_scheduler_tasks(self, tasks: Dict[str, Dict]):
        """Update scheduler tasks"""
        self.scheduler_tasks = tasks

    def add_output(self, message: str, style: str = "white"):
        """Add output message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.output_history.append({
            'time': timestamp,
            'message': message,
            'style': style
        })
        if len(self.output_history) > 100:
            self.output_history.pop(0)

    def log(self, message: str, level: str = "info", detail_lines: List[str] = None, trader_id: str = None):
        """Log message (for compatibility with scheduler)

        Args:
            message: Log message
            level: Log level (info, warning, error, success, decide, optimize, trigger, thinking)
            detail_lines: Optional list of detail lines
            trader_id: Optional trader ID
        """
        # Map log levels to output styles
        style_map = {
            "info": "cyan",
            "warning": "yellow",
            "error": "red",
            "success": "green",
            "decide": "blue",
            "optimize": "magenta",
            "trigger": "yellow",
            "thinking": "dim",
        }
        style = style_map.get(level, "white")

        # Add trader_id prefix if provided
        if trader_id:
            message = f"[{trader_id}] {message}"

        self.add_output(message, style)

    def log_decision_start(self, trader_id: str, trigger_type: str = "manual"):
        """Log decision start (for compatibility with scheduler)"""
        self.log(f"{trader_id} deciding...", "decide", trader_id=trader_id)

    def log_decision_thinking(self, trader_id: str, phase1_thinking: str = None,
                             phase2_thinking: str = None, indicator_data: Dict = None,
                             market_context: Dict = None):
        """Log decision thinking (for compatibility with scheduler)"""
        # Simplified - just log that thinking is happening
        self.log(f"{trader_id} analyzing...", "thinking", trader_id=trader_id)

    def log_decision_complete(self, trader_id: str, decision: str, phase1_thinking: str = None,
                             phase2_thinking: str = None):
        """Log decision complete (for compatibility with scheduler)"""
        self.log(f"{trader_id} decision: {decision}", "success", trader_id=trader_id)

    def _build_status_table(self) -> Table:
        """Build status table"""
        table = Table(title="", show_header=True, header_style="bold cyan", expand=True)
        table.add_column("Trader ID", style="cyan", width=18)
        table.add_column("Last Decision", style="yellow", width=22)
        table.add_column("Time Ago", justify="center", style="dim", width=8)
        table.add_column("Last Opt", justify="center", style="magenta", width=8)
        table.add_column("Pos", justify="center", style="white", width=4)
        table.add_column("PnL", justify="right", style="bold", width=10)

        if not self.monitored_trader_ids:
            table.add_row("[dim]No traders[/dim]", "[dim]Use /start[/dim]", "", "", "", "")
            return table

        from datetime import timedelta
        for trader_id in self.monitored_trader_ids:
            decision_info = self.decision_results.get(trader_id, {})
            last_decision = decision_info.get('last_decision', 'none')
            last_decision_time = decision_info.get('last_decision_time')

            if last_decision_time:
                time_ago = datetime.now() - last_decision_time
                if time_ago < timedelta(minutes=1):
                    time_str = f"{time_ago.seconds}s"
                elif time_ago < timedelta(hours=1):
                    time_str = f"{time_ago.seconds // 60}m"
                else:
                    time_str = f"{time_ago.seconds // 3600}h"
            else:
                time_str = "-"

            last_optimize_time = self.last_optimize_times.get(trader_id)
            if last_optimize_time:
                optimize_ago = datetime.now() - last_optimize_time
                if optimize_ago < timedelta(hours=1):
                    optimize_str = f"{optimize_ago.seconds // 60}m"
                else:
                    optimize_str = f"{optimize_ago.seconds // 3600}h"
            else:
                optimize_str = "[dim]-[/dim]"

            summary = self.position_db.get_trader_positions_summary(trader_id)
            position_count = summary['open_positions']
            total_pnl = summary['total_unrealized_pnl'] + summary['total_realized_pnl']

            if total_pnl > 0:
                pnl_str = f"+${total_pnl:.2f}"
                pnl_style = "green"
            elif total_pnl < 0:
                pnl_str = f"-${abs(total_pnl):.2f}"
                pnl_style = "red"
            else:
                pnl_str = "$0.00"
                pnl_style = "dim"

            task_info = self.scheduler_tasks.get(trader_id, {})
            is_processing = task_info.get('processing', False)
            trader_display = f"{'[yellow]⟳[/yellow] ' if is_processing else ''}{trader_id}"

            decision_display = "[dim]none[/dim]" if last_decision == 'none' else last_decision

            table.add_row(
                trader_display,
                decision_display,
                time_str,
                optimize_str,
                str(position_count),
                f"[{pnl_style}]{pnl_str}[/{pnl_style}]"
            )

        return table

    def render(self):
        """Render the full UI

        Returns:
            List of renderable objects
        """
        # Build status text
        if self.scheduler_running:
            status_text = "[green]●[/green] Running"
        else:
            status_text = "[dim]○[/dim] Stopped"

        # Build dashboard
        dashboard = Panel(
            self._build_status_table(),
            title=f"[bold cyan]Trader Monitor[/bold cyan] {status_text}",
            border_style="cyan"
        )

        # Build output
        if not self.output_history:
            output_content = Text("[dim]Ready. Type /help for commands.[/dim]", style="dim")
        else:
            output_content = Text()
            for entry in self.output_history[-12:]:
                output_content.append(f"[{entry['time']}] ", style="dim")
                output_content.append(entry['message'] + "\n", style=entry['style'])

        output = Panel(
            output_content,
            title="[bold]Command Output[/bold]",
            border_style="dim"
        )

        return [dashboard, output]
