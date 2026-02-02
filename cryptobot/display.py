"""Rich Display Components

Beautiful terminal K-line data display using Rich library
"""

from datetime import datetime
from typing import Optional, List
from array import array

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text


class KlineDisplay:
    """K-line Data Display

    Real-time K-line chart updates using Rich Live Display
    """

    # Chinese convention: green up, red down
    COLOR_UP = "green"
    COLOR_DOWN = "red"
    COLOR_NEUTRAL = "white"

    # Chart configuration
    CHART_HEIGHT = 15  # K-line chart height (rows)
    CHART_WIDTH = 60   # K-line chart width (chars per candle)

    def __init__(self, console: Optional[Console] = None):
        """Initialize display

        Args:
            console: Rich Console instance, creates new one if not provided
        """
        self.console = console or Console()
        self._kline_history: List[dict] = []
        self._max_history = 30  # Maximum 30 historical records

    def _format_timestamp(self, ts: int) -> str:
        """Format timestamp

        Args:
            ts: Millisecond timestamp

        Returns:
            Formatted time string
        """
        dt = datetime.fromtimestamp(ts / 1000)
        return dt.strftime("%H:%M:%S")

    def _format_timestamp_short(self, ts: int) -> str:
        """Format timestamp (short format)

        Args:
            ts: Millisecond timestamp

        Returns:
            Formatted time string
        """
        dt = datetime.fromtimestamp(ts / 1000)
        return dt.strftime("%H:%M")

    def _get_color(self, open_price: float, close_price: float) -> str:
        """Get color based on price movement

        Args:
            open_price: Open price
            close_price: Close price

        Returns:
            Color name
        """
        if close_price > open_price:
            return self.COLOR_UP
        elif close_price < open_price:
            return self.COLOR_DOWN
        else:
            return self.COLOR_NEUTRAL

    def _create_kline_chart(self) -> Panel:
        """Create ASCII K-line chart

        Returns:
            Rich Panel object containing K-line chart
        """
        if not self._kline_history:
            return Panel("[dim]Waiting for data...[/dim]", title="K-line Chart", style="dim")

        # Get price range
        all_highs = [k["high"] for k in self._kline_history]
        all_lows = [k["low"] for k in self._kline_history]
        min_price = min(all_lows)
        max_price = max(all_highs)
        price_range = max_price - min_price

        if price_range == 0:
            price_range = max_price * 0.001  # Avoid division by zero

        # Calculate Y-axis scale (add padding for breathing room)
        padding = price_range * 0.05  # Reduce padding to 5%
        chart_min = min_price - padding
        chart_max = max_price + padding
        chart_range = chart_max - chart_min

        # Create chart grid (height x width)
        height = self.CHART_HEIGHT
        width = min(len(self._kline_history), self._max_history)

        # Use character art, store (char, color)
        grid = [[("  ", None) for _ in range(width)] for _ in range(height)]

        # Draw each K-line (candlestick)
        for i, kline in enumerate(self._kline_history[-width:]):
            open_p = kline["open"]
            close_p = kline["close"]
            high_p = kline["high"]
            low_p = kline["low"]

            # Calculate positions (using height instead of height-1 to fill entire height)
            high_pos = int((chart_max - high_p) / chart_range * height)
            low_pos = int((chart_max - low_p) / chart_range * height)
            open_pos = int((chart_max - open_p) / chart_range * height)
            close_pos = int((chart_max - close_p) / chart_range * height)

            # Ensure within range (clamp to 0 to height-1 due to rounding)
            high_pos = max(0, min(height - 1, high_pos))
            low_pos = max(0, min(height - 1, low_pos))
            open_pos = max(0, min(height - 1, open_pos))
            close_pos = max(0, min(height - 1, close_pos))

            # Get color
            color = self._get_color(open_p, close_p)

            # Draw body (from open to close)
            body_top = min(open_pos, close_pos)
            body_bottom = max(open_pos, close_pos)

            # Draw upper shadow (from high_pos to body_top, connect to body)
            # If high_pos >= body_top, no upper shadow or shadow is covered by body
            if high_pos < body_top:
                for pos in range(high_pos, body_top + 1):
                    grid[pos][i] = ("│ ", color)

            # Draw lower shadow (from body_bottom to low_pos, connect to body)
            # If low_pos <= body_bottom, no lower shadow or shadow is covered by body
            if low_pos > body_bottom:
                for pos in range(body_bottom, low_pos + 1):
                    grid[pos][i] = ("│ ", color)

            if body_top == body_bottom:
                # Doji: open = close
                grid[body_top][i] = ("─ ", color)
            else:
                for pos in range(body_top, body_bottom + 1):
                    if pos == body_top:
                        grid[pos][i] = ("▀ ", color)
                    elif pos == body_bottom:
                        grid[pos][i] = ("▄ ", color)
                    else:
                        grid[pos][i] = ("█ ", color)

        # Build chart using Rich Text
        from rich.text import Text
        from rich.console import Group as RichGroup

        renderables = []

        # Draw Y-axis scale and chart
        for row in range(height):
            # Use height instead of height-1, consistent with position calculation
            price = chart_max - (row / height) * chart_range
            price_label = f"{price:8.2f} │"

            line_text = Text()
            line_text.append(price_label)

            for cell in grid[row]:
                char, color = cell
                if color:
                    line_text.append(char, style=color)
                else:
                    line_text.append(char)

            renderables.append(line_text)

        # Draw X-axis (time)
        time_line = "         └" + "─ " * width
        renderables.append(Text(time_line))

        time_labels = Text("         ")
        for i, kline in enumerate(self._kline_history[-width:]):
            if i % 5 == 0:  # Show time label every 5 candlesticks
                ts = self._format_timestamp_short(kline["timestamp"])
                time_labels.append(ts[:2] + " ")
            else:
                time_labels.append("  ")
        renderables.append(time_labels)

        # Add latest price information
        if self._kline_history:
            latest = self._kline_history[-1]
            change = latest["close"] - latest["open"]
            change_pct = (change / latest["open"]) * 100
            change_color = self.COLOR_UP if change > 0 else self.COLOR_DOWN if change < 0 else "white"
            change_sign = "+" if change > 0 else ""

            info = (
                f"\n[bold]Latest:[/bold] {latest['close']:.2f}  "
                f"[bold]Change:[/bold] [{change_color}]{change_sign}{change:.2f} ({change_pct:.2f}%)[/]  "
                f"[bold]High:[/bold] {latest['high']:.2f}  "
                f"[bold]Low:[/bold] {latest['low']:.2f}  "
                f"[bold]Volume:[/bold] {latest['volume']:.2f}"
            )
            renderables.append(Text(info, justify="left"))

        return Panel(RichGroup(*renderables), title="K-line Chart", style="dim")

    def _create_kline_table(self) -> Table:
        """Create K-line data table

        Returns:
            Rich Table object
        """
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("K-line", style="cyan")

        # Show last 8 records
        recent = self._kline_history[-8:]

        for kline in recent:
            open_p = kline["open"]
            close_p = kline["close"]
            color = self._get_color(open_p, close_p)
            ts = self._format_timestamp(kline["timestamp"])

            # Calculate K-line display
            body_char = "█" if abs(close_p - open_p) > 0.01 else "─"
            trend_symbol = "↑" if close_p > open_p else "↓" if close_p < open_p else "→"

            line = (
                f"[dim]{ts}[/dim]  "
                f"[{color}]{trend_symbol}[/] "
                f"O:[cyan]{open_p:.2f}[/cyan] "
                f"H:[cyan]{kline['high']:.2f}[/cyan] "
                f"L:[cyan]{kline['low']:.2f}[/cyan] "
                f"C:[{color}]{close_p:.2f}[/] "
                f"V:[dim]{kline['volume']:.2f}[/dim]"
            )
            table.add_row(line)

        return table

    def _create_status_panel(self, symbol: str, exchange: str, interval: str) -> Panel:
        """Create status bar panel

        Args:
            symbol: Trading pair
            exchange: Exchange
            interval: K-line interval

        Returns:
            Rich Panel object
        """
        status_text = (
            f"[bold cyan]Exchange:[/bold cyan] {exchange.upper()}  "
            f"[bold cyan]Trading Pair:[/bold cyan] {symbol.upper()}  "
            f"[bold cyan]Timeframe:[/bold cyan] {interval}  "
            f"[bold yellow]Press space to stop subscription[/bold yellow]"
        )
        return Panel(status_text, style="dim")

    def update_kline(self, kline: dict):
        """Update K-line data

        Unclosed K-lines are overwritten, closed K-lines are finalized,
        new K-lines are appended to the end

        Args:
            kline: K-line data dictionary
        """
        # Check if we need to update the last K-line (same timestamp and not closed)
        if self._kline_history:
            last_kline = self._kline_history[-1]

            # Same K-line (same timestamp): overwrite update
            if last_kline["timestamp"] == kline["timestamp"]:
                self._kline_history[-1] = kline
                return

            # Last K-line not closed: update it
            if not last_kline.get("is_closed", True):
                self._kline_history[-1] = kline
                return

        # New closed K-line or first K-line: append to end
        self._kline_history.append(kline)
        # Maintain history size
        if len(self._kline_history) > self._max_history:
            self._kline_history.pop(0)

    def clear_history(self):
        """Clear historical data"""
        self._kline_history.clear()

    def generate_display(
        self,
        symbol: str,
        exchange: str,
        interval: str,
    ) -> str:
        """Generate display content

        Args:
            symbol: Trading pair
            exchange: Exchange
            interval: K-line interval

        Returns:
            Formatted display string
        """
        chart = self._create_kline_chart()
        table = self._create_kline_table()
        panel = self._create_status_panel(symbol, exchange, interval)

        # Use Console to capture output
        with self.console.capture() as capture:
            self.console.print(panel)
            self.console.print(chart)
            self.console.print(table)

        return capture.get()

    def display_live(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        stop_event,
    ):
        """Start Live Display

        This is a generator that yields new display content on each K-line update

        Args:
            symbol: Trading pair
            exchange: Exchange
            interval: K-line interval
            stop_event: Stop event (asyncio.Event)

        Yields:
            Formatted display content
        """
        while not stop_event.is_set():
            yield self.generate_display(symbol, exchange, interval)
