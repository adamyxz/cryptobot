"""Rich 显示组件

使用 Rich 库实现美观的终端 K线数据展示
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
    """K线数据显示器

    使用 Rich Live Display 实时更新 K线图表
    """

    # 中国习惯：绿涨红跌
    COLOR_UP = "green"
    COLOR_DOWN = "red"
    COLOR_NEUTRAL = "white"

    # 图表配置
    CHART_HEIGHT = 15  # K线图高度（行数）
    CHART_WIDTH = 60   # K线图宽度（每根K线占用字符数）

    def __init__(self, console: Optional[Console] = None):
        """初始化显示器

        Args:
            console: Rich Console 实例，如不提供则创建新的
        """
        self.console = console or Console()
        self._kline_history: List[dict] = []
        self._max_history = 30  # 最多保留 30 条历史

    def _format_timestamp(self, ts: int) -> str:
        """格式化时间戳

        Args:
            ts: 毫秒时间戳

        Returns:
            格式化的时间字符串
        """
        dt = datetime.fromtimestamp(ts / 1000)
        return dt.strftime("%H:%M:%S")

    def _format_timestamp_short(self, ts: int) -> str:
        """格式化时间戳（短格式）

        Args:
            ts: 毫秒时间戳

        Returns:
            格式化的时间字符串
        """
        dt = datetime.fromtimestamp(ts / 1000)
        return dt.strftime("%H:%M")

    def _get_color(self, open_price: float, close_price: float) -> str:
        """根据涨跌获取颜色

        Args:
            open_price: 开盘价
            close_price: 收盘价

        Returns:
            颜色名称
        """
        if close_price > open_price:
            return self.COLOR_UP
        elif close_price < open_price:
            return self.COLOR_DOWN
        else:
            return self.COLOR_NEUTRAL

    def _create_kline_chart(self) -> Panel:
        """创建 ASCII K线图

        Returns:
            Rich Panel 对象包含 K线图
        """
        if not self._kline_history:
            return Panel("[dim]等待数据...[/dim]", title="K线图", style="dim")

        # 获取价格范围
        all_highs = [k["high"] for k in self._kline_history]
        all_lows = [k["low"] for k in self._kline_history]
        min_price = min(all_lows)
        max_price = max(all_highs)
        price_range = max_price - min_price

        if price_range == 0:
            price_range = max_price * 0.001  # 避免除零

        # 计算Y轴刻度（添加padding让K线图有呼吸空间）
        padding = price_range * 0.05  # 减小padding到5%
        chart_min = min_price - padding
        chart_max = max_price + padding
        chart_range = chart_max - chart_min

        # 创建图表网格 (height x width)
        height = self.CHART_HEIGHT
        width = min(len(self._kline_history), self._max_history)

        # 使用字符画，存储 (字符, 颜色)
        grid = [[("  ", None) for _ in range(width)] for _ in range(height)]

        # 绘制每根 K线
        for i, kline in enumerate(self._kline_history[-width:]):
            open_p = kline["open"]
            close_p = kline["close"]
            high_p = kline["high"]
            low_p = kline["low"]

            # 计算位置（使用height而非height-1，让价格能够填充整个高度）
            high_pos = int((chart_max - high_p) / chart_range * height)
            low_pos = int((chart_max - low_p) / chart_range * height)
            open_pos = int((chart_max - open_p) / chart_range * height)
            close_pos = int((chart_max - close_p) / chart_range * height)

            # 确保在范围内（由于四舍五入，需要clamp到0到height-1）
            high_pos = max(0, min(height - 1, high_pos))
            low_pos = max(0, min(height - 1, low_pos))
            open_pos = max(0, min(height - 1, open_pos))
            close_pos = max(0, min(height - 1, close_pos))

            # 获取颜色
            color = self._get_color(open_p, close_p)

            # 绘制实体（从 open 到 close）
            body_top = min(open_pos, close_pos)
            body_bottom = max(open_pos, close_pos)

            # 绘制上影线（从 high_pos 到 body_top，连接到实体）
            # 如果 high_pos >= body_top，说明没有上影线或上影线被实体覆盖
            if high_pos < body_top:
                for pos in range(high_pos, body_top + 1):
                    grid[pos][i] = ("│ ", color)

            # 绘制下影线（从 body_bottom 到 low_pos，连接到实体）
            # 如果 low_pos <= body_bottom，说明没有下影线或下影线被实体覆盖
            if low_pos > body_bottom:
                for pos in range(body_bottom, low_pos + 1):
                    grid[pos][i] = ("│ ", color)

            if body_top == body_bottom:
                # 十字星：开盘=收盘
                grid[body_top][i] = ("─ ", color)
            else:
                for pos in range(body_top, body_bottom + 1):
                    if pos == body_top:
                        grid[pos][i] = ("▀ ", color)
                    elif pos == body_bottom:
                        grid[pos][i] = ("▄ ", color)
                    else:
                        grid[pos][i] = ("█ ", color)

        # 使用 Rich Text 构建图表
        from rich.text import Text
        from rich.console import Group as RichGroup

        renderables = []

        # 绘制 Y 轴刻度和图表
        for row in range(height):
            # 使用height而非height-1，与位置计算保持一致
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

        # 绘制 X 轴（时间）
        time_line = "         └" + "─ " * width
        renderables.append(Text(time_line))

        time_labels = Text("         ")
        for i, kline in enumerate(self._kline_history[-width:]):
            if i % 5 == 0:  # 每5根 K线显示一个时间
                ts = self._format_timestamp_short(kline["timestamp"])
                time_labels.append(ts[:2] + " ")
            else:
                time_labels.append("  ")
        renderables.append(time_labels)

        # 添加最新价格信息
        if self._kline_history:
            latest = self._kline_history[-1]
            change = latest["close"] - latest["open"]
            change_pct = (change / latest["open"]) * 100
            change_color = self.COLOR_UP if change > 0 else self.COLOR_DOWN if change < 0 else "white"
            change_sign = "+" if change > 0 else ""

            info = (
                f"\n[bold]最新:[/bold] {latest['close']:.2f}  "
                f"[bold]涨跌:[/bold] [{change_color}]{change_sign}{change:.2f} ({change_pct:.2f}%)[/]  "
                f"[bold]高:[/bold] {latest['high']:.2f}  "
                f"[bold]低:[/bold] {latest['low']:.2f}  "
                f"[bold]量:[/bold] {latest['volume']:.2f}"
            )
            renderables.append(Text(info, justify="left"))

        return Panel(RichGroup(*renderables), title="K线图", style="dim")

    def _create_kline_table(self) -> Table:
        """创建 K线数据表格

        Returns:
            Rich Table 对象
        """
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("K线", style="cyan")

        # 显示最近的 8 条数据
        recent = self._kline_history[-8:]

        for kline in recent:
            open_p = kline["open"]
            close_p = kline["close"]
            color = self._get_color(open_p, close_p)
            ts = self._format_timestamp(kline["timestamp"])

            # 计算 K线显示
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
        """创建状态栏面板

        Args:
            symbol: 交易对
            exchange: 交易所
            interval: K线间隔

        Returns:
            Rich Panel 对象
        """
        status_text = (
            f"[bold cyan]交易所:[/bold cyan] {exchange.upper()}  "
            f"[bold cyan]交易对:[/bold cyan] {symbol.upper()}  "
            f"[bold cyan]周期:[/bold cyan] {interval}  "
            f"[bold yellow]按空格键停止订阅[/bold yellow]"
        )
        return Panel(status_text, style="dim")

    def update_kline(self, kline: dict):
        """更新 K线数据

        未收盘的 K线 会覆盖更新，收盘的 K线 会被定格，新 K线 添加到末尾

        Args:
            kline: K线数据字典
        """
        # 检查是否需要更新最后一根 K线（同一时间戳且未收盘）
        if self._kline_history:
            last_kline = self._kline_history[-1]

            # 同一根 K线（时间戳相同）：覆盖更新
            if last_kline["timestamp"] == kline["timestamp"]:
                self._kline_history[-1] = kline
                return

            # 最后一根 K线 未收盘：更新它
            if not last_kline.get("is_closed", True):
                self._kline_history[-1] = kline
                return

        # 新的已收盘 K线或第一根 K线：添加到末尾
        self._kline_history.append(kline)
        # 保持历史记录数量
        if len(self._kline_history) > self._max_history:
            self._kline_history.pop(0)

    def clear_history(self):
        """清空历史数据"""
        self._kline_history.clear()

    def generate_display(
        self,
        symbol: str,
        exchange: str,
        interval: str,
    ) -> str:
        """生成显示内容

        Args:
            symbol: 交易对
            exchange: 交易所
            interval: K线间隔

        Returns:
            格式化的显示字符串
        """
        chart = self._create_kline_chart()
        table = self._create_kline_table()
        panel = self._create_status_panel(symbol, exchange, interval)

        # 使用 Console 捕获输出
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
        """启动 Live Display

        这是一个生成器，每次 K线更新时 yield 新的显示内容

        Args:
            symbol: 交易对
            exchange: 交易所
            interval: K线间隔
            stop_event: 停止事件（asyncio.Event）

        Yields:
            格式化的显示内容
        """
        while not stop_event.is_set():
            yield self.generate_display(symbol, exchange, interval)
