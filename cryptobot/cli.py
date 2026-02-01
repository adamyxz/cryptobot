"""CLI 核心逻辑

使用 Prompt Toolkit 处理用户输入
"""

import asyncio
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console

from .exchanges import (
    get_exchange_config,
    get_supported_exchanges,
    get_region_hint,
    fetch_klines_ccxt,
    fetch_pairs_ccxt,
)
from .display import KlineDisplay
from .trader_db import TraderDatabase
from .position_db import PositionDatabase
from .position import Position, PositionSide, PositionStatus
from .fees import calculate_fee
from .price_service import get_price_service


def is_interactive_terminal() -> bool:
    """检查是否在交互式终端中运行

    Returns:
        是否为交互式终端
    """
    return sys.stdout.isatty()


class CryptoBot:
    """CryptoBot 主类

    管理用户交互和数据显示
    """

    DEFAULT_EXCHANGE = "binance"
    DEFAULT_SYMBOL = "BTCUSDT"
    DEFAULT_INTERVAL = "1m"

    def __init__(self):
        """初始化 CLI"""
        self.console = Console()
        self.display = KlineDisplay(self.console)
        self.session = PromptSession()
        self._stop_subscription = asyncio.Event()

    def _print_banner(self):
        """打印欢迎横幅"""
        banner = """
[bold cyan]╔═══════════════════════════════════════════════════════════╗
║                    CryptoBot v0.1.0                          ║
║              永续合约K线数据订阅工具 (CCXT)                   ║
╚═══════════════════════════════════════════════════════════╝[/bold cyan]

[dim]支持的交易所: {exchanges}[/dim]
[dim]默认参数: {default_exchange} {default_symbol} {default_interval}[/dim]
[dim]数据类型: 永续合约 (Perpetual Futures/Swap)[/dim]

[bold yellow]命令:[/bold yellow]
  /rest [exchange] [symbol] [interval] [limit]  - 获取历史 K线 (REST)
  /pairs [exchange]  - 显示支持的交易对
  /intervals  - 显示支持的周期
  /traders [id] [-p]  - 查看/修改交易者档案 (查看仓位使用 -p)
  /newtrader [prompt]  - Generate new trader using AI
  /decide <trader_id>  - AI 自动交易决策 (CSV 指标)
  /openposition <trader_id> <exchange> <symbol> <side> <size> [leverage]  - 开仓
  /closeposition <position_id> [price]  - 平仓
  /help  - 显示帮助
  /quit 或 /exit  - 退出程序

[dim green]✓ 自动清算监控已启用 (查看仓位时自动检查)[/dim green]
[dim]提示: 按 Ctrl+C 停止当前操作[/dim]
""".format(
            exchanges=", ".join(get_supported_exchanges()),
            default_exchange=self.DEFAULT_EXCHANGE,
            default_symbol=self.DEFAULT_SYMBOL,
            default_interval=self.DEFAULT_INTERVAL,
        )
        self.console.print(banner)

    def _print_help(self):
        """显示帮助信息"""
        help_text = """
[bold cyan]命令帮助[/bold cyan]

[bold yellow]/rest [exchange] [symbol] [interval] [limit][/bold yellow]
  获取历史 K线数据 (REST API 一次性获取，静态显示)
  数据类型: 永续合约 (Perpetual Futures/Swap)
  参数说明:
    exchange  - 交易所名称 (binance, okx, bybit, bitget)，默认: {default_exchange}
    symbol    - 交易对 (如 BTCUSDT)，默认: {default_symbol}
    interval  - K线周期 (1m, 5m, 15m, 1h, 1d)，默认: {default_interval}
    limit     - 获取条数 (1-1000)，默认: 30

  示例:
    /rest                          # 使用默认参数 (30 条)
    /rest okx                      # 指定交易所
    /rest okx ETHUSDT              # 指定交易所和交易对
    /rest binance ETHUSDT 5m 100   # 指定所有参数 (获取 100 条)

[bold yellow]/pairs [exchange][/bold yellow]
  显示支持的交易对
  数据类型: 永续合约 (Perpetual Futures/Swap)
  参数说明:
    exchange  - 交易所名称 (binance, okx, bybit, bitget)，默认: {default_exchange}

  示例:
    /pairs          # 显示默认交易所的交易对
    /pairs binance  # 显示 Binance 的交易对

[bold yellow]/intervals[/bold yellow]
  显示支持的 K线周期

  支持的周期: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d, 1w, 1M

[bold yellow]/traders [trader_id] [-d] [-p] [prompt][/bold yellow]
  查看所有交易者、查看单个交易者、删除、修改交易者或查看仓位
  参数说明:
    trader_id  - 交易者 ID（可选）
    -d         - 删除标志（需要配合 trader_id 使用）
    -p         - 显示仓位信息（需要配合 trader_id 使用）
    prompt     - 修改提示词（当提供 trader_id 和 prompt 时修改交易者）

  示例:
    /traders                    # 显示所有交易者信息
    /traders 1                  # 显示 ID 为 1 的交易者详情
    /traders 1 -p               # 显示 ID 为 1 的交易者的仓位信息
    /traders 1 -d               # 删除 ID 为 1 的交易者（包括数据库和 md 文件）
    /traders 1 增加杠杆使用     # 使用 Claude Code 修改 ID 为 1 的交易者
    /traders 2 改为保守策略      # 修改 ID 为 2 的交易者的策略为保守型

[bold yellow]/openposition <trader_id> <exchange> <symbol> <side> <size> [leverage][/bold yellow]
  开立永续合约仓位
  参数说明:
    trader_id  - 交易者 ID
    exchange   - 交易所名称 (binance, okx, bybit, bitget)
    symbol     - 交易对 (如 BTCUSDT)
    side       - 方向 (long 或 short)
    size       - 仓位大小（基础货币数量，如 BTC 数量）
    leverage   - 杠杆倍数（可选，默认 1）

  示例:
    /openposition 1 binance BTCUSDT long 0.5 10     # 开 10 倍杠杆多单，0.5 BTC
    /openposition 2 bybit ETHUSDT short 2.0        # 开 1 倍杠杆空单，2 ETH

[bold yellow]/closeposition <position_id> [price][/bold yellow]
  平仓
  参数说明:
    position_id  - 仓位 ID
    price        - 平仓价格（可选，不提供则使用当前市价）

  示例:
    /closeposition 1              # 使用当前市价平仓 ID 为 1 的仓位
    /closeposition 1 45000        # 以 45000 价格平仓 ID 为 1 的仓位

[bold yellow]/newtrader [prompt][/bold yellow]
  Generate a new trading strategy profile using Claude Code AI
  参数说明:
    prompt  - Optional description of desired trader

  示例:
    /newtrader                              # Generate random unique trader
    /newtrader create a conservative trader  # Generate with specific characteristics

  注意: 新的交易者将以文件夹形式创建，如: traders/TraderName_ID/profile.md

[bold yellow]/decide <trader_id>[/bold yellow]
  AI 自动交易决策
  参数说明:
    trader_id  - 交易者 ID

  示例:
    /decide 1              # 为交易员 1 执行 AI 决策

  决策流程:
    1. 收集交易员档案、仓位、PnL 数据
    2. AI 分析是否需要额外市场数据
    3. 如需要，自动调用 indicators/ 中的指标脚本 (CSV 输出)
    4. AI 基于完整数据做出决策并执行

  可能的决策: 开仓 (OPEN_LONG/OPEN_SHORT)、平仓 (CLOSE_POSITION)、清仓 (CLOSE_ALL)、持有 (HOLD)

[bold yellow]/help[/bold yellow]
  显示此帮助信息

[bold yellow]/quit 或 /exit[/bold yellow]
  退出程序

[dim]支持的交易所: {exchanges}[/dim]
[dim]数据来源: CCXT - 统一的加密货币交易所API[/dim]
""".format(
            exchanges=", ".join(get_supported_exchanges()),
            default_exchange=self.DEFAULT_EXCHANGE,
            default_symbol=self.DEFAULT_SYMBOL,
            default_interval=self.DEFAULT_INTERVAL,
        )
        self.console.print(help_text)

    def _parse_command(self, cmd: str) -> Tuple[str, list]:
        """解析用户命令

        Args:
            cmd: 用户输入的命令

        Returns:
            (命令名称, 参数列表)
        """
        parts = cmd.strip().split()
        if not parts:
            return "", []

        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        return command, args

    def _create_key_bindings(self):
        """创建键绑定

        Returns:
            KeyBindings 对象
        """
        bindings = KeyBindings()
        return bindings

    async def _handle_rest_command(self, args: list):
        """处理 /rest 命令

        Args:
            args: 命令参数
        """
        # 解析参数
        exchange = args[0] if len(args) > 0 else self.DEFAULT_EXCHANGE
        symbol = args[1] if len(args) > 1 else self.DEFAULT_SYMBOL
        interval = args[2] if len(args) > 2 else self.DEFAULT_INTERVAL
        limit_str = args[3] if len(args) > 3 else "30"

        # 验证并转换 limit
        try:
            limit = int(limit_str)
            if limit < 1:
                self.console.print("[red]错误: limit 必须 >= 1[/red]")
                return
            if limit > 1000:
                self.console.print("[yellow]警告: limit 最大为 1000，已自动调整[/yellow]")
                limit = 1000
        except ValueError:
            self.console.print(f"[red]错误: 无效的 limit 值: {limit_str}[/red]")
            return

        # 执行 REST 请求
        await self._fetch_rest_klines(exchange, symbol, interval, limit)

    async def _fetch_rest_klines(self, exchange: str, symbol: str, interval: str, limit: int):
        """通过 REST API 获取历史 K线数据（使用 CCXT）

        Args:
            exchange: 交易所名称
            symbol: 交易对
            interval: K线周期
            limit: 获取条数
        """
        self.console.print(
            f"[cyan]正在获取 {exchange.upper()} {symbol} {interval} 永续合约历史数据 (limit={limit})...[/cyan]"
        )

        try:
            # 使用 CCXT 获取数据
            klines = await fetch_klines_ccxt(exchange, symbol, interval, limit)

            if not klines:
                self.console.print("[yellow]未获取到数据[/yellow]")
                return

            self.console.print(f"[green]成功获取 {len(klines)} 条 K线数据[/green]\n")

            # 清空历史并添加新数据
            self.display.clear_history()
            for kline in klines:
                self.display.update_kline(kline)

            # 显示静态图表
            chart = self.display._create_kline_chart()
            table = self.display._create_kline_table()
            panel = self.display._create_status_panel(symbol, exchange, interval)

            from rich.console import Group as RichGroup
            self.console.print(RichGroup(panel, chart, table))

            # 显示统计信息
            if klines:
                latest = klines[-1]
                first = klines[0]
                price_change = latest["close"] - first["open"]
                price_change_pct = (price_change / first["open"]) * 100
                change_color = "green" if price_change > 0 else "red" if price_change < 0 else "white"
                change_sign = "+" if price_change > 0 else ""

                self.console.print(
                    f"\n[dim]时间范围: {self.display._format_timestamp(first['timestamp'])} - "
                    f"{self.display._format_timestamp(latest['timestamp'])}[/dim]"
                )
                self.console.print(
                    f"[dim]价格变化: [{change_color}]{change_sign}{price_change:.2f} "
                    f"({change_sign}{price_change_pct:.2f}%)[/][/dim]"
                )

        except ValueError as e:
            self.console.print(f"[red]错误: {e}[/red]")
        except Exception as e:
            self.console.print(f"[red]错误: {e}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")

    async def _handle_pairs_command(self, args: list):
        """处理 /pairs 命令

        Args:
            args: 命令参数
        """
        exchange = args[0] if len(args) > 0 else self.DEFAULT_EXCHANGE

        # 验证交易所
        try:
            get_exchange_config(exchange)
        except ValueError as e:
            self.console.print(f"[red]错误: {e}[/red]")
            return

        await self._fetch_and_display_pairs(exchange)

    async def _handle_intervals_command(self, args: list):
        """处理 /intervals 命令

        Args:
            args: 命令参数（未使用）
        """
        self._display_supported_intervals()

    async def _handle_traders_command(self, args: list):
        """处理 /traders 命令

        显示所有交易者、查看单个交易者、删除交易者、修改交易者或查看仓位

        Args:
            args: 命令参数 [trader_id] [-d] [-p] [prompt]
        """

        # Parse arguments
        trader_id = None
        delete_flag = False
        positions_flag = False
        edit_prompt = None

        for i, arg in enumerate(args):
            if arg == '-d':
                delete_flag = True
            elif arg == '-p':
                positions_flag = True
            elif not arg.startswith('-') and trader_id is None:
                trader_id = arg
            elif not arg.startswith('-') and trader_id is not None:
                # Remaining arguments form the edit prompt
                edit_prompt = ' '.join(args[i:])
                break

        # Initialize database
        db = TraderDatabase()
        db.initialize()

        try:
            # Case 1: Delete trader
            if delete_flag:
                if not trader_id:
                    self.console.print("[red]错误: 删除操作需要指定交易者 ID[/red]")
                    self.console.print("[yellow]用法: /traders <trader_id> -d[/yellow]")
                    return

                self._delete_trader(db, trader_id)
                return

            # Case 2: Edit trader (new feature)
            if trader_id and edit_prompt:
                await self._edit_trader(db, trader_id, edit_prompt)
                return

            # Case 3: Show trader positions
            if trader_id and positions_flag:
                await self._show_trader_positions(trader_id)
                return

            # Case 4: Show specific trader
            if trader_id:
                self._show_trader_detail(db, trader_id)
                return

            # Case 3: Show all traders
            traders = db.list_traders()

            if not traders:
                self.console.print("[yellow]暂无交易者档案[/yellow]")
                self.console.print("[dim]使用 /newtrader 命令创建新的交易者档案[/dim]")
                return

            # Display traders in a table
            from rich.table import Table
            from rich.panel import Panel

            # Create main table
            table = Table(title=f"[bold cyan]交易者档案列表[/bold cyan] (共 {len(traders)} 个)", show_header=True, header_style="bold magenta")
            table.add_column("ID", style="cyan", width=10)
            table.add_column("交易风格", style="green", width=20)
            table.add_column("风险偏好", style="yellow", width=12)
            table.add_column("交易对", style="blue", width=30)
            table.add_column("创建时间", style="dim", width=16)

            for trader in traders:
                # Extract characteristics
                chars = trader.get('characteristics', {})
                risk = chars.get('risk_tolerance', 'N/A')

                # Get trading pairs (limit to 3 for display)
                pairs = trader.get('trading_pairs', [])
                pairs_str = ', '.join(pairs[:3]) if pairs else 'N/A'
                if len(pairs) > 3:
                    pairs_str += f' (+{len(pairs) - 3})'

                # Format style
                style = trader.get('style', 'N/A').replace('_', ' ').title()

                # Format created_at
                created = trader.get('created_at', 'N/A')
                if created != 'N/A':
                    # Format: 2024-02-01 12:34:56 -> 2024-02-01 12:34
                    try:
                        created = created[:16].replace('T', ' ')
                    except:
                        pass

                table.add_row(
                    trader.get('id', 'N/A'),
                    style,
                    risk,
                    pairs_str,
                    created
                )

            self.console.print(table)

            # Show statistics
            stats = db.get_statistics()
            self.console.print("\n[bold cyan]统计信息[/bold cyan]")

            # Style distribution
            by_style = stats.get('by_style', {})
            if by_style:
                from rich.text import Text
                stats_text = Text()
                for style, count in by_style.items():
                    stats_text.append(f"  • {style.replace('_', ' ').title()}: ", style="white")
                    stats_text.append(f"{count}\n", style="green")
                self.console.print(stats_text)

            # Show usage hints
            self.console.print("\n[dim]提示:[/dim]")
            self.console.print("  [dim]/traders <id>           - 查看交易者详情[/dim]")
            self.console.print("  [dim]/traders <id> -p        - 查看交易者仓位[/dim]")
            self.console.print("  [dim]/traders <id> -d        - 删除交易者[/dim]")
            self.console.print("  [dim]/traders <id> <prompt>  - 使用 AI 修改交易者[/dim]")

        except Exception as e:
            self.console.print(f"[red]错误: {e}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
        finally:
            db.close()

    def _delete_trader(self, db, trader_id: str):
        """删除交易者（包括数据库记录和 md 文件）

        Args:
            db: TraderDatabase 实例
            trader_id: 交易者 ID
        """
        import os

        # Get trader info first
        trader = db.get_trader(trader_id)

        if not trader:
            self.console.print(f"[yellow]未找到 ID 为 '{trader_id}' 的交易者[/yellow]")
            return

        # Show trader info for confirmation
        chars = trader.get('characteristics', {})
        name = chars.get('name', 'N/A')
        style = trader.get('style', 'N/A').replace('_', ' ').title()
        trader_file = trader.get('trader_file', '')

        self.console.print(f"\n[bold yellow]即将删除交易者:[/bold yellow]")
        self.console.print(f"  [cyan]ID:[/cyan] {trader_id}")
        self.console.print(f"  [cyan]名称:[/cyan] {name}")
        self.console.print(f"  [cyan]风格:[/cyan] {style}")
        self.console.print(f"  [cyan]文件:[/cyan] {trader_file}")

        # Confirm deletion
        from rich.prompt import Confirm
        if not Confirm.ask("[bold red]确认删除？[/bold red]", default=False):
            self.console.print("[yellow]已取消删除[/yellow]")
            return

        # Delete from database
        success = db.delete_trader(trader_id)

        if not success:
            self.console.print(f"[red]从数据库删除失败[/red]")
            return

        # Delete trader folder (contains profile.md)
        if trader_file and os.path.exists(trader_file):
            trader_folder = os.path.dirname(trader_file)
            try:
                shutil.rmtree(trader_folder)
                self.console.print(f"[green]✓ 已删除文件夹: {trader_folder}[/green]")
            except Exception as e:
                self.console.print(f"[yellow]警告: 无法删除文件夹 {trader_folder}: {e}[/yellow]")
                self.console.print("[dim]文件夹可能已被手动删除或权限不足[/dim]")

        self.console.print(f"[green]✓ 交易者 '{trader_id}' 已成功删除[/green]")

    def _show_trader_detail(self, db, trader_id: str):
        """显示交易者详细信息

        Args:
            db: TraderDatabase 实例
            trader_id: 交易者 ID
        """
        trader = db.get_trader(trader_id)

        if not trader:
            self.console.print(f"[yellow]未找到 ID 为 '{trader_id}' 的交易者[/yellow]")
            return

        # Extract trader info
        chars = trader.get('characteristics', {})
        name = chars.get('name', 'N/A')
        experience = chars.get('experience_level', 'N/A')
        risk = chars.get('risk_tolerance', 'N/A')
        capital = chars.get('capital_allocation', 'N/A')

        style = trader.get('style', 'N/A').replace('_', ' ').title()
        pairs = trader.get('trading_pairs', [])
        timeframes = trader.get('timeframes', [])
        indicators = trader.get('indicators', [])
        trader_file = trader.get('trader_file', 'N/A')
        created = trader.get('created_at', 'N/A')

        # Format created_at
        if created != 'N/A':
            try:
                created = created[:16].replace('T', ' ')
            except:
                pass

        # Display trader info
        from rich.panel import Panel
        from rich.text import Text

        # Title
        title_text = Text()
        title_text.append(f"交易者详情: {name} ", style="bold cyan")
        title_text.append(f"(ID: {trader_id})", style="dim")

        # Content
        content = f"""
[bold yellow]基本信息[/bold yellow]
  名称: {name}
  经验等级: {experience}
  风险偏好: {risk}
  资金配置: {capital}

[bold yellow]交易风格[/bold yellow]
  风格: {style}
  时间周期: {', '.join(timeframes) if timeframes else 'N/A'}

[bold yellow]交易工具[/bold yellow]
  交易对:
"""

        for pair in pairs[:10]:
            content += f"    • {pair}\n"
        if len(pairs) > 10:
            content += f"    ... 还有 {len(pairs) - 10} 个\n"

        content += f"\n  技术指标 ({len(indicators)} 个):\n"
        for indicator in indicators[:8]:
            content += f"    • {indicator}\n"
        if len(indicators) > 8:
            content += f"    ... 还有 {len(indicators) - 8} 个\n"

        content += f"""
[bold yellow]其他信息[/bold yellow]
  创建时间: {created}
  文件路径: {trader_file}
"""

        panel = Panel(content, title=title_text, border_style="cyan")
        self.console.print(panel)

    async def _edit_trader(self, db, trader_id: str, prompt: str):
        """编辑交易者（使用 Claude Code 修改 md 文件和数据库）

        Args:
            db: TraderDatabase 实例
            trader_id: 交易者 ID
            prompt: 修改提示词
        """
        import os
        import subprocess

        # Get trader info first
        trader = db.get_trader(trader_id)

        if not trader:
            self.console.print(f"[yellow]未找到 ID 为 '{trader_id}' 的交易者[/yellow]")
            return

        # Get trader file path
        trader_file = trader.get('trader_file', '')
        if not trader_file or not os.path.exists(trader_file):
            self.console.print(f"[red]错误: 找不到交易者文件 {trader_file}[/red]")
            return

        # Show trader info
        chars = trader.get('characteristics', {})
        name = chars.get('name', 'N/A')
        style = trader.get('style', 'N/A').replace('_', ' ').title()

        self.console.print(f"\n[bold cyan]正在修改交易者:[/bold cyan]")
        self.console.print(f"  [dim]ID:[/dim] {trader_id}")
        self.console.print(f"  [dim]名称:[/dim] {name}")
        self.console.print(f"  [dim]风格:[/dim] {style}")
        self.console.print(f"  [dim]文件:[/dim] {trader_file}")
        self.console.print(f"  [dim]修改要求:[/dim] {prompt}\n")

        # Check if TRADERS.md exists
        project_root = Path(__file__).parent.parent
        traders_guide = project_root / "traders" / "TRADERS.md"

        if not traders_guide.exists():
            self.console.print(f"[red]错误: 找不到 {traders_guide}[/red]")
            return

        # Find Claude Code executable
        claude_path = shutil.which("claude")
        if not claude_path:
            self.console.print(
                "[red]错误: 未找到 Claude Code 可执行文件[/red]"
            )
            self.console.print(
                "[yellow]请访问 https://code.claude.com 安装 Claude Code[/yellow]"
            )
            return

        # Store file modification time before editing
        mtime_before = os.path.getmtime(trader_file)

        # Prepare instructions for Claude Code
        instructions = f"""You are editing an existing trader profile. Follow these steps:

1. Read the TRADERS.md file for the trader profile template and guidelines.

2. Read the current trader file: profile.md in the current directory

3. Your task: {prompt}

4. IMPORTANT Editing Rules:
   - Keep the same Trader ID: {trader_id}
   - Keep the same folder structure (profile.md file name)
   - Maintain the markdown structure and template from TRADERS.md
   - Only modify the relevant sections based on the user's request
   - Preserve information that isn't directly related to the change request
   - Save your changes to profile.md in the current directory

5. After making changes, verify:
   - The file follows the TRADERS.md template structure
   - All required sections are present
   - The Trader ID remains unchanged

Edit the profile.md file now."""

        self.console.print("[cyan]正在调用 Claude Code 修改交易者档案...[/cyan]\n")

        try:
            # Run Claude Code as subprocess
            result = subprocess.run(
                [claude_path, "--print", instructions],
                cwd=str(os.path.dirname(trader_file)),
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            # Check if file was modified
            mtime_after = os.path.getmtime(trader_file)

            if mtime_after == mtime_before:
                self.console.print("[yellow]未检测到文件修改[/yellow]")
                self.console.print(f"[dim]Claude Code 输出:\n{result.stdout}[/dim]")
                if result.stderr:
                    self.console.print(f"[dim]错误:\n{result.stderr}[/dim]")
                return

            # Re-parse the modified trader file
            trader_path = Path(trader_file)
            updated_data = self._parse_trader_file(trader_path)

            # Prepare database update record
            update_record = {
                'characteristics': updated_data.get('characteristics', {}),
                'style': updated_data.get('style', ''),
                'strategy': updated_data.get('strategy', {}),
                'trading_pairs': updated_data.get('trading_pairs', []),
                'timeframes': updated_data.get('timeframes', []),
                'indicators': updated_data.get('indicators', []),
                'information_sources': updated_data.get('information_sources', []),
                'metadata': updated_data.get('metadata', {})
            }

            # Update database
            success = db.update_trader(trader_id, update_record)

            if success:
                self.console.print(f"[green]✓ 交易者 '{trader_id}' 已成功修改[/green]")
                self.console.print(f"[dim]数据库记录已同步更新[/dim]")
            else:
                self.console.print(f"[yellow]警告: 文件已修改，但数据库更新失败[/yellow]")

            # Show Claude output if there were issues
            if result.returncode != 0:
                self.console.print(f"\n[dim]Claude Code 退出码: {result.returncode}[/dim]")
                if result.stderr:
                    self.console.print(f"[dim]错误输出:\n{result.stderr}[/dim]")

        except subprocess.TimeoutExpired:
            self.console.print("[red]错误: Claude Code 执行超时 (5分钟)[/red]")
        except Exception as e:
            self.console.print(f"[red]错误: {e}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")

    async def _fetch_and_display_pairs(self, exchange: str):
        """获取并显示交易所的永续合约交易对

        Args:
            exchange: 交易所名称
        """
        self.console.print(f"[cyan]正在获取 {exchange.upper()} 永续合约交易对列表...[/cyan]")

        try:
            # 使用 CCXT 获取永续合约市场
            markets = await fetch_pairs_ccxt(exchange)

            if not markets:
                self.console.print("[yellow]未获取到交易对数据[/yellow]")
                return

            # 过滤活跃的 USDT 永续合约
            usdt_pairs = []
            for market in markets:
                symbol = market['symbol']
                # 只显示活跃的 USDT 合约
                if market.get('active', True) and 'USDT' in symbol.upper():
                    # 标准化 symbol 显示（移除 CCXT 特殊格式）
                    display_symbol = symbol.replace('/', '').replace(':', '').replace('-', '')
                    usdt_pairs.append({
                        'symbol': display_symbol,
                        'ccxt_symbol': symbol,
                        'base': market.get('base'),
                        'contract': market.get('contract', True),
                    })

            # 显示交易对
            self.console.print(f"\n[green]{exchange.upper()} 支持的 USDT 永续合约 (共 {len(usdt_pairs)} 个):[/green]\n")

            # 使用 Rich 表格显示
            from rich.table import Table

            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("排名", style="dim", width=6)
            table.add_column("交易对", style="cyan", width=16)
            table.add_column("基础币", style="green", width=12)
            table.add_column("排名", style="dim", width=6)
            table.add_column("交易对", style="cyan", width=16)
            table.add_column("基础币", style="green", width=12)

            # 分两列显示，显示前100个交易对
            max_display = min(100, len(usdt_pairs))
            for i in range(0, max_display, 2):
                if i + 1 < max_display:
                    pair1 = usdt_pairs[i]
                    pair2 = usdt_pairs[i + 1]
                    table.add_row(
                        str(i + 1),
                        pair1['symbol'],
                        pair1.get('base', 'N/A'),
                        str(i + 2),
                        pair2['symbol'],
                        pair2.get('base', 'N/A'),
                    )
                else:
                    pair1 = usdt_pairs[i]
                    table.add_row(
                        str(i + 1),
                        pair1['symbol'],
                        pair1.get('base', 'N/A'),
                        "",
                        "",
                        "",
                    )

            self.console.print(table)

            if len(usdt_pairs) > max_display:
                self.console.print(f"\n[dim]注: 仅显示前 {max_display} 个交易对，共 {len(usdt_pairs)} 个[/dim]")

            self.console.print(f"\n[dim]提示: 使用 /rest {exchange} <交易对> <周期> 获取更多数据[/dim]")
            self.console.print(f"[dim]注意: 所有数据均为永续合约（perpetual futures/swap）数据[/dim]")

        except ValueError as e:
            self.console.print(f"[red]错误: {e}[/red]")
        except Exception as e:
            self.console.print(f"[red]错误: {e}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")

    def _display_supported_intervals(self):
        """显示支持的 K线周期"""
        intervals = [
            ("1m", "1 分钟"),
            ("3m", "3 分钟"),
            ("5m", "5 分钟"),
            ("15m", "15 分钟"),
            ("30m", "30 分钟"),
            ("1h", "1 小时"),
            ("2h", "2 小时"),
            ("4h", "4 小时"),
            ("6h", "6 小时"),
            ("12h", "12 小时"),
            ("1d", "1 天"),
            ("1w", "1 周"),
            ("1M", "1 月"),
        ]

        from rich.table import Table

        table = Table(title="支持的 K线周期", show_header=True, header_style="bold cyan")
        table.add_column("周期代码", style="green", width=8)
        table.add_column("说明", style="white", width=12)
        table.add_column("周期代码", style="green", width=8)
        table.add_column("说明", style="white", width=12)

        # 分两列显示
        for i in range(0, len(intervals), 2):
            if i + 1 < len(intervals):
                table.add_row(
                    intervals[i][0], intervals[i][1],
                    intervals[i + 1][0], intervals[i + 1][1]
                )
            else:
                table.add_row(intervals[i][0], intervals[i][1], "", "")

        self.console.print(table)
        self.console.print("\n[dim]提示: 使用 /rest <交易所> <交易对> <周期> 获取更多数据[/dim]")

    def _parse_trader_file(self, trader_file: Path) -> dict:
        """Extract metadata from a trader markdown file

        Args:
            trader_file: Path to the trader markdown file

        Returns:
            Dictionary with extracted metadata including:
            - characteristics, style, strategy, trading_pairs, timeframes,
              indicators, information_sources, and metadata
        """
        import re

        result = {
            'characteristics': {},
            'style': '',
            'strategy': {},
            'trading_pairs': [],
            'timeframes': [],
            'indicators': [],
            'information_sources': [],
            'metadata': {'parse_errors': []}
        }

        try:
            content = trader_file.read_text(encoding='utf-8')

            # Extract Trader ID
            id_match = re.search(r'\*\*Trader ID:\*\*\s*`([^`]+)`', content)
            if id_match:
                result['id'] = id_match.group(1)
            else:
                # 从文件名提取数字ID（格式：TraderName_123.md）
                import re
                filename = trader_file.stem  # 去掉.md后缀
                numbers = re.findall(r'\d+', filename)
                if numbers:
                    # 使用数字部分作为ID
                    result['id'] = numbers[-1]
                else:
                    # 如果没有数字，使用整个文件名
                    result['id'] = filename

            # Extract Identity section
            name_match = re.search(r'- \*\*Name:\*\*\s*(.+)', content)
            if name_match:
                result['characteristics']['name'] = name_match.group(1).strip()

            experience_match = re.search(r'- \*\*Experience Level:\*\*\s*(.+)', content)
            if experience_match:
                result['characteristics']['experience_level'] = experience_match.group(1).strip()

            # Extract Characteristics
            risk_match = re.search(r'- \*\*Risk Tolerance:\*\*\s*(.+)', content)
            if risk_match:
                result['characteristics']['risk_tolerance'] = risk_match.group(1).strip()

            capital_match = re.search(r'- \*\*Capital Allocation:\*\*\s*(.+)', content)
            if capital_match:
                result['characteristics']['capital_allocation'] = capital_match.group(1).strip()

            # Extract Trading Style
            style_match = re.search(r'- \*\*Primary Style:\*\*\s*(.+)', content)
            if style_match:
                result['style'] = style_match.group(1).strip().lower().replace(' ', '_')

            holding_match = re.search(r'- \*\*Holding Period:\*\*\s*(.+)', content)
            if holding_match:
                result['characteristics']['holding_period'] = holding_match.group(1).strip()

            # Extract Trading Instruments (Primary Assets)
            assets_match = re.search(r'- \*\*Primary Assets:\*\*\s*(.+)', content)
            if assets_match:
                assets_str = assets_match.group(1).strip()
                result['trading_pairs'] = [a.strip() for a in assets_str.split(',')]

            pairs_match = re.search(r'- \*\*Preferred Pairs:\*\*\s*(.+)', content)
            if pairs_match:
                pairs_str = pairs_match.group(1).strip()
                result['trading_pairs'].extend([p.strip() for p in pairs_str.split(',')])

            # Extract Timeframes
            analysis_tf_match = re.search(r'- \*\*Analysis Timeframe:\*\*\s*(.+)', content)
            if analysis_tf_match:
                result['timeframes'].append(analysis_tf_match.group(1).strip())

            entry_tf_match = re.search(r'- \*\*Entry Timeframe:\*\*\s*(.+)', content)
            if entry_tf_match:
                result['timeframes'].append(entry_tf_match.group(1).strip())

            # Extract Technical Indicators
            indicators_section = re.search(r'## Technical Indicators\n(.*?)##', content, re.DOTALL)
            if indicators_section:
                # Extract list items from the section
                indicator_matches = re.findall(r'^-\s+(.+)$', indicators_section.group(1), re.MULTILINE)
                for indicator in indicator_matches:
                    # Clean up the indicator text (remove ** and other markdown)
                    clean_indicator = re.sub(r'\*\*', '', indicator).strip()
                    if clean_indicator:
                        result['indicators'].append(clean_indicator)

            # Extract Information Sources
            sources_section = re.search(r'## Information Sources\n(.*?)##', content, re.DOTALL)
            if sources_section:
                # Extract various source types
                news_match = re.search(r'- \*\*News Sources:\*\*\s*(.+)', sources_section.group(1))
                if news_match:
                    result['information_sources'].extend(
                        ['news:' + s.strip() for s in news_match.group(1).split(',')]
                    )

                onchain_match = re.search(r'- \*\*On-chain Data:\*\*\s*(.+)', sources_section.group(1))
                if onchain_match:
                    result['information_sources'].extend(
                        ['onchain:' + s.strip() for s in onchain_match.group(1).split(',')]
                    )

                social_match = re.search(r'- \*\*Social Sentiment:\*\*\s*(.+)', sources_section.group(1))
                if social_match:
                    result['information_sources'].extend(
                        ['social:' + s.strip() for s in social_match.group(1).split(',')]
                    )

            # Extract Strategy elements
            entry_section = re.search(r'### Entry Conditions\n(.*?)###', content, re.DOTALL)
            if entry_section:
                result['strategy']['entry_conditions'] = entry_section.group(1).strip()[:500]

            exit_section = re.search(r'### Exit Conditions\n(.*?)###', content, re.DOTALL)
            if exit_section:
                result['strategy']['exit_conditions'] = exit_section.group(1).strip()[:500]

            # Clean up lists to remove duplicates
            result['trading_pairs'] = list(set(result['trading_pairs']))
            result['timeframes'] = list(set(result['timeframes']))
            result['indicators'] = list(set(result['indicators']))
            result['information_sources'] = list(set(result['information_sources']))

        except Exception as e:
            result['metadata']['parse_errors'].append(str(e))

        return result

    async def _fetch_top_trading_pairs(self, exchange: str = "binance", limit: int = 100) -> list:
        """获取主流永续合约交易对列表

        Args:
            exchange: 交易所名称
            limit: 返回交易对数量

        Returns:
            交易对符号列表
        """
        try:
            # 使用 CCXT 获取永续合约市场
            markets = await fetch_pairs_ccxt(exchange)

            if not markets:
                return []

            # 过滤并提取 USDT 永续合约
            pairs = []
            for market in markets:
                symbol = market['symbol']
                # 只返回活跃的 USDT 永续合约
                if market.get('active', True) and 'USDT' in symbol.upper():
                    # 标准化格式（移除 CCXT 特殊字符）
                    normalized = symbol.replace('/', '').replace(':', '').replace('-', '')
                    pairs.append(normalized)

            return pairs[:limit]

        except Exception as e:
            self.console.print(f"[yellow]获取交易对列表失败: {e}[/yellow]")
            return []

        return []

    def _get_next_trader_id(self, db) -> int:
        """获取下一个交易员数字ID

        Args:
            db: TraderDatabase 实例

        Returns:
            下一个可用的数字ID
        """
        try:
            # 获取所有交易员ID
            traders = db.list_traders()

            # 提取所有数字ID
            numeric_ids = []
            for trader in traders:
                trader_id = trader.get('id', '')
                # 尝试从文件名或ID中提取数字部分
                # 支持格式：TraderName_123.md 或 123.md 或只是 123
                import re
                numbers = re.findall(r'\d+', trader_id)
                if numbers:
                    numeric_ids.append(int(numbers[-1]))  # 取最后一个数字

            # 返回最大ID + 1，如果没有则返回1
            if numeric_ids:
                return max(numeric_ids) + 1
            else:
                return 1

        except Exception as e:
            self.console.print(f"[yellow]获取ID失败，使用默认值: {e}[/yellow]")
            return 1

    async def _handle_newtrader_command(self, args: list):
        """Handle the /newtrader command

        Generates a new trader profile using Claude Code as a subprocess.

        Args:
            args: Command arguments (optional prompt for trader generation)
        """

        # Check if TRADERS.md exists
        project_root = Path(__file__).parent.parent
        traders_dir = project_root / "traders"
        traders_guide = traders_dir / "TRADERS.md"

        if not traders_guide.exists():
            self.console.print(
                f"[red]错误: 找不到 {traders_guide}[/red]"
            )
            self.console.print(
                "[yellow]请确保 TRADERS.md 文件存在于 traders/ 目录中[/yellow]"
            )
            return

        # Find Claude Code executable
        claude_path = shutil.which("claude")
        if not claude_path:
            self.console.print(
                "[red]错误: 未找到 Claude Code 可执行文件[/red]"
            )
            self.console.print(
                "[yellow]请访问 https://code.claude.com 安装 Claude Code[/yellow]"
            )
            return

        # Fetch available trading pairs
        self.console.print("[cyan]正在获取可用交易对列表...[/cyan]")
        top_pairs = await self._fetch_top_trading_pairs()

        if not top_pairs:
            self.console.print("[yellow]警告: 未能获取交易对列表，将使用默认列表[/yellow]")
            top_pairs = [
                "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
                "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT"
            ]

        self.console.print(f"[green]已获取 {len(top_pairs)} 个主流交易对[/green]")

        # Get next numeric ID
        db = TraderDatabase()
        db.initialize()
        next_id = self._get_next_trader_id(db)
        db.close()

        # Prepare user prompt
        user_prompt = " ".join(args) if args else "Generate a unique, diverse cryptocurrency trader"

        # Format pairs list for instructions
        pairs_list = "\n".join([f"  - {pair}" for pair in top_pairs[:50]])  # Top 50 pairs

        # Prepare instructions for Claude Code
        instructions = f"""Read the file TRADERS.md for complete instructions on generating traders.

Then read all existing trader profile.md files to understand what traders already exist.
They are organized in subdirectories like: traders/TraderName_ID/profile.md

Your task: {user_prompt}

IMPORTANT - Trading Pairs Restriction:
You MUST ONLY select trading pairs from the following list (top {len(top_pairs)} pairs by volume):
{pairs_list}

Focus on mainstream, highly liquid pairs from the top of this list (especially BTC, ETH, BNB, SOL, XRP, etc.).

IMPORTANT - Trader Folder Structure:
- Use a NUMERIC auto-increment ID: {next_id}
- Create a FOLDER named: <TraderName>_{next_id}
- Inside that folder, create a file named: profile.md
  Example: Create folder QuantumTrader_{next_id}/ with profile.md inside
  Example: If ID is 1: BitcoinMaximalist_1/profile.md, EthDegen_2/profile.md, etc.

Important:
1. Create EXACTLY ONE new trader profile
2. Ensure the new trader is DISTINCTLY DIFFERENT from all existing traders
3. Follow the template in TRADERS.md exactly
4. Create a folder named <TraderName>_{next_id}/ with profile.md inside
5. The trader must be unique and diverse from all existing traders
6. ONLY use trading pairs from the provided list above"""

        self.console.print("[cyan]正在调用 Claude Code 生成新的交易者档案...[/cyan]")
        self.console.print(f"[dim]提示: {user_prompt}[/dim]")
        self.console.print(f"[dim]交易员ID: {next_id}[/dim]\n")

        # Get list of existing trader folders BEFORE running Claude Code
        # Check for subdirectories containing profile.md
        trader_folders_before = set()
        for item in traders_dir.iterdir():
            if item.is_dir() and (item / "profile.md").exists():
                trader_folders_before.add(item.name)

        md_files_before = set(f.name for f in traders_dir.glob("*.md") if f.name != "TRADERS.md")

        try:
            # Run Claude Code as subprocess with real-time output
            self.console.print("[dim]Claude Code 正在处理任务...[/dim]\n")

            # Use Popen for real-time output streaming
            process = subprocess.Popen(
                [claude_path, "--print", instructions],
                cwd=str(traders_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1  # Line buffered
            )

            # Stream output in real-time
            output_lines = []
            try:
                for line in process.stdout:
                    output_lines.append(line)
                    # Show output in dim color to avoid cluttering
                    self.console.print(f"[dim]{line.rstrip()}[/dim]", end="\n")
            except Exception as e:
                process.kill()
                raise e

            # Wait for process to complete with timeout
            try:
                return_code = process.wait(timeout=300)  # 5 minute timeout
            except subprocess.TimeoutExpired:
                process.kill()
                self.console.print("[red]错误: Claude Code 执行超时（5分钟）[/red]")
                return

            result = type('obj', (object,), {
                'stdout': ''.join(output_lines),
                'stderr': '',
                'returncode': return_code
            })()

            # Get list of trader folders AFTER running Claude Code
            # Check for subdirectories containing profile.md
            trader_folders_after = set()
            for item in traders_dir.iterdir():
                if item.is_dir() and (item / "profile.md").exists():
                    trader_folders_after.add(item.name)

            # Find new folders
            new_folders = trader_folders_after - trader_folders_before

            if not new_folders:
                self.console.print("[yellow]未检测到新创建的交易者文件夹[/yellow]")
                self.console.print(f"[dim]Claude Code 输出:\n{result.stdout}[/dim]")
                if result.stderr:
                    self.console.print(f"[dim]错误:\n{result.stderr}[/dim]")
                return

            # Initialize database
            db = TraderDatabase()
            db.initialize()

            new_traders_count = 0

            # Process only new folders
            for folder_name in new_folders:
                trader_folder = traders_dir / folder_name
                trader_file = trader_folder / "profile.md"

                # Parse the trader file
                trader_data = self._parse_trader_file(trader_file)

                # Prepare database record
                trader_record = {
                    'id': trader_data.get('id', folder_name),
                    'trader_file': str(trader_file),
                    'characteristics': trader_data.get('characteristics', {}),
                    'style': trader_data.get('style', ''),
                    'strategy': trader_data.get('strategy', {}),
                    'trading_pairs': trader_data.get('trading_pairs', []),
                    'timeframes': trader_data.get('timeframes', []),
                    'indicators': trader_data.get('indicators', []),
                    'information_sources': trader_data.get('information_sources', []),
                    'prompt': user_prompt,
                    'diversity_score': None,
                    'metadata': trader_data.get('metadata', {}),
                    'initial_balance': 10000.0,
                    'current_balance': 10000.0,
                    'equity': 10000.0
                }

                # Check if trader already exists in database
                existing = db.get_trader(trader_record['id'])
                if existing:
                    self.console.print(
                        f"[yellow]警告: 交易者 '{trader_record['id']}' 已存在于数据库中，跳过[/yellow]"
                    )
                    continue

                # Add to database
                success = db.add_trader(trader_record)
                if success:
                    new_traders_count += 1
                    self.console.print(
                        f"[green]✓ 交易者 '{trader_record['id']}' 已创建并记录到数据库[/green]"
                    )
                else:
                    self.console.print(
                        f"[yellow]警告: 无法将交易者 '{trader_record['id']}' 添加到数据库[/yellow]"
                    )

            db.close()

            if new_traders_count > 0:
                self.console.print(
                    f"\n[green]成功! 已创建 {new_traders_count} 个新交易者档案[/green]"
                )
            else:
                self.console.print("[yellow]未创建新交易者[/yellow]")

            # Show Claude output if there were issues
            if result.returncode != 0:
                self.console.print(f"\n[dim]Claude Code 退出码: {result.returncode}[/dim]")

        except Exception as e:
            self.console.print(f"[red]错误: {e}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")

    async def _handle_decide_command(self, args: list):
        """Handle the /decide command - AI-driven trading decision

        Args:
            args: Command arguments (trader_id [--wait])
        """
        import os
        import json
        import tempfile
        from pathlib import Path

        if not args:
            self.console.print("[red]错误: 请提供 trader_id[/red]")
            return

        trader_id = args[0]

        # Verify trader exists
        with TraderDatabase() as db:
            trader = db.get_trader(trader_id)
            if not trader:
                self.console.print(f"[red]错误: 未找到交易员 {trader_id}[/red]")
                return

        # Check if --wait flag is present
        wait_for_completion = '--wait' in args

        # Execute decision (wait for completion by default for better UX)
        await self._execute_decision_process(trader_id)

    async def _execute_decision_process(self, trader_id: str):
        """Execute the full decision workflow

        Args:
            trader_id: Trader ID
        """
        import os
        import json
        import tempfile
        from pathlib import Path

        try:
            # Phase 1: Gather data
            self.console.print(f"[Phase 1] 收集交易员 {trader_id} 数据...")

            # Get trader profile
            with TraderDatabase() as db:
                trader = db.get_trader(trader_id)

            # Get trader profile file content
            trader_file = Path(trader['trader_file'])
            if trader_file.exists():
                profile_content = trader_file.read_text(encoding='utf-8')
            else:
                profile_content = "Profile file not found"

            # Get position information
            with PositionDatabase() as pos_db:
                open_positions = pos_db.list_positions(trader_id, status='open')
                try:
                    summary = pos_db.get_trader_positions_summary(trader_id)
                except Exception:
                    summary = {
                        'total_unrealized_pnl': 0,
                        'total_realized_pnl': 0,
                        'open_count': len(open_positions),
                        'average_roi': 0
                    }

            # Update positions with current prices
            price_service = get_price_service()
            try:
                await price_service.update_trader_positions(trader_id, pos_db)
                # Refresh positions after update
                open_positions = pos_db.list_positions(trader_id, status='open')
                summary = pos_db.get_trader_positions_summary(trader_id)
            except Exception as e:
                self.console.print(f"[警告] 无法更新价格: {e}")

            # Build decision context
            decision_context = self._build_decision_context(trader, open_positions, summary, profile_content)

            # Phase 2: AI initial assessment
            self.console.print("[Phase 2] AI 初步分析中...")
            phase1_prompt = self._build_phase1_prompt(decision_context)
            phase1_response = await self._call_claude_code_for_decision(phase1_prompt, trader_id)

            if not phase1_response or phase1_response.startswith("ERROR"):
                self.console.print(f"[错误] AI 调用失败: {phase1_response}")
                return

            # Show brief summary of AI response
            response_lines = phase1_response.strip().split('\n')
            first_line = response_lines[0] if response_lines else phase1_response[:100]
            self.console.print(f"[AI 响应] {first_line}")

            # Phase 3: Execute indicators if needed
            indicator_data = {}
            response_upper = phase1_response.upper()

            if "NEED_ORDERBOOK" in response_upper or "NEED_MARKET" in response_upper or "NEED_BOTH" in response_upper:
                self.console.print("[Phase 3] 收集额外市场数据...")
                indicator_data = await self._execute_indicators_from_response(phase1_response, trader)

                if indicator_data:
                    self.console.print(f"[完成] 已收集指标数据: {list(indicator_data.keys())}")

            # Phase 4: Final decision
            self.console.print("[Phase 4] 做出最终决策...")
            phase2_prompt = self._build_phase2_prompt(decision_context, indicator_data, phase1_response)
            final_decision = await self._call_claude_code_for_decision(phase2_prompt, trader_id)

            if not final_decision or final_decision.startswith("ERROR"):
                self.console.print(f"[错误] 最终决策失败: {final_decision}")
                return

            # Extract decision from response - look for valid action keywords
            decision_lines = final_decision.strip().split('\n')
            actual_decision = None

            # Valid action keywords
            valid_actions = ['OPEN_LONG', 'OPEN_SHORT', 'CLOSE_POSITION', 'CLOSE_ALL', 'HOLD']

            # Find the line containing a valid action
            for line in decision_lines:
                line_upper = line.upper().strip()
                for action in valid_actions:
                    if line_upper.startswith(action):
                        actual_decision = line.strip()
                        break
                if actual_decision:
                    break

            # If no valid action found, use first line
            if not actual_decision:
                actual_decision = decision_lines[0].strip() if decision_lines else final_decision.strip()

            self.console.print(f"[AI 决策] {actual_decision}")

            # Phase 5: Execute decision
            await self._execute_decision(actual_decision, trader_id)
            self.console.print("[完成] 决策流程结束")

        except Exception as e:
            self.console.print(f"[错误] 决策进程错误: {e}")
            import traceback
            self.console.print(f"[调试] {traceback.format_exc()}")

    def _build_decision_context(self, trader, open_positions, summary, profile_content):
        """Build decision context dict

        Args:
            trader: Trader database record
            open_positions: List of open positions
            summary: Position summary
            profile_content: Trader profile markdown content

        Returns:
            Decision context dictionary
        """
        # Parse trader characteristics
        import json
        characteristics = json.loads(trader['characteristics']) if isinstance(trader.get('characteristics'), str) else trader.get('characteristics', {})
        strategy = json.loads(trader['strategy']) if isinstance(trader.get('strategy'), str) else trader.get('strategy', {})
        trading_pairs = json.loads(trader['trading_pairs']) if isinstance(trader.get('trading_pairs'), str) else trader.get('trading_pairs', [])
        timeframes = json.loads(trader['timeframes']) if isinstance(trader.get('timeframes'), str) else trader.get('timeframes', [])

        return {
            'trader': {
                'id': trader['id'],
                'balance': trader.get('current_balance', 10000.0),
                'equity': trader.get('equity', 10000.0),
                'characteristics': characteristics,
                'strategy': strategy,
                'trading_pairs': trading_pairs,
                'timeframes': timeframes,
                'profile_content': profile_content[:2000]  # Truncate for brevity
            },
            'positions': {
                'open': [self._position_to_dict(p) for p in open_positions],
                'summary': summary
            }
        }

    def _position_to_dict(self, position):
        """Convert position object to dict

        Args:
            position: Position object or dict

        Returns:
            Dictionary representation
        """
        if hasattr(position, 'to_dict'):
            return position.to_dict()
        elif isinstance(position, dict):
            return position
        else:
            return {
                'id': getattr(position, 'id', None),
                'symbol': getattr(position, 'symbol', ''),
                'side': getattr(position, 'side', ''),
                'size': getattr(position, 'size', 0),
                'entry_price': getattr(position, 'entry_price', 0),
                'unrealized_pnl': getattr(position, 'unrealized_pnl', 0),
                'roi': getattr(position, 'roi', 0)
            }

    def _build_phase1_prompt(self, context):
        """Build Phase 1 prompt for initial AI assessment

        Args:
            context: Decision context dictionary

        Returns:
            Prompt string for Claude Code
        """
        trader = context['trader']
        positions = context['positions']

        # Format position info
        pos_info = ""
        if positions['open']:
            pos_info = f"\n当前持仓 ({len(positions['open'])}):\n"
            for p in positions['open'][:5]:  # Limit to 5 positions
                pos_info += f"  - {p.get('symbol')} {p.get('side')} size={p.get('size')} entry={p.get('entry_price')} pnl={p.get('unrealized_pnl', 0):.2f}\n"
            pos_info += f"\n总未实现盈亏: {positions['summary'].get('total_unrealized_pnl', 0):.2f}\n"
            pos_info += f"总已实现盈亏: {positions['summary'].get('total_realized_pnl', 0):.2f}\n"
        else:
            pos_info = "\n当前持仓: 无\n"

        return f"""You are a trading decision engine for trader {trader['id']}.

TRADER PROFILE:
{trader['profile_content']}

TRADER DATA:
- Balance: ${trader['balance']:.2f}
- Equity: ${trader['equity']:.2f}
- Trading pairs: {', '.join(trader['trading_pairs'][:5])}
- Timeframes: {', '.join(trader['timeframes'])}
{pos_info}

TASK: Decide if additional market data is needed before making a trading decision.

Available indicators (CSV format):
- fetch_orderbook: Order book depth (side,price,volume)
- market_data: OHLCV with indicators (open,high,low,close,volume,rsi,trend,support,resistance)

Respond with ONE of:
- NO_DECISION_NEEDED
- NEED_ORDERBOOK <exchange> <symbol>
- NEED_MARKET_DATA <exchange> <symbol> <interval>
- NEED_BOTH <exchange> <symbol> <interval>

Your decision:"""

    def _build_phase2_prompt(self, context, indicator_data, phase1_response):
        """Build Phase 2 prompt for final decision

        Args:
            context: Decision context dictionary
            indicator_data: Collected indicator data (CSV strings)
            phase1_response: Phase 1 AI response

        Returns:
            Prompt string for Claude Code
        """
        trader = context['trader']
        positions = context['positions']

        # Format indicator data (CSV format)
        indicator_text = ""
        if indicator_data:
            indicator_text = "\nADDITIONAL MARKET DATA (CSV format):\n"
            for key, value in indicator_data.items():
                # Truncate to max 50 lines to save tokens
                lines = value.strip().split('\n')
                if len(lines) > 50:
                    preview = '\n'.join(lines[:25]) + '\n...\n' + '\n'.join(lines[-25:])
                else:
                    preview = value.strip()
                indicator_text += f"\n{key}:\n{preview}\n"
        else:
            indicator_text = "\nNo additional indicator data was collected.\n"

        return f"""{indicator_text}

TRADER CONTEXT:
- Trader ID: {trader['id']}
- Balance: ${trader['balance']:.2f}
- Current Positions: {len(positions['open'])}

Make your final trading decision based on:
1. Trader profile and strategy
2. Current positions and PnL
3. Market data (CSV format - analyze independently)

IMPORTANT: Respond with ONLY the action command below, no explanation:

- "OPEN_LONG <exchange> <symbol> <size> [leverage]"
- "OPEN_SHORT <exchange> <symbol> <size> [leverage]"
- "CLOSE_POSITION <position_id>"
- "CLOSE_ALL"
- "HOLD"

Examples:
OPEN_LONG binance BTCUSDT 0.1 5
OPEN_SHORT okx ETHUSDT 1.0
CLOSE_POSITION 123
CLOSE_ALL
HOLD

Constraints:
- Size should be 1-10% of balance (current: ${trader['balance']:.2f})
- Leverage is optional, default is 1
- Exchange: binance, okx, bybit, bitget

Your decision (ONE LINE ONLY):"""

    async def _call_claude_code_for_decision(self, prompt: str, trader_id: str):
        """Call Claude Code subprocess for AI decision

        Args:
            prompt: Prompt string
            trader_id: Trader ID for logging

        Returns:
            Claude Code response string
        """
        claude_path = shutil.which("claude")
        if not claude_path:
            return "ERROR: Claude Code not installed"

        # Use stdin to pass the prompt
        try:
            process = await asyncio.create_subprocess_exec(
                claude_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Send prompt via stdin with timeout
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=prompt.encode()),
                timeout=300  # 5 minutes
            )

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                return f"ERROR: Claude Code failed: {error_msg}"

            return stdout.decode().strip()

        except asyncio.TimeoutError:
            if process:
                process.kill()
            return "ERROR: Claude Code timeout (5 minutes)"
        except Exception as e:
            return f"ERROR: {str(e)}"

    async def _execute_indicators_from_response(self, response: str, trader):
        """Execute indicators based on AI response

        Args:
            response: AI response string
            trader: Trader database record

        Returns:
            Dictionary of indicator results (CSV strings)
        """
        import json
        from pathlib import Path

        results = {}
        response_upper = response.upper()

        # Parse trading pairs from trader
        trading_pairs = json.loads(trader['trading_pairs']) if isinstance(trader.get('trading_pairs'), str) else trader.get('trading_pairs', [])
        default_symbol = trading_pairs[0] if trading_pairs else "BTCUSDT"
        default_exchange = "binance"

        # Extract parameters from response
        import re
        orderbook_match = re.search(r'NEED_ORDERBOOK\s+(\w+)\s+(\w+)', response_upper)
        market_match = re.search(r'NEED_MARKET_DATA\s+(\w+)\s+(\w+)\s+(\w+)', response_upper)
        both_match = re.search(r'NEED_BOTH\s+(\w+)\s+(\w+)\s+(\w+)', response_upper)

        try:
            if "NEED_ORDERBOOK" in response_upper or both_match:
                if orderbook_match:
                    exchange = orderbook_match.group(1).lower()
                    symbol = orderbook_match.group(2).upper()
                elif both_match:
                    exchange = both_match.group(1).lower()
                    symbol = both_match.group(2).upper()
                else:
                    exchange = default_exchange
                    symbol = default_symbol

                self.console.print(f"[指标] 运行 fetch_orderbook: {exchange} {symbol}")
                orderbook_data = await self._run_indicator("fetch_orderbook.py", [
                    "--exchange", exchange,
                    "--symbol", symbol
                ])
                if orderbook_data and not orderbook_data.startswith("error"):
                    results['orderbook'] = orderbook_data

            if "NEED_MARKET" in response_upper or both_match:
                if market_match:
                    exchange = market_match.group(1).lower()
                    symbol = market_match.group(2).upper()
                    interval = market_match.group(3).lower()
                elif both_match:
                    exchange = both_match.group(1).lower()
                    symbol = both_match.group(2).upper()
                    interval = both_match.group(3).lower()
                else:
                    exchange = default_exchange
                    symbol = default_symbol
                    interval = "1h"

                self.console.print(f"[指标] 运行 market_data: {exchange} {symbol} {interval}")
                market_data = await self._run_indicator("market_data.py", [
                    "--exchange", exchange,
                    "--symbol", symbol,
                    "--interval", interval
                ])
                if market_data and not market_data.startswith("error"):
                    results['market_data'] = market_data

        except Exception as e:
            self.console.print(f"[警告] 指标执行异常: {e}")

        return results

    async def _run_indicator(self, script_name: str, args: list):
        """Run an indicator script and parse CSV output

        Args:
            script_name: Name of the indicator script
            args: Command line arguments

        Returns:
            CSV data as string or None
        """
        from pathlib import Path

        indicators_dir = Path(__file__).parent.parent / "indicators"
        script_path = indicators_dir / script_name

        if not script_path.exists():
            self.console.print(f"[错误] 指标脚本不存在: {script_path}")
            return None

        cmd = [sys.executable, str(script_path)] + args

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=60  # 1 minute timeout
            )

            if process.returncode != 0:
                self.console.print(f"[警告] 指标脚本错误: {stderr.decode()[:100]}")
                return None

            return stdout.decode()

        except asyncio.TimeoutError:
            process.kill()
            self.console.print(f"[警告] 指标超时: {script_name}")
            return None
        except Exception as e:
            self.console.print(f"[警告] 指标执行失败: {e}")
            return None

    async def _execute_decision(self, decision: str, trader_id: str):
        """Parse and execute AI decision

        Args:
            decision: Decision string from AI
            trader_id: Trader ID
        """
        decision = decision.strip()
        parts = decision.split()
        if not parts:
            self.console.print("[决策] 空决策，无操作")
            return

        action = parts[0].upper()

        try:
            if action == "OPEN_LONG":
                # Parse: OPEN_LONG <exchange> <symbol> <size> [leverage]
                if len(parts) < 4:
                    self.console.print(f"[错误] 无效的 OPEN_LONG 格式: {decision}")
                    return
                exchange = parts[1]
                symbol = parts[2]
                size = float(parts[3])
                leverage = int(parts[4]) if len(parts) > 4 else None
                await self._handle_openposition_command([trader_id, exchange, symbol, "long", str(size)] + ([str(leverage)] if leverage else []))

            elif action == "OPEN_SHORT":
                # Parse: OPEN_SHORT <exchange> <symbol> <size> [leverage]
                if len(parts) < 4:
                    self.console.print(f"[错误] 无效的 OPEN_SHORT 格式: {decision}")
                    return
                exchange = parts[1]
                symbol = parts[2]
                size = float(parts[3])
                leverage = int(parts[4]) if len(parts) > 4 else None
                await self._handle_openposition_command([trader_id, exchange, symbol, "short", str(size)] + ([str(leverage)] if leverage else []))

            elif action == "CLOSE_POSITION":
                # Parse: CLOSE_POSITION <position_id>
                if len(parts) < 2:
                    self.console.print(f"[错误] 无效的 CLOSE_POSITION 格式: {decision}")
                    return
                position_id = parts[1]
                await self._handle_closeposition_command([position_id])

            elif action == "CLOSE_ALL":
                # Close all positions for trader
                with PositionDatabase() as db:
                    positions = db.list_positions(trader_id, status='open')
                    for pos in positions:
                        self.console.print(f"[执行] 平仓: {pos.id}")
                        await self._handle_closeposition_command([str(pos.id)])

            elif action == "HOLD":
                self.console.print("[决策] 持有 - 无操作")

            else:
                self.console.print(f"[错误] 未知决策类型: {action}")

        except Exception as e:
            self.console.print(f"[错误] 执行决策失败: {e}")
            import traceback
            self.console.print(f"[调试] {traceback.format_exc()}")

    async def _show_trader_positions(self, trader_id: str):
        """Display trader's positions with updated PnL

        Args:
            trader_id: Trader ID
        """
        from .position_db import PositionDatabase

        # Verify trader exists
        trader_db = TraderDatabase()
        trader_db.initialize()
        trader = trader_db.get_trader(trader_id)
        trader_db.close()

        if not trader:
            self.console.print(f"[yellow]未找到 ID 为 '{trader_id}' 的交易者[/yellow]")
            return

        # Initialize position database
        pos_db = PositionDatabase()
        pos_db.initialize()

        try:
            # Fetch current prices and update all positions
            self.console.print(f"[cyan]正在获取 {trader_id} 的仓位信息...[/cyan]")

            price_service = get_price_service()
            updated_positions = await price_service.update_trader_positions(trader_id, pos_db)

            # Get all positions
            all_positions = pos_db.list_positions(trader_id)

            if not all_positions:
                self.console.print(f"[yellow]交易者 {trader_id} 暂无仓位[/yellow]")
                return

            # Display positions table
            from rich.table import Table

            table = Table(
                title=f"[bold cyan]交易者 {trader_id} 的仓位[/bold cyan]",
                show_header=True,
                header_style="bold magenta"
            )
            table.add_column("ID", style="cyan", width=6)
            table.add_column("交易所", style="green", width=10)
            table.add_column("交易对", style="white", width=12)
            table.add_column("方向", style="yellow", width=6)
            table.add_column("杠杆", style="magenta", width=6)
            table.add_column("入场价", style="white", width=12)
            table.add_column("数量", style="white", width=10)
            table.add_column("保证金", style="white", width=10)
            table.add_column("未实现盈亏", style="white", width=12)
            table.add_column("ROI %", style="white", width=10)
            table.add_column("状态", style="white", width=10)

            # Sort by unrealized_pnl DESC (most profitable first)
            sorted_positions = sorted(
                all_positions,
                key=lambda p: p.unrealized_pnl if p.status == PositionStatus.OPEN else p.realized_pnl,
                reverse=True
            )

            for pos in sorted_positions:
                # Format PnL with color
                pnl = pos.unrealized_pnl if pos.status == PositionStatus.OPEN else pos.realized_pnl
                pnl_color = "green" if pnl > 0 else "red" if pnl < 0 else "white"
                pnl_str = f"[{pnl_color}]{pnl:+.2f}[/{pnl_color}]"

                # Format ROI with color
                roi_color = "green" if pos.roi > 0 else "red" if pos.roi < 0 else "white"
                roi_str = f"[{roi_color}]{pos.roi:+.2f}%[/{roi_color}]"

                # Format status
                status_str = pos.status.value
                status_color = "green" if pos.status == PositionStatus.OPEN else "yellow"

                table.add_row(
                    str(pos.id),
                    pos.exchange,
                    pos.symbol,
                    pos.position_side.value,
                    f"{pos.leverage:.1f}x",
                    f"{pos.entry_price:.2f}",
                    f"{pos.position_size:.4f}",
                    f"{pos.margin:.2f}",
                    pnl_str,
                    roi_str,
                    f"[{status_color}]{status_str}[/{status_color}]"
                )

            self.console.print(table)

            # Display summary
            summary = pos_db.get_trader_positions_summary(trader_id)

            from rich.panel import Panel
            from rich.text import Text

            summary_text = Text()
            summary_text.append(f"总仓位: {summary['total_positions']}\n", style="white")
            summary_text.append(f"持仓中: {summary['open_positions']}\n", style="green")
            summary_text.append(f"已平仓: {summary['closed_positions']}\n", style="yellow")
            summary_text.append(f"已清算: {summary['liquidated_positions']}\n", style="red")
            summary_text.append(f"\n未实现盈亏: ", style="white")
            summary_text.append(f"{summary['total_unrealized_pnl']:+.2f} USDT\n",
                             style="green" if summary['total_unrealized_pnl'] > 0 else "red")
            summary_text.append(f"已实现盈亏: ", style="white")
            summary_text.append(f"{summary['total_realized_pnl']:+.2f} USDT\n",
                             style="green" if summary['total_realized_pnl'] > 0 else "red")
            summary_text.append(f"平均 ROI: ", style="white")
            summary_text.append(f"{summary['average_roi']:+.2f}%",
                             style="green" if summary['average_roi'] > 0 else "red")
            summary_text.append(f"\n\n余额: ", style="white")
            summary_text.append(f"{trader.get('current_balance', 0):.2f} USDT",
                             style="cyan")
            summary_text.append(f"\n权益: ", style="white")
            summary_text.append(f"{trader.get('equity', 0):.2f} USDT",
                             style="green" if trader.get('equity', 0) > trader.get('current_balance', 0) else "red")

            panel = Panel(summary_text, title="[bold cyan]仓位统计[/bold cyan]", border_style="cyan")
            self.console.print("\n", panel)

            # Update trader equity with current unrealized PnL
            trader_db = TraderDatabase()
            trader_db.initialize()
            trader_db.update_equity_with_unrealized_pnl(trader_id, summary['total_unrealized_pnl'])
            trader_db.close()

        except Exception as e:
            self.console.print(f"[red]错误: {e}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
        finally:
            pos_db.close()

    async def _handle_openposition_command(self, args: list):
        """Handle the /openposition command

        Opens a new trading position.

        Args:
            args: Command arguments: <trader_id> <exchange> <symbol> <side> <size> [leverage]
        """
        # Parse arguments
        if len(args) < 5:
            self.console.print("[red]错误: 参数不足[/red]")
            self.console.print("[yellow]用法: /openposition <trader_id> <exchange> <symbol> <side> <size> [leverage][/yellow]")
            self.console.print("[dim]示例: /openposition 1 binance BTCUSDT long 0.5 10[/dim]")
            return

        trader_id = args[0]
        exchange = args[1]
        symbol = args[2]
        side = args[3].lower()

        try:
            size = float(args[4])
        except ValueError:
            self.console.print(f"[red]错误: 无效的仓位大小 '{args[4]}'[/red]")
            return

        leverage = float(args[5]) if len(args) > 5 else 1.0

        # Validate inputs
        if side not in ('long', 'short'):
            self.console.print(f"[red]错误: 无效的方向 '{side}'. 必须是 'long' 或 'short'[/red]")
            return

        if size <= 0:
            self.console.print(f"[red]错误: 仓位大小必须大于 0[/red]")
            return

        if leverage <= 0:
            self.console.print(f"[red]错误: 杠杆必须大于 0[/red]")
            return

        # Verify exchange is supported
        try:
            get_exchange_config(exchange)
        except ValueError as e:
            self.console.print(f"[red]错误: {e}[/red]")
            return

        # Verify trader exists
        trader_db = TraderDatabase()
        trader_db.initialize()
        trader = trader_db.get_trader(trader_id)
        trader_db.close()

        if not trader:
            self.console.print(f"[yellow]未找到 ID 为 '{trader_id}' 的交易者[/yellow]")
            return

        # Fetch current price
        try:
            price_service = get_price_service()
            entry_price = await price_service.fetch_current_price(exchange, symbol)
        except Exception as e:
            self.console.print(f"[red]错误: 获取价格失败 {exchange} {symbol}: {e}[/red]")
            return

        # Calculate fee
        try:
            entry_fee = calculate_fee(exchange, size, entry_price)
        except Exception as e:
            self.console.print(f"[red]错误: 计算费用失败: {e}[/red]")
            return

        # Calculate margin
        margin = (size * entry_price) / leverage

        # Check if trader has sufficient balance
        required_margin = margin + entry_fee
        current_balance = trader.get('current_balance', 0)

        if current_balance < required_margin:
            self.console.print(f"[red]错误: 余额不足[/red]")
            self.console.print(f"  [dim]当前余额:[/dim] {current_balance:.2f} USDT")
            self.console.print(f"  [dim]需要金额:[/dim] {required_margin:.2f} USDT (保证金: {margin:.2f} + 费用: {entry_fee:.4f})")
            self.console.print(f"  [dim]差额:[/dim] {required_margin - current_balance:.2f} USDT")
            return

        # Create position
        position = Position(
            trader_id=trader_id,
            exchange=exchange,
            symbol=symbol,
            position_side=PositionSide.LONG if side == 'long' else PositionSide.SHORT,
            status=PositionStatus.OPEN,
            leverage=leverage,
            entry_price=entry_price,
            entry_time=datetime.now(),
            entry_fee=entry_fee,
            position_size=size,
            margin=margin,
            contract_size=1.0,
            unrealized_pnl=0.0,  # Will be updated by price service
        )

        # Calculate liquidation price
        position.liquidation_price = position.calculate_liquidation_price()

        # Save to database
        pos_db = PositionDatabase()
        pos_db.initialize()

        try:
            position_id = pos_db.add_position(position)

            # Update trader balance and equity
            # Balance decreases by margin + fee
            # Equity = balance + unrealized_pnl (initially 0 for new position)
            trader_db = TraderDatabase()
            trader_db.initialize()
            balance_change = -(margin + entry_fee)
            trader_db.update_balance_and_equity(trader_id, balance_change=balance_change)
            trader_db.close()

            self.console.print(f"[green]✓ 仓位已开立[/green]")
            self.console.print(f"  [dim]ID:[/dim] {position_id}")
            self.console.print(f"  [dim]交易者:[/dim] {trader_id}")
            self.console.print(f"  [dim]交易所:[/dim] {exchange}")
            self.console.print(f"  [dim]交易对:[/dim] {symbol}")
            self.console.print(f"  [dim]方向:[/dim] {side}")
            self.console.print(f"  [dim]入场价:[/dim] {entry_price:.2f}")
            self.console.print(f"  [dim]数量:[/dim] {size:.4f}")
            self.console.print(f"  [dim]杠杆:[/dim] {leverage:.1f}x")
            self.console.print(f"  [dim]保证金:[/dim] {margin:.2f} USDT")
            self.console.print(f"  [dim]费用:[/dim] {entry_fee:.4f} USDT")
            self.console.print(f"  [dim]清算价:[/dim] {position.liquidation_price:.2f}")
        except Exception as e:
            self.console.print(f"[red]错误: 保存仓位失败: {e}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
        finally:
            pos_db.close()

    async def _handle_closeposition_command(self, args: list):
        """Handle the /closeposition command

        Closes an existing position.

        Args:
            args: Command arguments: <position_id> [price]
        """
        # Parse arguments
        if len(args) < 1:
            self.console.print("[red]错误: 参数不足[/red]")
            self.console.print("[yellow]用法: /closeposition <position_id> [price][/yellow]")
            self.console.print("[dim]示例: /closeposition 1[/dim]")
            self.console.print("[dim]示例: /closeposition 1 45000[/dim]")
            return

        try:
            position_id = int(args[0])
        except ValueError:
            self.console.print(f"[red]错误: 无效的仓位 ID '{args[0]}'[/red]")
            return

        # Get position from database
        pos_db = PositionDatabase()
        pos_db.initialize()

        try:
            position = pos_db.get_position(position_id)

            if not position:
                self.console.print(f"[yellow]未找到 ID 为 '{position_id}' 的仓位[/yellow]")
                return

            if position.status != PositionStatus.OPEN:
                self.console.print(f"[yellow]仓位 {position_id} 不是开放状态 (状态: {position.status.value})[/yellow]")
                return

            # Determine exit price
            if len(args) > 1:
                try:
                    exit_price = float(args[1])
                except ValueError:
                    self.console.print(f"[red]错误: 无效的退出价格 '{args[1]}'[/red]")
                    return
            else:
                # Fetch current price
                try:
                    price_service = get_price_service()
                    exit_price = await price_service.fetch_current_price(
                        position.exchange,
                        position.symbol
                    )
                    self.console.print(f"[dim]当前价格: {exit_price:.2f}[/dim]")
                except Exception as e:
                    self.console.print(f"[red]错误: 获取价格失败: {e}[/red]")
                    return

            # Calculate exit fee
            try:
                exit_fee = calculate_fee(position.exchange, position.position_size, exit_price)
            except Exception as e:
                self.console.print(f"[red]错误: 计算费用失败: {e}[/red]")
                return

            # Close position
            success = pos_db.close_position(position_id, exit_price, exit_fee)

            if success:
                # Get updated position
                closed_position = pos_db.get_position(position_id)

                # Update trader balance and equity
                # Balance change: margin returned + realized_pnl
                # realized_pnl already includes fees deduction
                trader_db = TraderDatabase()
                trader_db.initialize()

                balance_change = closed_position.margin + closed_position.realized_pnl
                trader_db.update_balance_and_equity(position.trader_id, balance_change=balance_change)

                # Update equity with remaining unrealized PnL from other open positions
                position_summary = pos_db.get_trader_positions_summary(position.trader_id)
                trader_db.update_equity_with_unrealized_pnl(
                    position.trader_id,
                    position_summary['total_unrealized_pnl']
                )
                trader_db.close()

                pnl_color = "green" if closed_position.realized_pnl > 0 else "red"
                self.console.print(f"[green]✓ 仓位已平仓[/green]")
                self.console.print(f"  [dim]ID:[/dim] {position_id}")
                self.console.print(f"  [dim]交易对:[/dim] {position.symbol}")
                self.console.print(f"  [dim]入场价:[/dim] {position.entry_price:.2f}")
                self.console.print(f"  [dim]出场价:[/dim] {exit_price:.2f}")
                self.console.print(f"  [dim]入场费用:[/dim] {position.entry_fee:.4f} USDT")
                self.console.print(f"  [dim]出场费用:[/dim] {exit_fee:.4f} USDT")
                self.console.print(f"  [dim]总费用:[/dim] {position.entry_fee + exit_fee:.4f} USDT")
                self.console.print(f"  [dim]已实现盈亏: [{pnl_color}]{closed_position.realized_pnl:+.2f} USDT[/{pnl_color}]")
                self.console.print(f"  [dim]ROI: [{pnl_color}]{closed_position.roi:+.2f}%[/{pnl_color}]")
            else:
                self.console.print(f"[red]错误: 平仓失败[/red]")

        except Exception as e:
            self.console.print(f"[red]错误: {e}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
        finally:
            pos_db.close()

    async def run(self):
        """运行 CLI 主循环"""
        self._print_banner()

        while True:
            try:
                with patch_stdout():
                    cmd = await self.session.prompt_async(
                        "cryptobot>",
                    )

                # 解析并处理命令
                command, args = self._parse_command(cmd)

                if not command:
                    continue

                if command in ("/quit", "/exit", "quit", "exit"):
                    self.console.print("[yellow]再见！[/yellow]")
                    break

                elif command == "/help":
                    self._print_help()

                elif command == "/rest":
                    await self._handle_rest_command(args)

                elif command == "/pairs":
                    await self._handle_pairs_command(args)

                elif command == "/intervals":
                    await self._handle_intervals_command(args)

                elif command == "/traders":
                    await self._handle_traders_command(args)

                elif command == "/newtrader":
                    await self._handle_newtrader_command(args)

                elif command == "/decide":
                    await self._handle_decide_command(args)

                elif command == "/openposition":
                    await self._handle_openposition_command(args)

                elif command == "/closeposition":
                    await self._handle_closeposition_command(args)

                else:
                    self.console.print(
                        f"[red]未知命令: {command}. 输入 /help 查看帮助[/red]"
                    )

            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[yellow]再见！[/yellow]")
                break
            except Exception as e:
                # 使用 Text 来避免解析异常消息中的 Rich 标签
                from rich.text import Text
                error_text = Text()
                error_text.append("错误: ", style="red")
                error_text.append(str(e))
                self.console.print(error_text)
