"""CLI Core Logic

Handles user input using Prompt Toolkit
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
    """Check if running in an interactive terminal

    Returns:
        True if running in an interactive terminal
    """
    return sys.stdout.isatty()


class CryptoBot:
    """CryptoBot Main Class

    Manages user interaction and data display
    """

    DEFAULT_EXCHANGE = "binance"
    DEFAULT_SYMBOL = "BTCUSDT"
    DEFAULT_INTERVAL = "1m"

    def __init__(self):
        """Initialize CLI"""
        self.console = Console()
        self.display = KlineDisplay(self.console)
        self.session = PromptSession()
        self._stop_subscription = asyncio.Event()

        # Initialize databases (lazy initialization, create connections when needed)
        self.trader_db = None
        self.pos_db = None
        self.scheduler = None

    def _print_banner(self):
        """Print welcome banner"""
        banner = """
[bold cyan]╔═══════════════════════════════════════════════════════════╗
║                    CryptoBot v0.1.0                          ║
║           Perpetual Futures K-Line Data Tool (CCXT)          ║
╚═══════════════════════════════════════════════════════════╝[/bold cyan]

[dim]Supported exchanges: {exchanges}[/dim]
[dim]Default parameters: {default_exchange} {default_symbol} {default_interval}[/dim]
[dim]Data type: Perpetual Futures/Swap[/dim]

[bold yellow]Commands:[/bold yellow]
  /start [trader_ids...]  - Start continuous mode (optionally specify traders)
  /stop  - Stop continuous mode
  /status  - View scheduler status
  /config [key] [value]  - View/modify configuration
  /market [exchange] [symbol] [interval] [limit]  - Get historical K-line data
  /pairs [exchange]  - Show supported trading pairs
  /intervals  - Show supported intervals
  /traders [-a [prompt] [-t <count>]] [trader_id ...] [-d|-p|-m <prompt>]  - Create/view/delete/modify traders or positions
  /indicators [-a <prompt>] [filename] [-d|-m <prompt>|-t <args...>]  - Create/view/delete/modify/test indicators
  /decide <trader_id>  - AI trading decision
  /positions [trader_id|position_id] [-o <params>|-c [price]]  - Position management
  /optimize <trader_id>  - AI self-optimization
  /help  - Show detailed help
  /quit or /exit  - Exit program

[dim green]✓ Auto liquidation monitoring enabled[/dim green]
[dim]Tip: Enter /help for detailed command information[/dim]
""".format(
            exchanges=", ".join(get_supported_exchanges()),
            default_exchange=self.DEFAULT_EXCHANGE,
            default_symbol=self.DEFAULT_SYMBOL,
            default_interval=self.DEFAULT_INTERVAL,
        )
        self.console.print(banner)

    def _print_help(self):
        """Display help information"""
        help_text = """
[bold cyan]════════════════════════════════════════════════════════════════════════════════
                              CryptoBot Command Help
══════════════════════════════════════════════════════════════════════════════════[/bold cyan]

[dim]════════════════════════════════════════════════════════════════════════════════════════
                              📊 Market Data Commands
═════════════════════════════════════════════════════════════════════════════════════════[/dim]

[bold yellow]/market [exchange] [symbol] [interval] [limit][/bold yellow]
  Get historical K-line data (REST API one-time fetch, static display)
  Data type: Perpetual Futures/Swap

  [dim]Parameters:[/dim]
    exchange  - Exchange (binance, okx, bybit, bitget), default: {default_exchange}
    symbol    - Trading pair (e.g., BTCUSDT), default: {default_symbol}
    interval  - K-line interval, default: {default_interval}
    limit     - Number of candles (1-1000), default: 30

  [dim]Examples:[/dim]
    /market                          # Use default parameters
    /market okx ETHUSDT              # Specify exchange and symbol
    /market binance ETHUSDT 5m 100   # Get 100 5-minute K-lines

[bold yellow]/pairs [exchange][/bold yellow]
  Show list of supported trading pairs

  [dim]Examples:[/dim]
    /pairs          # Show trading pairs for default exchange
    /pairs binance  # Show Binance trading pairs

[bold yellow]/intervals[/bold yellow]
  Show supported K-line intervals

  [dim]Supported intervals:[/dim] 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d, 1w, 1M


[dim]════════════════════════════════════════════════════════════════════════════════════════
                              👤 Trader Management Commands
═════════════════════════════════════════════════════════════════════════════════════════[/dim]

[bold yellow]/traders [trader_id1 trader_id2 ...] [-d|-p|-m <prompt>|--reload][/bold yellow]
  View/delete/modify/reload trader profiles or view positions

  [dim]Parameters:[/dim]
    trader_id  -Trader ID (optional, multiple supported, space-separated)
    -d         - Delete flag (requires trader_id, supports batch delete)
    -p         - Show positions (requires trader_id)
    -m         - Modify flag (requires single trader_id and prompt)
    --reload   - Re-parse profile.md and update database (fix parsing errors)

  [dim]Examples:[/dim]
    /traders                        # Show all traders
    /traders 1                      # Show details for trader ID=1
    /traders 1 -p                   # Show positions for trader ID=1
    /traders 1 -d                   # Delete trader ID=1
    /traders 1 2 3 -d               # Batch delete traders ID=1,2,3
    /traders 1 -m increase leverage usage      # AI-modify trader
    /traders 1 --reload             # Re-parse profile.md and update database

[bold yellow]/traders -a [prompt] [-t <count>][/bold yellow]
  Generate new trader strategy profile using AI

  [dim]Parameters:[/dim]
    -a        - Add flag (create new trader)
    prompt    - Trader description (optional)
    -t <count> - Batch generation count (default: 1)

  [dim]Examples:[/dim]
    /traders -a                              # Generate random trader
    /traders -a conservative value investment                # Generate specific strategy
    /traders -a -t 3                         # Generate 3 random traders
    /traders -a aggressive scalping -t 5              # Generate 5 aggressive scalping traders

[bold yellow]/optimize <trader_id>[/bold yellow]
  AI self-optimization analysis - optimize strategy based on historical performance

  [dim]Process:[/dim]
    1. Collect historical positions and P&L data
    2. Analyze metrics like win rate, risk control
    3. AI evaluates and adjusts profile.md strategy parameters
    4. Sync update database records

  [dim]Examples:[/dim]
    /optimize 1    # Optimize strategy for trader 1


[dim]════════════════════════════════════════════════════════════════════════════════════════
                              📈 Indicator Management Commands
═════════════════════════════════════════════════════════════════════════════════════════[/dim]

[bold yellow]/indicators [-a <prompt>] [filename] [-d|-m <prompt>|-t <args...>][/bold yellow]
  Create/view/delete/modify/test indicator scripts

  [dim]Parameters:[/dim]
    -a        - Add flag (create new indicator)
    filename  - Script filename (optional)
    -d        - Delete flag
    -m        - Modify flag (requires prompt)
    -t        - Test flag (pass test parameters)
    prompt    - Add/modify prompt

  [dim]Examples:[/dim]
    /indicators -a fetch funding rate history    # Create new indicator
    /indicators -a calculate MACD indicator         # Create new indicator
    /indicators -a multi-exchange price comparison        # Create new indicator
    /indicators                        # List all indicators
    /indicators fetch_orderbook.py     # View script details
    /indicators fetch_orderbook.py -d  # Delete script
    /indicators market_data.py -m add MACD  # Modify script
    /indicators market_data.py -t BTCUSDT  # Test script


[dim]════════════════════════════════════════════════════════════════════════════════════════
                              💼 Position Management Commands
═════════════════════════════════════════════════════════════════════════════════════════[/dim]

[bold yellow]/positions [trader_id|position_id] [-o <params>|-c [price]][/bold yellow]
  Position management command

  [dim]Usage 1: View all traders' positions[/dim]
    /positions                          # Show all traders' positions

  [dim]Usage 2: View specific trader's positions[/dim]
    /positions <trader_id>              # Show that trader's positions

  [dim]Usage 3: Open position[/dim]
    /positions <trader_id> -o <exchange> <symbol> <side> <size> [leverage]
      trader_id  -Trader ID
      -o         - Open position flag
      exchange   - Exchange (binance, okx, bybit, bitget)
      symbol     - Trading pair (e.g., BTCUSDT)
      side       - Direction (long or short)
      size       - Position size (base currency amount)
      leverage   - Leverage multiplier (optional, default 1)

    [dim]Examples:[/dim]
      /positions 1 -o binance BTCUSDT long 0.5 10   # 10x long 0.5 BTC
      /positions 2 -o bybit ETHUSDT short 2.0      # 1x short 2 ETH

  [dim]Usage 4: Close position[/dim]
    /positions <position_id> -c [price]
      position_id  - Position ID
      -c           - Close position flag
      price        - Close price (optional, default market price)

    [dim]Examples:[/dim]
      /positions 1 -c              # Market close
      /positions 1 -c 45000        # Limit close @45000


[dim]════════════════════════════════════════════════════════════════════════════════════════
                              🤖 AI Decision Commands
═════════════════════════════════════════════════════════════════════════════════════════[/dim]

[bold yellow]/decide <trader_id>[/bold yellow]
  AI automated trading decision

  [dim]Decision process:[/dim]
    1. Collect trader profile, positions, P&L data
    2. AI analyzes and automatically calls indicator scripts for market data
    3. Make decision and execute based on complete data

  [dim]Possible decisions:[/dim]
    OPEN_LONG / OPEN_SHORT - Open position
    CLOSE_POSITION - Close position
    CLOSE_ALL - Clear all positions
    HOLD - Hold

  [dim]Examples:[/dim]
    /decide 1    # Execute AI decision for trader 1


[dim]════════════════════════════════════════════════════════════════════════════════════════
                              ⚙️  Scheduler Commands
═════════════════════════════════════════════════════════════════════════════════════════[/dim]

[bold yellow]/start [trader_ids...][/bold yellow]
  Start continuous mode (scheduler + real-time dashboard)

  [dim]Parameters:[/dim]
    trader_ids  - List of trader IDs to schedule (optional, default all)

  [dim]Examples:[/dim]
    /start              # Start all traders
    /start 1 2 3        # Start only traders 1,2,3

[bold yellow]/stop[/bold yellow]
  Stop continuous mode

[bold yellow]/status[/bold yellow]
  View scheduler status (queue, active tasks, trader status)

[bold yellow]/config [key] [value][/bold yellow]
  View/modify scheduler configuration

  [dim]Subcommands:[/dim]
    (none)     - Show all configuration
    list       - List all configuration
    reset      - Reset to defaults
    <key>      - View single configuration
    <key> <value> - Set configuration value

  [dim]Configuration items:[/dim]
    scheduler.check_interval          - Check interval (seconds)
    scheduler.max_concurrent_tasks    - Max concurrent tasks
    trigger.time.enabled              - Enable time trigger
    trigger.price.enabled             - Enable price trigger
    trigger.price.change_threshold    - Price change threshold
    indicator.limit                   - Indicator data limit
    optimize.enabled                  - Enable auto optimization
    optimize.min_positions            - Min positions before optimization
    optimize.interval_hours           - Optimization interval (hours)

  [dim]Examples:[/dim]
    /config                    # Show all configuration
    /config scheduler.check_interval 60  # Set check interval
    /config reset             # Reset configuration


[dim]════════════════════════════════════════════════════════════════════════════════════════
                              💡 Other Commands
═════════════════════════════════════════════════════════════════════════════════════════[/dim]

[bold yellow]/help[/bold yellow]
  Show this help information

[bold yellow]/quit or /exit[/bold yellow]
  Exit program


[dim]════════════════════════════════════════════════════════════════════════════════════════
                              ℹ️  System Information
═════════════════════════════════════════════════════════════════════════════════════════[/dim]

[dim]Supported exchanges: {exchanges}[/dim]
[dim]Data type: Perpetual Futures/Swap[/dim]
[dim]Data source: CCXT - Unified cryptocurrency exchange API[/dim]
[dim green]✓ Auto liquidation monitoring enabled[/dim green]
[dim]Tip: Press Ctrl+C to stop current operation[/dim]
""".format(
            exchanges=", ".join(get_supported_exchanges()),
            default_exchange=self.DEFAULT_EXCHANGE,
            default_symbol=self.DEFAULT_SYMBOL,
            default_interval=self.DEFAULT_INTERVAL,
        )
        self.console.print(help_text)

    def _parse_command(self, cmd: str) -> Tuple[str, list]:
        """Parse user command

        Args:
            cmd: User input command

        Returns:
            (command_name, argument_list)
        """
        parts = cmd.strip().split()
        if not parts:
            return "", []

        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        return command, args

    def _create_key_bindings(self):
        """Create key bindings

        Returns:
            KeyBindings object
        """
        bindings = KeyBindings()
        return bindings

    async def _handle_rest_command(self, args: list):
        """Handle /market command

        Args:
            args: Command arguments
        """
        # Parse parameters
        exchange = args[0] if len(args) > 0 else self.DEFAULT_EXCHANGE
        symbol = args[1] if len(args) > 1 else self.DEFAULT_SYMBOL
        interval = args[2] if len(args) > 2 else self.DEFAULT_INTERVAL
        limit_str = args[3] if len(args) > 3 else "30"

        # Validate and convert limit
        try:
            limit = int(limit_str)
            if limit < 1:
                self.console.print("[red]Error: limit must be >= 1[/red]")
                return
            if limit > 1000:
                self.console.print("[yellow]Warning: limit max is 1000, automatically adjusted[/yellow]")
                limit = 1000
        except ValueError:
            self.console.print(f"[red]Error: Invalid limit value: {limit_str}[/red]")
            return

        # Execute REST request
        await self._fetch_rest_klines(exchange, symbol, interval, limit)

    async def _fetch_rest_klines(self, exchange: str, symbol: str, interval: str, limit: int):
        """Fetch historical K-line data via REST API (using CCXT)

        Args:
            exchange: Exchange name
            symbol: Trading pair
            interval: K-line interval
            limit: Number of records to fetch
        """
        self.console.print(
            f"[cyan]Fetching {exchange.upper()} {symbol} {interval} perpetual futures data (limit={limit})...[/cyan]"
        )

        try:
            # Fetch data using CCXT
            klines = await fetch_klines_ccxt(exchange, symbol, interval, limit)

            if not klines:
                self.console.print("[yellow]No data retrieved[/yellow]")
                return

            self.console.print(f"[green]Successfully retrieved {len(klines)} K-line records[/green]\n")

            # Clear history and add new data
            self.display.clear_history()
            for kline in klines:
                self.display.update_kline(kline)

            # Show static chart
            chart = self.display._create_kline_chart()
            table = self.display._create_kline_table()
            panel = self.display._create_status_panel(symbol, exchange, interval)

            from rich.console import Group as RichGroup
            self.console.print(RichGroup(panel, chart, table))

            # Show statistics
            if klines:
                latest = klines[-1]
                first = klines[0]
                price_change = latest["close"] - first["open"]
                price_change_pct = (price_change / first["open"]) * 100
                change_color = "green" if price_change > 0 else "red" if price_change < 0 else "white"
                change_sign = "+" if price_change > 0 else ""

                self.console.print(
                    f"\n[dim]Time range: {self.display._format_timestamp(first['timestamp'])} - "
                    f"{self.display._format_timestamp(latest['timestamp'])}[/dim]"
                )
                self.console.print(
                    f"[dim]Price change: [{change_color}]{change_sign}{price_change:.2f} "
                    f"({change_sign}{price_change_pct:.2f}%)[/][/dim]"
                )

        except ValueError as e:
            self.console.print(f"[red]Error: {e}[/red]")
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")

    async def _handle_pairs_command(self, args: list):
        """Handle /pairs command

        Args:
            args: Command arguments
        """
        exchange = args[0] if len(args) > 0 else self.DEFAULT_EXCHANGE

        # Validate exchange
        try:
            get_exchange_config(exchange)
        except ValueError as e:
            self.console.print(f"[red]Error: {e}[/red]")
            return

        await self._fetch_and_display_pairs(exchange)

    async def _handle_intervals_command(self, args: list):
        """Handle /intervals command

        Args:
            args: Command arguments (unused)
        """
        self._display_supported_intervals()

    async def _handle_traders_command(self, args: list):
        """Handle /traders command

        Show all traders, view single trader, delete trader (supports batch delete), modify trader or view positions, add new trader

        Args:
            args: Command arguments [-a [prompt] [-t <count>]] | [trader_id1 trader_id2 ...] [-d] [-p] [-m <prompt>] [--reload]
        """

        # Parse arguments
        trader_ids = []
        add_flag = False
        delete_flag = False
        positions_flag = False
        modify_flag = False
        reload_flag = False
        edit_prompt = None

        i = 0
        while i < len(args):
            arg = args[i]
            if arg == '-a':
                add_flag = True
                i += 1
            elif arg == '-d':
                delete_flag = True
                i += 1
            elif arg == '-p':
                positions_flag = True
                i += 1
            elif arg == '-m':
                modify_flag = True
                # Remaining arguments after -m form the edit prompt
                edit_prompt = ' '.join(args[i+1:])
                break
            elif arg == '--reload' or arg == '-r':
                reload_flag = True
                i += 1
            elif not arg.startswith('-'):
                trader_ids.append(arg)
                i += 1
            else:
                i += 1

        # Case 1: Add new trader(s) with -a flag
        if add_flag:
            # Prepare args for newtrader handler: collect prompt args and -t parameter
            newtrader_args = []
            # Add non-flag args as prompt
            for trader_id in trader_ids:
                newtrader_args.append(trader_id)
            # Check if -t was in original args
            if '-t' in args:
                t_index = args.index('-t')
                if t_index + 1 < len(args):
                    newtrader_args.extend(['-t', args[t_index + 1]])
            await self._handle_newtrader_command(newtrader_args)
            return

        # Initialize database
        db = TraderDatabase()
        db.initialize()

        try:
            # Case 2: Delete trader(s)
            if delete_flag:
                if not trader_ids:
                    self.console.print("[red]Error: Delete operation requires trader ID[/red]")
                    self.console.print("[yellow]Usage: /traders <trader_id1 trader_id2 ...> -d[/yellow]")
                    return

                self._delete_traders(db, trader_ids)
                return

            # Case 2: Edit trader (requires -m flag)
            if modify_flag:
                if not trader_ids:
                    self.console.print("[red]Error: Modify operation requires trader ID[/red]")
                    self.console.print("[yellow]Usage: /traders <trader_id> -m <prompt>[/yellow]")
                    return
                if not edit_prompt:
                    self.console.print("[red]Error: Modify operation requires prompt[/red]")
                    self.console.print("[yellow]Usage: /traders <trader_id> -m <prompt>[/yellow]")
                    return
                await self._edit_trader(db, trader_ids[0], edit_prompt)
                return

            # Case 3: Reload trader (re-parse profile.md and update database)
            if reload_flag:
                if not trader_ids:
                    self.console.print("[red]Error: Reload operation requires trader ID[/red]")
                    self.console.print("[yellow]Usage: /traders <trader_id> --reload[/yellow]")
                    return
                self._reload_trader(db, trader_ids[0])
                return

            # Case 4: Show trader positions
            if trader_ids and positions_flag:
                await self._show_trader_positions(trader_ids[0])
                return

            # Case 4: Show specific trader
            if trader_ids:
                self._show_trader_detail(db, trader_ids[0])
                return

            # Case 5: Show all traders
            traders = db.list_traders()

            if not traders:
                self.console.print("[yellow]No trader profiles yet[/yellow]")
                self.console.print("[dim]Use /traders -a command to create new trader profile[/dim]")
                return

            # Display traders in a table
            from rich.table import Table
            from rich.panel import Panel

            # Create main table
            table = Table(title=f"[bold cyan]Trader Profile List[/bold cyan] (Total {len(traders)} traders)", show_header=True, header_style="bold magenta")
            table.add_column("ID", style="cyan", width=10)
            table.add_column("Trading Style", style="green", width=18)
            table.add_column("Risk Preference", style="yellow", width=10)
            table.add_column("Trading Pairs", style="blue", width=25)
            table.add_column("Timeframe", style="magenta", width=18)
            table.add_column("Created", style="dim", width=16)

            for trader in traders:
                # Extract characteristics
                chars = trader.get('characteristics', {})
                risk = chars.get('risk_tolerance', 'N/A')

                # Get trading pairs (limit to 3 for display)
                pairs = trader.get('trading_pairs', [])
                pairs_str = ', '.join(pairs[:3]) if pairs else 'N/A'
                if len(pairs) > 3:
                    pairs_str += f' (+{len(pairs) - 3})'

                # Get intervals (timeframes)
                intervals = trader.get('timeframes', [])
                intervals_str = ', '.join(intervals[:4]) if intervals else 'N/A'
                if len(intervals) > 4:
                    intervals_str += f' (+{len(intervals) - 4})'

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
                    intervals_str,
                    created
                )

            self.console.print(table)

            # Show statistics
            stats = db.get_statistics()
            self.console.print("\n[bold cyan]Statistics[/bold cyan]")

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
            self.console.print("\n[dim]Tip:[/dim]")
            self.console.print("  [dim]/traders -a [prompt]       - Create new trader[/dim]")
            self.console.print("  [dim]/traders <id>              - View trader details[/dim]")
            self.console.print("  [dim]/traders <id> -p           - View trader positions[/dim]")
            self.console.print("  [dim]/traders <id> -d           - Delete trader[/dim]")
            self.console.print("  [dim]/traders <id> -m <prompt>  - AI-modify trader[/dim]")
            self.console.print("  [dim]/traders <id> --reload     - Re-parse profile.md and update database[/dim]")

        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
        finally:
            db.close()

    def _reload_trader(self, db, trader_id: str):
        """Re-parse profile.md and update database

        Args:
            db: TraderDatabase instance
            trader_id:Trader ID
        """
        import os

        # Get trader info first
        trader = db.get_trader(trader_id)

        if not trader:
            self.console.print(f"[yellow]Trader with ID '{trader_id}' not found[/yellow]")
            return

        # Get trader file path
        trader_file = trader.get('trader_file', '')
        if not trader_file or not os.path.exists(trader_file):
            self.console.print(f"[red]Error: Trader file not found {trader_file}[/red]")
            return

        # Show trader info
        chars = trader.get('characteristics', {})
        name = chars.get('name', 'N/A')

        self.console.print(f"\n[bold cyan]Reloading trader:[/bold cyan]")
        self.console.print(f"  [dim]ID:[/dim] {trader_id}")
        self.console.print(f"  [dim]Name:[/dim] {name}")
        self.console.print(f"  [dim]File:[/dim] {trader_file}\n")

        # Parse the trader file
        from pathlib import Path
        trader_data = self._parse_trader_file(Path(trader_file))

        # Extract updateable fields
        updates = {
            'characteristics': trader_data.get('characteristics', {}),
            'style': trader_data.get('style', ''),
            'strategy': trader_data.get('strategy', {}),
            'trading_pairs': trader_data.get('trading_pairs', []),
            'timeframes': trader_data.get('timeframes', []),
            'indicators': trader_data.get('indicators', []),
            'information_sources': trader_data.get('information_sources', []),
        }

        # Display what will be updated
        self.console.print("[bold cyan]Parse Results:[/bold cyan]")
        self.console.print(f"  [dim]Trading Pairs:[/dim] {', '.join(updates['trading_pairs'])}")
        self.console.print(f"  [dim]Timeframe:[/dim] {', '.join(updates['timeframes'])}")

        # Update database
        try:
            # First, delete old relational data
            cursor = db.conn.cursor()
            cursor.execute("DELETE FROM trader_pairs WHERE trader_id = ?", (trader_id,))
            cursor.execute("DELETE FROM trader_intervals WHERE trader_id = ?", (trader_id,))

            # Update main record
            db.update_trader(trader_id, updates)

            # Re-add relational data
            if updates['trading_pairs']:
                db.add_trader_pairs(trader_id, updates['trading_pairs'])
            if updates['timeframes']:
                db.add_trader_intervals(trader_id, updates['timeframes'])

            db.conn.commit()

            self.console.print(f"\n[green]✓trader {trader_id} has been successfully reloaded[/green]")

        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")

    def _delete_trader(self, db, trader_id: str):
        """deletetrader（includingdatalibraryrecordsand md File）

        Args:
            db: TraderDatabase instance
            trader_id:Trader ID
        """
        import os

        # Get trader info first
        trader = db.get_trader(trader_id)

        if not trader:
            self.console.print(f"[yellow]Trader with ID '{trader_id}' not found[/yellow]")
            return

        # Show trader info for confirmation
        chars = trader.get('characteristics', {})
        name = chars.get('name', 'N/A')
        style = trader.get('style', 'N/A').replace('_', ' ').title()
        trader_file = trader.get('trader_file', '')

        self.console.print(f"\n[bold yellow]About to delete trader:[/bold yellow]")
        self.console.print(f"  [cyan]ID:[/cyan] {trader_id}")
        self.console.print(f"  [cyan]Name:[/cyan] {name}")
        self.console.print(f"  [cyan]Style:[/cyan] {style}")
        self.console.print(f"  [cyan]File:[/cyan] {trader_file}")

        # Confirm deletion
        from rich.prompt import Confirm
        if not Confirm.ask("[bold red]Confirm deletion？[/bold red]", default=False):
            self.console.print("[yellow]Cancelled[/yellow]")
            return

        # Delete from database
        success = db.delete_trader(trader_id)

        if not success:
            self.console.print(f"[red]Failed to delete from database[/red]")
            return

        # Delete trader folder (contains profile.md)
        if trader_file and os.path.exists(trader_file):
            trader_folder = os.path.dirname(trader_file)
            try:
                shutil.rmtree(trader_folder)
                self.console.print(f"[green]✓ has beendeleteFilemargin: {trader_folder}[/green]")
            except Exception as e:
                self.console.print(f"[yellow]Warning: CannotdeleteFilemargin {trader_folder}: {e}[/yellow]")
                self.console.print("[dim]Filemargin mayhas beenbeen manuallydeleteorinsufficient permissions[/dim]")

        self.console.print(f"[green]✓trader '{trader_id}' has been successfully deleted[/green]")

    def _delete_traders(self, db, trader_ids: list):
        """batchdeletetrader（includingdatalibraryrecordsand md File）

        Args:
            db: TraderDatabase instance
            trader_ids:Trader ID List
        """
        if not trader_ids:
            self.console.print("[yellow]notspecify anyTrader ID[/yellow]")
            return

        # Verify all trader_id exists
        valid_traders = []
        invalid_ids = []
        for trader_id in trader_ids:
            trader = db.get_trader(trader_id)
            if trader:
                valid_traders.append((trader_id, trader))
            else:
                invalid_ids.append(trader_id)

        if invalid_ids:
            self.console.print(f"[yellow]Warning: following ID does not exist: {', '.join(invalid_ids)}[/yellow]")

        if not valid_traders:
            self.console.print("[red]nofoundvalid oftrader[/red]")
            return

        # displaypendingdelete oftraderList
        from rich.table import Table
        table = Table(title=f"[bold yellow]about todelete {len(valid_traders)} traderstrader[/bold yellow]", show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", width=10)
        table.add_column("Name", style="green", width=20)
        table.add_column("Style", style="yellow", width=20)
        table.add_column("File", style="dim")

        for trader_id, trader in valid_traders:
            chars = trader.get('characteristics', {})
            name = chars.get('name', 'N/A')
            style = trader.get('style', 'N/A').replace('_', ' ').title()
            trader_file = trader.get('trader_file', 'N/A')
            table.add_row(trader_id, name, style, trader_file)

        self.console.print(table)

        # Confirm deletion
        from rich.prompt import Confirm
        if not Confirm.ask(f"[bold red]Confirm deleting {len(valid_traders)} traders?[/bold red]", default=False):
            self.console.print("[yellow]Deletion cancelled[/yellow]")
            return

        # Batch delete
        import os
        success_count = 0
        failed_count = 0

        for trader_id, trader in valid_traders:
            # Delete from database
            success = db.delete_trader(trader_id)

            if not success:
                self.console.print(f"[red]✗ Trader '{trader_id}' failed to delete from database[/red]")
                failed_count += 1
                continue

            # Delete trader folder (contains profile.md)
            trader_file = trader.get('trader_file', '')
            if trader_file and os.path.exists(trader_file):
                trader_folder = os.path.dirname(trader_file)
                try:
                    shutil.rmtree(trader_folder)
                    self.console.print(f"[green]✓ Trader '{trader_id}' successfully deleted[/green]")
                    success_count += 1
                except Exception as e:
                    self.console.print(f"[yellow]⚠ Trader '{trader_id}' database deleted, but folder deletion failed: {e}[/yellow]")
                    failed_count += 1
            else:
                self.console.print(f"[green]✓trader '{trader_id}' has been successfully deleted[/green]")
                success_count += 1

        # Show summary
        self.console.print(f"\n[bold]Deletion complete:[/bold] {success_count} succeeded, {failed_count} failed")

    def _show_trader_detail(self, db, trader_id: str):
        """Display detailed trader information

        Args:
            db: TraderDatabase instance
            trader_id:Trader ID
        """
        trader = db.get_trader(trader_id)

        if not trader:
            self.console.print(f"[yellow]Trader with ID '{trader_id}' not found[/yellow]")
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
        title_text.append(f"Trader Details: {name} ", style="bold cyan")
        title_text.append(f"(ID: {trader_id})", style="dim")

        # Content
        content = f"""
[bold yellow]Basic Information[/bold yellow]
  Name: {name}
  Experience Level: {experience}
  Risk Preference: {risk}
  capitalconfiguration: {capital}

[bold yellow]Trading Style[/bold yellow]
  Style: {style}
  timeTimeframe: {', '.join(timeframes) if timeframes else 'N/A'}

[bold yellow]Trading instruments[/bold yellow]
  Trading Pairs:
"""

        for pair in pairs[:10]:
            content += f"    • {pair}\n"
        if len(pairs) > 10:
            content += f"    ... still has {len(pairs) - 10} traders\n"

        content += f"\n  technicalindicator ({len(indicators)} traders):\n"
        for indicator in indicators[:8]:
            content += f"    • {indicator}\n"
        if len(indicators) > 8:
            content += f"    ... still has {len(indicators) - 8} traders\n"

        content += f"""
[bold yellow]otherinformation[/bold yellow]
  Created: {created}
  Filepath: {trader_file}
"""

        panel = Panel(content, title=title_text, border_style="cyan")
        self.console.print(panel)

    async def _edit_trader(self, db, trader_id: str, prompt: str):
        """edittrader（Use Claude Code modify md Fileanddatalibrary）

        Args:
            db: TraderDatabase instance
            trader_id:Trader ID
            prompt: modifyhintword
        """
        import os
        import subprocess

        # Get trader info first
        trader = db.get_trader(trader_id)

        if not trader:
            self.console.print(f"[yellow]Trader with ID '{trader_id}' not found[/yellow]")
            return

        # Get trader file path
        trader_file = trader.get('trader_file', '')
        if not trader_file or not os.path.exists(trader_file):
            self.console.print(f"[red]Error: Trader file not found {trader_file}[/red]")
            return

        # Show trader info
        chars = trader.get('characteristics', {})
        name = chars.get('name', 'N/A')
        style = trader.get('style', 'N/A').replace('_', ' ').title()

        self.console.print(f"\n[bold cyan]Modifyingtrader:[/bold cyan]")
        self.console.print(f"  [dim]ID:[/dim] {trader_id}")
        self.console.print(f"  [dim]Name:[/dim] {name}")
        self.console.print(f"  [dim]Style:[/dim] {style}")
        self.console.print(f"  [dim]File:[/dim] {trader_file}")
        self.console.print(f"  [dim]Modification request:[/dim] {prompt}\n")

        # Check if TRADERS.md exists
        project_root = Path(__file__).parent.parent
        traders_guide = project_root / "traders" / "TRADERS.md"

        if not traders_guide.exists():
            self.console.print(f"[red]Error: {traders_guide} not found[/red]")
            return

        # Find Claude Code executable
        claude_path = shutil.which("claude")
        if not claude_path:
            self.console.print(
                "[red]Error: Claude Code executable not found[/red]"
            )
            self.console.print(
                "[yellow]Please visit https://code.claude.com to install Claude Code[/yellow]"
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
   - Keep the sameTrader ID: {trader_id}
   - Keep the same folder structure (profile.md file name)
   - Maintain the markdown structure and template from TRADERS.md
   - Only modify the relevant sections based on the user's request
   - Preserve information that isn't directly related to the change request
   - Save your changes to profile.md in the current directory

5. After making changes, verify:
   - The file follows the TRADERS.md template structure
   - All required sections are present
   - TheTrader ID remains unchanged

Edit the profile.md file now."""

        self.console.print("[cyan]Nowcalling Claude Code modifytraderprofile...[/cyan]\n")

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
                self.console.print("[yellow]notdetectedtoFilemodify[/yellow]")
                self.console.print(f"[dim]Claude Code output:\n{result.stdout}[/dim]")
                if result.stderr:
                    self.console.print(f"[dim]Error:\n{result.stderr}[/dim]")
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
                self.console.print(f"[green]✓trader '{trader_id}' has beenSuccessmodify[/green]")
                self.console.print(f"[dim]datalibraryrecordshas beensyncmorenew[/dim]")
            else:
                self.console.print(f"[yellow]Warning: Filehas beenmodify，butdatalibrarymorenewfailed[/yellow]")

            # Show Claude output if there were issues
            if result.returncode != 0:
                self.console.print(f"\n[dim]Claude Code exit code: {result.returncode}[/dim]")
                if result.stderr:
                    self.console.print(f"[dim]Erroroutput:\n{result.stderr}[/dim]")

        except subprocess.TimeoutExpired:
            self.console.print("[red]Error: Claude Code Execution timeout (5minutes)[/red]")
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")

    async def _fetch_and_display_pairs(self, exchange: str):
        """fetchanddisplayexchange ofperpetual futuresTrading Pairs

        Args:
            exchange: exchangeName
        """
        self.console.print(f"[cyan]Nowfetch {exchange.upper()} perpetual futuresTrading PairsList...[/cyan]")

        try:
            # Use CCXT fetchperpetual futuresmarket
            markets = await fetch_pairs_ccxt(exchange)

            if not markets:
                self.console.print("[yellow]notfetchtoTrading Pairsdata[/yellow]")
                return

            # Sync pairs to database
            from cryptobot.trader_db import TraderDatabase
            db = TraderDatabase()
            db.initialize()
            synced_count = db.sync_pairs_from_exchange(exchange, markets)
            self.console.print(f"[green]Synced {synced_count} trading pairs to database[/green]")
            db.close()

            # filter active of USDT perpetual futures
            usdt_pairs = []
            for market in markets:
                symbol = market['symbol']
                # onlydisplayactive of USDT contract
                if market.get('active', True) and 'USDT' in symbol.upper():
                    # standardized symbol display（remove CCXT specialformat）
                    display_symbol = symbol.replace('/', '').replace(':', '').replace('-', '')
                    usdt_pairs.append({
                        'symbol': display_symbol,
                        'ccxt_symbol': symbol,
                        'base': market.get('base'),
                        'contract': market.get('contract', True),
                    })

            # displayTrading Pairs
            self.console.print(f"\n[green]{exchange.upper()} supports of USDT perpetual futures (Total {len(usdt_pairs)} traders):[/green]\n")

            # Use Rich tabledisplay
            from rich.table import Table

            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("rank", style="dim", width=6)
            table.add_column("Trading Pairs", style="cyan", width=16)
            table.add_column("base currency", style="green", width=12)
            table.add_column("rank", style="dim", width=6)
            table.add_column("Trading Pairs", style="cyan", width=16)
            table.add_column("base currency", style="green", width=12)

            # in two columnsdisplay，displayfirst100tradersTrading Pairs
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
                self.console.print(f"\n[dim]note: onlydisplayfirst {max_display} tradersTrading Pairs，Total {len(usdt_pairs)} traders[/dim]")

            self.console.print(f"\n[dim]hint: Use /market {exchange} <Trading Pairs> <Timeframe> fetch more data[/dim]")
            self.console.print(f"[dim]notemeaning: alldataare allperpetual futures（perpetual futures/swap）data[/dim]")

        except ValueError as e:
            self.console.print(f"[red]Error: {e}[/red]")
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")

    def _display_supported_intervals(self):
        """displaysupports of KlineTimeframe"""
        from cryptobot.trader_db import TraderDatabase
        from rich.table import Table

        # Read intervals from database
        db = TraderDatabase()
        db.initialize()
        intervals_data = db.get_all_intervals()
        db.close()

        table = Table(title="supports of KlineTimeframe", show_header=True, header_style="bold cyan")
        table.add_column("Timeframecode", style="green", width=8)
        table.add_column("description", style="white", width=12)
        table.add_column("Timeframecode", style="green", width=8)
        table.add_column("description", style="white", width=12)

        # in two columnsdisplay
        for i in range(0, len(intervals_data), 2):
            if i + 1 < len(intervals_data):
                row1 = intervals_data[i]
                row2 = intervals_data[i + 1]
                table.add_row(
                    row1['code'], row1['name'],
                    row2['code'], row2['name']
                )
            else:
                row1 = intervals_data[i]
                table.add_row(row1['code'], row1['name'], "", "")

        self.console.print(table)
        self.console.print("\n[dim]hint: Use /market <exchange> <Trading Pairs> <Timeframe> fetch more data[/dim]")

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

            # ExtractTrader ID
            id_match = re.search(r'\*\*Trader ID:\*\*\s*`([^`]+)`', content)
            if id_match:
                result['id'] = id_match.group(1)
            else:
                # fromFilenameextractnumberID（format：TraderName_123.md）
                import re
                filename = trader_file.stem  # remove.mdsuffix
                numbers = re.findall(r'\d+', filename)
                if numbers:
                    # Usenumberpart asID
                    result['id'] = numbers[-1]
                else:
                    # ifnonumber，UsewholetradersFilename
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

            # Extract Timeframes and normalize to standard codes
            # Note: Removed broad keys like 'minute', 'hour', 'day' to avoid
            # matching '15m' as 'minute' -> '1m' or '4h' as 'hour' -> '1h'
            timeframe_map = {
                '1m': '1m', '1 minute': '1m', '1-minute': '1m',
                '3m': '3m', '3 minutes': '3m', '3-minute': '3m',
                '5m': '5m', '5 minutes': '5m', '5-minute': '5m',
                '15m': '15m', '15 minutes': '15m', '15-minute': '15m',
                '30m': '30m', '30 minutes': '30m', '30-minute': '30m',
                '1h': '1h', '1 hour': '1h', '1-hour': '1h',
                '2h': '2h', '2 hours': '2h', '2-hour': '2h',
                '4h': '4h', '4 hour': '4h', '4-hour': '4h', '4 hours': '4h',
                '6h': '6h', '6 hours': '6h', '6-hour': '6h',
                '12h': '12h', '12 hours': '12h', '12-hour': '12h',
                '1d': '1d', 'daily': '1d',
                '1w': '1w', 'weekly': '1w',
                '1M': '1M', 'monthly': '1M',
            }

            def extract_timeframes(text):
                """Extract all timeframe codes from text (returns list)"""
                import re
                text_lower = text.lower()
                found = []
                # Sort keys by length (descending) to match more specific patterns first
                sorted_keys = sorted(timeframe_map.keys(), key=len, reverse=True)

                # Find all matching timeframes using word boundary matching
                # to avoid matching '5m' in '15m' or 'minute' in '15-minute'
                for key in sorted_keys:
                    # Create pattern with word boundaries
                    # Replace spaces with \s+ to handle variations
                    pattern = r'\b' + re.escape(key).replace(r'\ ', r'\s+') + r'\b'
                    if re.search(pattern, text_lower, re.IGNORECASE):
                        code = timeframe_map[key]
                        if code not in found:
                            found.append(code)
                return found

            analysis_tf_match = re.search(r'- \*\*Analysis Timeframe:\*\*\s*(.+)', content)
            if analysis_tf_match:
                tf_text = analysis_tf_match.group(1).strip()
                # Extract timeframes from text like "Daily and 4-hour charts"
                timeframes = extract_timeframes(tf_text)
                for tf in timeframes:
                    if tf not in result['timeframes']:
                        result['timeframes'].append(tf)

            entry_tf_match = re.search(r'- \*\*Entry Timeframe:\*\*\s*(.+)', content)
            if entry_tf_match:
                tf_text = entry_tf_match.group(1).strip()
                # Extract all timeframes from entry timeframe line
                timeframes = extract_timeframes(tf_text)
                for tf in timeframes:
                    if tf not in result['timeframes']:
                        result['timeframes'].append(tf)

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

            # Clean up lists to remove duplicates (use dict.fromkeys to preserve order)
            result['trading_pairs'] = list(dict.fromkeys(result['trading_pairs']))
            result['timeframes'] = list(dict.fromkeys(result['timeframes']))
            result['indicators'] = list(dict.fromkeys(result['indicators']))
            result['information_sources'] = list(dict.fromkeys(result['information_sources']))

            # Limit to 1-5 items for focus and specialization
            # Take first 5 trading pairs (most important ones)
            if len(result['trading_pairs']) > 5:
                result['trading_pairs'] = result['trading_pairs'][:5]
            # Take first 5 timeframes (most important ones) - increased from 3 to 5
            # to better support multi-timeframe strategies
            if len(result['timeframes']) > 5:
                result['timeframes'] = result['timeframes'][:5]

        except Exception as e:
            result['metadata']['parse_errors'].append(str(e))

        return result

    async def _fetch_top_trading_pairs(self, exchange: str = "binance", limit: int = 100) -> list:
        """fetchmainstreamperpetual futuresTrading PairsList

        Args:
            exchange: exchangeName
            limit: returnTrading Pairsquantity

        Returns:
            Trading PairssymbolList
        """
        try:
            # Use CCXT fetchperpetual futuresmarket
            markets = await fetch_pairs_ccxt(exchange)

            if not markets:
                return []

            # Filter and extract USDT perpetual futures
            pairs = []
            for market in markets:
                symbol = market['symbol']
                # onlyreturnactive of USDT perpetual futures
                if market.get('active', True) and 'USDT' in symbol.upper():
                    # standardizedformat（remove CCXT specialcharacter）
                    normalized = symbol.replace('/', '').replace(':', '').replace('-', '')
                    pairs.append(normalized)

            return pairs[:limit]

        except Exception as e:
            self.console.print(f"[yellow]fetchTrading PairsListfailed: {e}[/yellow]")
            return []

        return []

    def _get_next_trader_id(self, db) -> int:
        """fetchnexttraderstradernumberID

        Args:
            db: TraderDatabase instance

        Returns:
            nexttradersavailable ofnumberID
        """
        try:
            # fetchalltraderID
            traders = db.list_traders()

            # extractallnumberID
            numeric_ids = []
            for trader in traders:
                trader_id = trader.get('id', '')
                # trytryfromFilenameorIDinextractnumberpart
                # supportsformat：TraderName_123.md or 123.md oronlyis 123
                import re
                numbers = re.findall(r'\d+', trader_id)
                if numbers:
                    numeric_ids.append(int(numbers[-1]))  # take lasttradersnumber

            # returnmostlargeID + 1，ifnothenreturn1
            if numeric_ids:
                return max(numeric_ids) + 1
            else:
                return 1

        except Exception as e:
            self.console.print(f"[yellow]fetchIDfailed，Usedefault value: {e}[/yellow]")
            return 1

    async def _handle_newtrader_command(self, args: list):
        """Handle the /newtrader command

        Generates a new trader profile using Claude Code as a subprocess.

        Args:
            args: Command arguments (optional prompt for trader generation, -t for repeat count)
        """

        # Parse -t parameter (repeat count)
        repeat_count = 1
        prompt_args = []
        i = 0
        while i < len(args):
            if args[i] == '-t' and i + 1 < len(args):
                try:
                    repeat_count = int(args[i + 1])
                    if repeat_count < 1:
                        repeat_count = 1
                    i += 2  # Skip both -t and the number
                except ValueError:
                    self.console.print("[red]Error: -t parametersmust be followed by atradersvalid ofnumber[/red]")
                    return
            else:
                prompt_args.append(args[i])
                i += 1

        # Check if TRADERS.md exists
        project_root = Path(__file__).parent.parent
        traders_dir = project_root / "traders"
        traders_guide = traders_dir / "TRADERS.md"

        if not traders_guide.exists():
            self.console.print(
                f"[red]Error: Cannot find {traders_guide}[/red]"
            )
            self.console.print(
                "[yellow]Please ensure TRADERS.md Fileexists in traders/ directoryin[/yellow]"
            )
            return

        # Find Claude Code executable
        claude_path = shutil.which("claude")
        if not claude_path:
            self.console.print(
                "[red]Error: Claude Code executable not found[/red]"
            )
            self.console.print(
                "[yellow]Please visit https://code.claude.com to install Claude Code[/yellow]"
            )
            return

        # Fetch available trading pairs
        self.console.print("[cyan]NowfetchavailableTrading PairsList...[/cyan]")
        top_pairs = await self._fetch_top_trading_pairs()

        if not top_pairs:
            self.console.print("[yellow]Warning: notcanfetchTrading PairsList，willUsedefaultList[/yellow]")
            top_pairs = [
                "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
                "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT"
            ]

        self.console.print(f"[green]has beenfetch {len(top_pairs)} tradersmainstreamTrading Pairs[/green]")

        # Prepare user prompt
        user_prompt = " ".join(prompt_args) if prompt_args else "Generate a unique, diverse cryptocurrency trader"

        # Loop to generate multiple traders if -t is specified
        for iteration in range(repeat_count):
            if repeat_count > 1:
                self.console.print(f"\n[bold cyan]===== generateth {iteration + 1}/{repeat_count} traderstrader =====[/bold cyan]\n")

            # Fetch next numeric ID for each iteration
            db = TraderDatabase()
            db.initialize()
            next_id = self._get_next_trader_id(db)
            db.close()

            # Get trader constraints from config
            from .scheduler_config import get_scheduler_config
            config = get_scheduler_config(str(traders_dir.parent / "traders.db"))
            max_pairs = config.get_int('trader.pairs.max', 10)
            max_intervals = config.get_int('trader.intervals.max', 5)
            min_interval_seconds = config.get_int('trader.intervals.min_seconds', 300)

            # Format min interval for display
            min_interval_display = f"{min_interval_seconds // 60} minutes" if min_interval_seconds >= 60 else f"{min_interval_seconds} seconds"

            # Format pairs list for instructions
            pairs_list = "\n".join([f"  - {pair}" for pair in top_pairs[:50]])  # Top 50 pairs

            # Get existing traders from database for context
            db = TraderDatabase()
            db.initialize()
            existing_traders = db.list_traders()
            db.close()

            # Format existing traders summary
            existing_traders_summary = ""
            if existing_traders:
                existing_traders_summary = "\nExisting Traders Summary:\n"
                for trader in existing_traders:
                    style = trader.get('style', 'N/A').replace('_', ' ').title()
                    chars = trader.get('characteristics', {})
                    risk = chars.get('risk_tolerance', 'N/A')

                    # Get trading pairs
                    pairs = trader.get('trading_pairs', [])
                    pairs_str = ', '.join(pairs[:5]) if pairs else 'N/A'
                    if len(pairs) > 5:
                        pairs_str += f' (+{len(pairs) - 5})'

                    # Get timeframes
                    intervals = trader.get('timeframes', [])
                    intervals_str = ', '.join(intervals[:4]) if intervals else 'N/A'
                    if len(intervals) > 4:
                        intervals_str += f' (+{len(intervals) - 4})'

                    existing_traders_summary += f"  - {trader.get('id', 'N/A')}: {style} | Risk: {risk} | Pairs: {pairs_str} | Timeframes: {intervals_str}\n"
                existing_traders_summary += "\nCreate a trader that is DISTINCTLY DIFFERENT from the existing ones above.\n"
            else:
                existing_traders_summary = "\nNo existing traders yet. You're creating the first one!\n"

            # Prepare instructions for Claude Code
            instructions = f"""Read the file TRADERS.md for complete instructions on generating traders.

{existing_traders_summary}

Your task: {user_prompt}

IMPORTANT - Trading Pairs Restriction:
You MUST ONLY select trading pairs from the following list (top {len(top_pairs)} pairs by volume):
{pairs_list}

Focus on mainstream, highly liquid pairs from the top of this list (especially BTC, ETH, BNB, SOL, XRP, etc.).

CRITICAL CONSTRAINTS - Trader Focus Limits:
These constraints ensure each trader maintains focus and specialization. You MUST adhere to them:

1. Maximum Trading Pairs: {max_pairs}
   - Each trader can ONLY trade up to {max_pairs} trading pair(s)
   - FEWER pairs = MORE FOCUSED and SPECIALIZED
   - Do NOT add extra pairs "for diversity" - the system handles diversity through multiple traders

2. Maximum Timeframes: {max_intervals}
   - Each trader can ONLY use up to {max_intervals} timeframe(s)
   - Choose timeframes that align with the strategy (e.g., day trader uses 1m/5m, swing trader uses 4h/1d)
   - FEWER timeframes = MORE CONSISTENT strategy execution

3. Minimum Timeframe: {min_interval_display}
   - Do NOT use timeframes shorter than {min_interval_display}
   - This prevents over-trading and excessive noise

These limits are BY DESIGN to keep traders focused. Better to have 3 focused traders each trading 2 pairs than 1 distracted trader trading 6 pairs.

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
6. ONLY use trading pairs from the provided list above
7. STRICTLY respect the trader focus limits above ({max_pairs} pairs max, {max_intervals} timeframes max, {min_interval_display} min timeframe)"""

            self.console.print("[cyan]Nowcalling Claude Code generatenew oftraderprofile...[/cyan]")
            self.console.print(f"[dim]hint: {user_prompt}[/dim]")
            self.console.print(f"[dim]traderID: {next_id}[/dim]\n")

            # Get list of existing trader folders BEFORE running Claude Code
            # Check for subdirectories containing profile.md
            trader_folders_before = set()
            for item in traders_dir.iterdir():
                if item.is_dir() and (item / "profile.md").exists():
                    trader_folders_before.add(item.name)

            md_files_before = set(f.name for f in traders_dir.glob("*.md") if f.name != "TRADERS.md")

            try:
                # Run Claude Code as subprocess with real-time output
                self.console.print("[dim]Claude Code Nowprocessingtask...[/dim]\n")

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
                    self.console.print("[red]Error: Claude Code Execution timeout（5minutes）[/red]")
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
                    self.console.print("[yellow]notdetectedtonewcreate oftraderFilemargin[/yellow]")
                    self.console.print(f"[dim]Claude Code output:\n{result.stdout}[/dim]")
                    if result.stderr:
                        self.console.print(f"[dim]Error:\n{result.stderr}[/dim]")
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
                            f"[yellow]Warning:trader '{trader_record['id']}' has beenexists indatalibraryin，skip[/yellow]"
                        )
                        continue

                    # Store original metadata for warning display
                    original_metadata = trader_record.get('metadata', {}).copy()

                    # Add to database
                    success = db.add_trader(trader_record)
                    if success:
                        new_traders_count += 1
                        self.console.print(
                            f"[green]✓trader '{trader_record['id']}' has beencreateandrecordstodatalibrary[/green]"
                        )

                        # Check for constraint warnings and display them
                        updated_metadata = trader_record.get('metadata', {})
                        warnings = updated_metadata.get('_constraint_warnings', [])
                        if warnings:
                            self.console.print(
                                f"[yellow]⚠ configurationtrimWarning:[/yellow]"
                            )
                            for warning in warnings:
                                self.console.print(f"  [dim]- {warning}[/dim]")
                    else:
                        self.console.print(
                            f"[yellow]Warning: Cannotwilltrader '{trader_record['id']}' addtodatalibrary[/yellow]"
                        )

                db.close()

                if new_traders_count > 0:
                    self.console.print(
                        f"\n[green]Success! has beencreate {new_traders_count} tradersnewtraderprofile[/green]"
                    )
                else:
                    self.console.print("[yellow]notcreatenewtrader[/yellow]")

                # Show Claude output if there were issues
                if result.returncode != 0:
                    self.console.print(f"\n[dim]Claude Code exit code: {result.returncode}[/dim]")

            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")
                import traceback
                self.console.print(f"[dim]{traceback.format_exc()}[/dim]")

    async def _handle_newindicator_command(self, args: list):
        """Handle the /newindicator command

        Generates a new indicator script using Claude Code as a subprocess.

        Args:
            args: Command arguments (prompt for indicator generation)
        """

        # Check if prompt is provided
        if not args:
            self.console.print("[red]Error: Please provideindicatordescriptionhintword[/red]")
            self.console.print("[yellow]Example: /indicators -a fetchcapitalfeeratehistoryhistorydata[/yellow]")
            return

        # Check if INDICATORS.md exists
        project_root = Path(__file__).parent.parent
        indicators_dir = project_root / "indicators"
        indicators_guide = indicators_dir / "INDICATORS.md"

        if not indicators_guide.exists():
            self.console.print(
                f"[red]Error: Cannot find {indicators_guide}[/red]"
            )
            self.console.print(
                "[yellow]Please ensure INDICATORS.md Fileexists in indicators/ directoryin[/yellow]"
            )
            return

        # Find Claude Code executable
        claude_path = shutil.which("claude")
        if not claude_path:
            self.console.print(
                "[red]Error: Claude Code executable not found[/red]"
            )
            self.console.print(
                "[yellow]Please visit https://code.claude.com to install Claude Code[/yellow]"
            )
            return

        # Prepare user prompt
        user_prompt = " ".join(args)

        # Get list of existing Python files BEFORE running Claude Code
        py_files_before = set(f.name for f in indicators_dir.glob("*.py") if f.name != "__init__.py")
        test_files_before = set(f.name for f in indicators_dir.glob("*test*.py"))

        # Prepare instructions for Claude Code
        instructions = f"""Read the file INDICATORS.md for complete instructions on writing indicator scripts.

Your task: {user_prompt}

Important requirements:
1. Follow the template in INDICATORS.md exactly
2. Output must be in CSV format
3. Include proper error handling (return CSV with 'error' column if failed)
4. Use argparse for command-line arguments
5. Add proper docstrings
6. Create a new Python file in the indicators/ directory

After writing the script, run a test to verify it works correctly.
Test by executing the script with sample parameters.

If test files are created during testing, clean them up after tests pass.
Only create ONE new indicator script."""

        self.console.print("[cyan]Nowcalling Claude Code generatenew ofindicatorscript...[/cyan]")
        self.console.print(f"[dim]hint: {user_prompt}[/dim]\n")

        try:
            # Run Claude Code as subprocess with real-time output
            self.console.print("[dim]Claude Code Nowprocessingtask...[/dim]\n")

            # Use Popen for real-time output streaming
            process = subprocess.Popen(
                [claude_path, "--print", instructions],
                cwd=str(indicators_dir),
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
                self.console.print("[red]Error: Claude Code Execution timeout（5minutes）[/red]")
                return

            result = type('obj', (object,), {
                'stdout': ''.join(output_lines),
                'stderr': '',
                'returncode': return_code
            })()

            # Get list of Python files AFTER running Claude Code
            py_files_after = set(f.name for f in indicators_dir.glob("*.py") if f.name != "__init__.py")

            # Find new files
            new_files = py_files_after - py_files_before

            if not new_files:
                self.console.print("[yellow]notdetectedtonewcreate ofindicatorscript[/yellow]")
                self.console.print(f"[dim]Claude Code output:\n{result.stdout}[/dim]")
                if result.stderr:
                    self.console.print(f"[dim]Error:\n{result.stderr}[/dim]")
                return

            # Check for test files and clean them up
            test_files_after = set(f.name for f in indicators_dir.glob("*test*.py"))
            new_test_files = test_files_after - test_files_before

            # Clean up test files
            for test_file in new_test_files:
                test_path = indicators_dir / test_file
                try:
                    test_path.unlink()
                    self.console.print(f"[dim]has beencleartestFile: {test_file}[/dim]")
                except Exception as e:
                    self.console.print(f"[yellow]Warning: CannotdeletetestFile {test_file}: {e}[/yellow]")

            # Report success
            self.console.print(f"\n[green]Success! has beencreate {len(new_files)} tradersnewindicatorscript[/green]")
            for script_file in new_files:
                self.console.print(f"  [cyan]• {script_file}[/cyan]")

            # Show Claude output if there were issues
            if result.returncode != 0:
                self.console.print(f"\n[dim]Claude Code exit code: {result.returncode}[/dim]")

        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")

    async def _handle_indicators_command(self, args: list):
        """Handle the /indicators command

        Creates, lists, deletes, or modifies indicator scripts in the indicators/ directory.

        Args:
            args: Command arguments (-a <prompt>) | (filename [-d] [-m <prompt>] [-t <args...>])
        """
        from rich.table import Table
        from rich.panel import Panel
        from rich.syntax import Syntax

        # Check if INDICATORS.md exists
        project_root = Path(__file__).parent.parent
        indicators_dir = project_root / "indicators"

        if not indicators_dir.exists():
            self.console.print(
                f"[red]Error: Cannot find {indicators_dir}[/red]"
            )
            return

        # Parse arguments
        filename = None
        add_mode = False
        add_prompt = None
        delete_mode = False
        modify_mode = False
        modify_prompt = None
        test_mode = False
        test_args = []

        # Check for -a flag first (add new indicator)
        if args and args[0] == '-a':
            add_mode = True
            # Everything after -a is the prompt
            add_prompt = ' '.join(args[1:]) if len(args) > 1 else None
        elif args:
            filename = args[0]
            # Check for flags
            if "-d" in args[1:]:
                delete_mode = True
            if "-m" in args[1:]:
                modify_mode = True
                try:
                    m_index = args.index("-m")
                    modify_prompt = " ".join(args[m_index + 1:]) if m_index + 1 < len(args) else None
                except ValueError:
                    modify_prompt = None
            if "-t" in args[1:]:
                test_mode = True
                try:
                    t_index = args.index("-t")
                    test_args = args[t_index + 1:] if t_index + 1 < len(args) else []
                except ValueError:
                    test_args = []

        # ADD MODE (create new indicator)
        if add_mode:
            # Call the newindicator handler with the prompt
            await self._handle_newindicator_command(add_prompt.split() if add_prompt else [])
            return

        # TEST MODE
        if test_mode and filename:
            if not filename.endswith('.py'):
                self.console.print("[red]Error: Filename must end with .py ending[/red]")
                return

            script_path = indicators_dir / filename

            if not script_path.exists():
                self.console.print(f"[red]Error: Cannot findFile {filename}[/red]")
                return

            self.console.print(f"[cyan]Nowtestexecute: {filename}[/cyan]")
            if test_args:
                self.console.print(f"[dim]parameters: {' '.join(test_args)}[/dim]")
            else:
                self.console.print("[dim]parameters: (No)[/dim]")
            self.console.print("")

            cmd = [sys.executable, str(script_path)] + test_args

            try:
                # Use Popen for real-time output streaming
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )

                # Stream output in real-time
                for line in process.stdout:
                    self.console.print(line.rstrip())

                process.wait()

                if process.returncode == 0:
                    self.console.print(f"\n[green]✓ scriptexecuteSuccess (exit code: {process.returncode})[/green]")
                else:
                    self.console.print(f"\n[yellow]scriptexecuteend (exit code: {process.returncode})[/yellow]")

            except Exception as e:
                self.console.print(f"[red]executeError: {e}[/red]")
            return

        # DELETE MODE
        if delete_mode and filename:
            if not filename.endswith('.py'):
                self.console.print("[red]Error: Filename must end with .py ending[/red]")
                return

            script_path = indicators_dir / filename

            if not script_path.exists():
                self.console.print(f"[red]Error: Cannot findFile {filename}[/red]")
                return

            # Prevent deletion of base.py
            if filename == "base.py":
                self.console.print("[red]Error: notcandelete base.py File[/red]")
                return

            # Confirm deletion
            self.console.print(f"[yellow]Confirm deletionscript: {filename} ?[/yellow]")
            self.console.print("[dim]thisoperateworknotcanrestorecomplex[/dim]")

            try:
                script_path.unlink()
                self.console.print(f"[green]✓ has beendelete {filename}[/green]")
            except Exception as e:
                self.console.print(f"[red]deletefailed: {e}[/red]")
            return

        # MODIFY MODE
        if modify_mode and filename:
            if not modify_prompt:
                self.console.print("[red]Error: Please providemodifyhintword[/red]")
                self.console.print("[yellow]Example: /indicators market_data.py -m increaseMACDindicator[/yellow]")
                return

            if not filename.endswith('.py'):
                self.console.print("[red]Error: Filename must end with .py ending[/red]")
                return

            script_path = indicators_dir / filename

            if not script_path.exists():
                self.console.print(f"[red]Error: Cannot findFile {filename}[/red]")
                return

            # Find Claude Code executable
            claude_path = shutil.which("claude")
            if not claude_path:
                self.console.print(
                    "[red]Error: notfound Claude Code canexecuteFile[/red]"
                )
                self.console.print(
                    "[yellow]Please visit https://code.claude.com install Claude Code[/yellow]"
                )
                return

            # Get file modification time before
            mtime_before = script_path.stat().st_mtime

            # Prepare instructions for Claude Code
            instructions = f"""Read the file INDICATORS.md for complete instructions on writing indicator scripts.

Your task: Modify the file {filename} according to the following request:
{modify_prompt}

Important requirements:
1. Follow the template in INDICATORS.md exactly
2. Maintain CSV output format
3. Keep existing functionality unless asked to change it
4. Preserve proper error handling
5. Add proper docstrings for any new code

After modifying the script, run a test to verify it works correctly.
Test by executing the script with sample parameters.

If test files are created during testing, clean them up after tests pass."""

            self.console.print("[cyan]Nowcalling Claude Code modifyindicatorscript...[/cyan]")
            self.console.print(f"[dim]File: {filename}[/dim]")
            self.console.print(f"[dim]modify: {modify_prompt}[/dim]\n")

            try:
                # Run Claude Code as subprocess with real-time output
                self.console.print("[dim]Claude Code Nowprocessingtask...[/dim]\n")

                # Use Popen for real-time output streaming
                process = subprocess.Popen(
                    [claude_path, "--print", instructions],
                    cwd=str(indicators_dir),
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
                    self.console.print("[red]Error: Claude Code Execution timeout（5minutes）[/red]")
                    return

                # Check if file was modified
                mtime_after = script_path.stat().st_mtime
                if mtime_after > mtime_before:
                    self.console.print(f"\n[green]✓ {filename} has beenSuccessmodify[/green]")
                else:
                    self.console.print(f"[yellow]Warning: notdetectedtoFilemodify[/yellow]")

                # Check for test files and clean them up
                test_files = list(indicators_dir.glob("*test*.py"))
                for test_file in test_files:
                    try:
                        test_file.unlink()
                        self.console.print(f"[dim]has beencleartestFile: {test_file.name}[/dim]")
                    except Exception as e:
                        self.console.print(f"[yellow]Warning: CannotdeletetestFile {test_file.name}: {e}[/yellow]")

            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")
                import traceback
                self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
            return

        # VIEW SINGLE FILE MODE
        if filename:
            if not filename.endswith('.py'):
                self.console.print("[red]Error: Filename must end with .py ending[/red]")
                return

            script_path = indicators_dir / filename

            if not script_path.exists():
                self.console.print(f"[red]Error: Cannot findFile {filename}[/red]")
                return

            # Read and display file content
            try:
                content = script_path.read_text(encoding='utf-8')

                # Display with syntax highlighting
                syntax = Syntax(content, "python", theme="monokai", line_numbers=True)
                panel = Panel(syntax, title=f"[bold cyan]{filename}[/bold cyan]", border_style="cyan")
                self.console.print("\n", panel)

            except Exception as e:
                self.console.print(f"[red]readFileError: {e}[/red]")
            return

        # LIST ALL MODE (default)
        py_files = [f for f in indicators_dir.glob("*.py") if f.name != "__init__.py"]

        if not py_files:
            self.console.print("[yellow]notfoundindicatorscript[/yellow]")
            return

        # Create table for display
        table = Table(title="[bold cyan]indicatorscriptList[/bold cyan]", show_header=True, header_style="bold magenta")
        table.add_column("Filename", style="cyan", width=20)
        table.add_column("description", style="white")
        table.add_column("parameters", style="yellow")

        # Read each file to extract docstring
        for script_file in sorted(py_files):
            try:
                content = script_file.read_text(encoding='utf-8')

                # Extract docstring (first multiline string after file start)
                docstring = ""
                lines = content.split('\n')

                # Look for docstring pattern
                in_docstring = False
                docstring_lines = []

                for i, line in enumerate(lines):
                    stripped = line.strip()

                    # Look for opening triple quotes
                    if '"""' in stripped or "'''" in stripped:
                        if not in_docstring:
                            in_docstring = True
                            # Remove the quotes and add content
                            quote_start = stripped.find('"""') if '"""' in stripped else stripped.find("'''")
                            content_part = stripped[quote_start + 3:].strip()
                            if content_part:  # Content on same line
                                docstring_lines.append(content_part)
                            # Check if closing on same line
                            if stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                                in_docstring = False
                                break
                        else:
                            # Closing quotes
                            in_docstring = False
                            break
                    elif in_docstring:
                        docstring_lines.append(stripped)

                    # Stop if we've gone too far (not in docstring anymore)
                    if not in_docstring and len(docstring_lines) > 0:
                        break

                if docstring_lines:
                    # Join and clean up
                    docstring = ' '.join(docstring_lines)
                else:
                    docstring = "[dim]Nodescription[/dim]"

                # Extract argparse parameters
                params = []
                import re
                for line in lines:
                    stripped = line.strip()
                    # Extract add_argument calls
                    if 'parser.add_argument' in stripped:
                        # Extract argument name
                        arg_match = re.search(r"--?[\w-]+", stripped)
                        if arg_match:
                            arg_name = arg_match.group(0)
                            # Extract help text if available
                            help_match = re.search(r'help=[\'"]([^\'\"]+)[\'"]', stripped)
                            if help_match:
                                help_text = help_match.group(1)
                                params.append(f"{arg_name} ({help_text})")
                            else:
                                params.append(arg_name)
                    # Stop if we've reached the main execution part
                    if 'args = parser.parse_args()' in stripped or 'args.parse_args()' in stripped:
                        break

                param_str = ', '.join(params) if params else "[dim]Noparameters[/dim]"

                table.add_row(script_file.name, docstring, param_str)

            except Exception as e:
                table.add_row(script_file.name, f"[red]readError: {e}[/red]", "[dim]-[/dim]")

        self.console.print("\n")
        self.console.print(table)

        # Show usage hint
        self.console.print("\n[dim]hint:[/dim]")
        self.console.print("[dim]  /indicators -a <description> createnew ofindicatorscript[/dim]")
        self.console.print("[dim]  /indicators <Filename> viewscriptdetails[/dim]")
        self.console.print("[dim]  /indicators <Filename> -d deletescript[/dim]")
        self.console.print("[dim]  /indicators <Filename> -m <hint> modifyscript[/dim]")
        self.console.print("[dim]  /indicators <Filename> -t [parameters...] testexecutescript[/dim]")

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
            self.console.print("[red]Error: Please provide trader_id[/red]")
            return

        trader_id = args[0]

        # Verify trader exists
        with TraderDatabase() as db:
            trader = db.get_trader(trader_id)
            if not trader:
                self.console.print(f"[red]Error: notfoundtrader {trader_id}[/red]")
                return

        # Check if --wait flag is present
        wait_for_completion = '--wait' in args

        # Execute decision (wait for completion by default for better UX)
        await self._execute_decision_process(trader_id, verbose=True)

    async def _execute_decision_process(self, trader_id: str, verbose: bool = True):
        """Execute the full decision workflow

        Args:
            trader_id:Trader ID
        """
        import os
        import json
        import tempfile
        from pathlib import Path

        try:
            # Phase 1: Gather data
            if verbose:
                self.console.print(f"[Phase 1] collecttrader {trader_id} data...")

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
                if verbose:
                    self.console.print(f"[Warning] Cannotmorenewprice: {e}")

            # Build decision context
            decision_context = self._build_decision_context(trader, open_positions, summary, profile_content)

            # Phase 2: AI initial assessment
            if verbose:
                self.console.print("[Phase 2] AI initialstepanalyzein...")
            phase1_prompt = self._build_phase1_prompt(decision_context)
            phase1_response = await self._call_claude_code_for_decision(phase1_prompt, trader_id)

            if not phase1_response or phase1_response.startswith("ERROR"):
                self.console.print(f"[Error] AI callingfailed: {phase1_response}")
                return "ERROR"

            # Show brief summary of AI response
            if verbose:
                response_lines = phase1_response.strip().split('\n')
                first_line = response_lines[0] if response_lines else phase1_response[:100]
                self.console.print(f"[AI response] {first_line}")

            # Phase 3: Execute indicators if needed
            indicator_data = {}
            response_upper = phase1_response.upper()

            if "NEED_ORDERBOOK" in response_upper or "NEED_MARKET" in response_upper or "NEED_BOTH" in response_upper:
                if verbose:
                    self.console.print("[Phase 3] collectamountexternalmarketdata...")
                indicator_data = await self._execute_indicators_from_response(phase1_response, trader)

                if verbose and indicator_data:
                    self.console.print(f"[completed] has beencollectindicatordata: {list(indicator_data.keys())}")

            # Phase 4: Final decision
            if verbose:
                self.console.print("[Phase 4] make finaldecision...")
            phase2_prompt = self._build_phase2_prompt(decision_context, indicator_data, phase1_response)
            final_decision = await self._call_claude_code_for_decision(phase2_prompt, trader_id)

            if not final_decision or final_decision.startswith("ERROR"):
                self.console.print(f"[Error] finaldecisionfailed: {final_decision}")
                return "ERROR"

            # Extract decision from response - look for valid action keywords
            decision_lines = final_decision.strip().split('\n')
            actual_decision = None

            # Valid action keywords (prioritize longer actions first to avoid partial matches)
            valid_actions = ['CLOSE_POSITION', 'OPEN_LONG', 'OPEN_SHORT', 'CLOSE_ALL', 'HOLD']

            # Find the line containing a valid action
            for line in decision_lines:
                line_upper = line.upper().strip()
                # Check if any valid action appears in this line (as a standalone word)
                for action in valid_actions:
                    # Use word boundaries to match standalone actions
                    pattern = r'\b' + action + r'\b'
                    if re.search(pattern, line_upper):
                        # Extract the portion starting from the action
                        match = re.search(pattern + r'.*', line_upper)
                        if match:
                            actual_decision = match.group(0).strip()
                            # Convert back to original case for parameters
                            action_idx = line.upper().find(action)
                            actual_decision = line[action_idx:].strip()
                        break
                if actual_decision:
                    break

            # If still no valid action, try searching in the entire response
            if not actual_decision:
                response_upper = final_decision.upper()
                for action in valid_actions:
                    # Look for the action as a standalone word
                    pattern = r'\b' + action + r'\b'
                    if re.search(pattern, response_upper):
                        # Find the original line
                        for line in decision_lines:
                            if action in line.upper():
                                action_idx = line.upper().find(action)
                                actual_decision = line[action_idx:].strip()
                                break
                        if not actual_decision:
                            actual_decision = action
                        break

            # Final fallback: if no valid action found, default to HOLD
            if not actual_decision:
                if verbose:
                    self.console.print(f"[Warning] Cannotparsedecision，defaultas HOLD")
                    self.console.print(f"[debug] AI response: {final_decision[:200]}")
                actual_decision = "HOLD"

            if verbose:
                self.console.print(f"[AI decision] {actual_decision}")

            # Phase 5: Execute decision
            await self._execute_decision(actual_decision, trader_id)
            if verbose:
                self.console.print("[completed] decisionflowprocessend")

            # Return the decision for dashboard tracking
            return actual_decision

        except Exception as e:
            self.console.print(f"[Error] decisionprocessError: {e}")
            import traceback
            if verbose:
                self.console.print(f"[debug] {traceback.format_exc()}")
            return "ERROR"

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
            pos_info = f"\nCurrent positions ({len(positions['open'])}):\n"
            for p in positions['open'][:5]:  # Limit to 5 positions
                pos_info += f"  - {p.get('symbol')} {p.get('side')} size={p.get('size')} entry={p.get('entry_price')} pnl={p.get('unrealized_pnl', 0):.2f}\n"
            pos_info += f"\ntotalUnrealized P&L: {positions['summary'].get('total_unrealized_pnl', 0):.2f}\n"
            pos_info += f"totalRealized P&L: {positions['summary'].get('total_realized_pnl', 0):.2f}\n"
        else:
            pos_info = "\nCurrent positions: No\n"

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
-Trader ID: {trader['id']}
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
            trader_id:Trader ID for logging

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

    def _script_has_limit_param(self, script_name: str) -> bool:
        """Check if indicator script has a --limit parameter

        Args:
            script_name: Name of the indicator script

        Returns:
            True if script has --limit parameter
        """
        from pathlib import Path
        import re

        indicators_dir = Path(__file__).parent.parent / "indicators"
        script_path = indicators_dir / script_name

        if not script_path.exists():
            return False

        try:
            content = script_path.read_text(encoding='utf-8')
            # Check if script has --limit argument
            return bool(re.search(r"add_argument\s*\(\s*['\"]--limit", content))
        except Exception:
            return False

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

                print(f"[indicator] running fetch_orderbook: {exchange} {symbol}")
                orderbook_args = [
                    "--exchange", exchange,
                    "--symbol", symbol
                ]

                # Add limit if configured and script supports it
                from .scheduler_config import get_scheduler_config
                config = get_scheduler_config()
                limit_config = config.get_int('indicator.limit', 0)
                if limit_config > 0 and self._script_has_limit_param("fetch_orderbook.py"):
                    orderbook_args.extend(["--limit", str(limit_config)])

                orderbook_data = await self._run_indicator("fetch_orderbook.py", orderbook_args)
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

                print(f"[indicator] running market_data: {exchange} {symbol} {interval}")
                market_args = [
                    "--exchange", exchange,
                    "--symbol", symbol,
                    "--interval", interval
                ]

                # Add limit if configured and script supports it
                from .scheduler_config import get_scheduler_config
                config = get_scheduler_config()
                limit_config = config.get_int('indicator.limit', 0)
                if limit_config > 0 and self._script_has_limit_param("market_data.py"):
                    market_args.extend(["--limit", str(limit_config)])

                market_data = await self._run_indicator("market_data.py", market_args)
                if market_data and not market_data.startswith("error"):
                    results['market_data'] = market_data

        except Exception as e:
            self.console.print(f"[Warning] indicatorexecuteexception: {e}")

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
            self.console.print(f"[Error] indicatorscriptdoes not exist: {script_path}")
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
                self.console.print(f"[Warning] indicatorscriptError: {stderr.decode()[:100]}")
                return None

            return stdout.decode()

        except asyncio.TimeoutError:
            process.kill()
            self.console.print(f"[Warning] indicatortimeout: {script_name}")
            return None
        except Exception as e:
            self.console.print(f"[Warning] indicatorexecutefailed: {e}")
            return None

    async def _execute_decision(self, decision: str, trader_id: str):
        """Parse and execute AI decision

        Args:
            decision: Decision string from AI
            trader_id:Trader ID
        """
        decision = decision.strip()
        parts = decision.split()
        if not parts:
            self.console.print("[decision] emptydecision，No action")
            return

        action = parts[0].upper()

        try:
            if action == "OPEN_LONG":
                # Parse: OPEN_LONG <exchange> <symbol> <size> [leverage]
                if len(parts) < 4:
                    self.console.print(f"[Error] Invalid OPEN_LONG format: {decision}")
                    return
                exchange = parts[1]
                symbol = parts[2]
                size = float(parts[3])
                leverage = int(parts[4]) if len(parts) > 4 else None
                await self._handle_openposition_command([trader_id, exchange, symbol, "long", str(size)] + ([str(leverage)] if leverage else []))

            elif action == "OPEN_SHORT":
                # Parse: OPEN_SHORT <exchange> <symbol> <size> [leverage]
                if len(parts) < 4:
                    self.console.print(f"[Error] Invalid OPEN_SHORT format: {decision}")
                    return
                exchange = parts[1]
                symbol = parts[2]
                size = float(parts[3])
                leverage = int(parts[4]) if len(parts) > 4 else None
                await self._handle_openposition_command([trader_id, exchange, symbol, "short", str(size)] + ([str(leverage)] if leverage else []))

            elif action == "CLOSE_POSITION":
                # Parse: CLOSE_POSITION <position_id>
                if len(parts) < 2:
                    self.console.print(f"[Error] Invalid CLOSE_POSITION format: {decision}")
                    return
                position_id = parts[1]
                await self._handle_closeposition_command([position_id])

            elif action == "CLOSE_ALL":
                # Close all positions for trader
                with PositionDatabase() as db:
                    positions = db.list_positions(trader_id, status='open')
                    for pos in positions:
                        self.console.print(f"[execute] close: {pos.id}")
                        await self._handle_closeposition_command([str(pos.id)])

            elif action == "HOLD":
                print("[decision] hold - No action")

            else:
                self.console.print(f"[Error] notknowdecisiontype: {action}")

        except Exception as e:
            self.console.print(f"[Error] executedecisionfailed: {e}")
            import traceback
            self.console.print(f"[debug] {traceback.format_exc()}")

    async def _show_trader_positions(self, trader_id: str):
        """Display trader's positions with updated PnL

        Args:
            trader_id:Trader ID
        """
        from .position_db import PositionDatabase

        # Verify trader exists
        trader_db = TraderDatabase()
        trader_db.initialize()
        trader = trader_db.get_trader(trader_id)
        trader_db.close()

        if not trader:
            self.console.print(f"[yellow]Trader with ID '{trader_id}' not found[/yellow]")
            return

        # Initialize position database
        pos_db = PositionDatabase()
        pos_db.initialize()

        try:
            # Fetch current prices and update all positions
            self.console.print(f"[cyan]Nowfetch {trader_id} positionsinformation...[/cyan]")

            price_service = get_price_service()
            updated_positions = await price_service.update_trader_positions(trader_id, pos_db)

            # Get all positions
            all_positions = pos_db.list_positions(trader_id)

            if not all_positions:
                self.console.print(f"[yellow]trader {trader_id} temporarilyNoposition[/yellow]")
                return

            # Display positions table
            from rich.table import Table

            table = Table(
                title=f"[bold cyan]trader {trader_id} positions[/bold cyan]",
                show_header=True,
                header_style="bold magenta"
            )
            table.add_column("ID", style="cyan", width=6)
            table.add_column("exchange", style="green", width=10)
            table.add_column("Trading Pairs", style="white", width=12)
            table.add_column("direction", style="yellow", width=6)
            table.add_column("leverage", style="magenta", width=6)
            table.add_column("entry price", style="white", width=12)
            table.add_column("quantity", style="white", width=10)
            table.add_column("margin", style="white", width=10)
            table.add_column("Unrealized P&L", style="white", width=12)
            table.add_column("ROI %", style="white", width=10)
            table.add_column("status", style="white", width=10)

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
            summary_text.append(f"Total positions: {summary['total_positions']}\n", style="white")
            summary_text.append(f"Open: {summary['open_positions']}\n", style="green")
            summary_text.append(f"has beenclose: {summary['closed_positions']}\n", style="yellow")
            summary_text.append(f"Liquidated: {summary['liquidated_positions']}\n", style="red")
            summary_text.append(f"\nUnrealized P&L: ", style="white")
            summary_text.append(f"{summary['total_unrealized_pnl']:+.2f} USDT\n",
                             style="green" if summary['total_unrealized_pnl'] > 0 else "red")
            summary_text.append(f"Realized P&L: ", style="white")
            summary_text.append(f"{summary['total_realized_pnl']:+.2f} USDT\n",
                             style="green" if summary['total_realized_pnl'] > 0 else "red")
            summary_text.append(f"Average ROI: ", style="white")
            summary_text.append(f"{summary['average_roi']:+.2f}%",
                             style="green" if summary['average_roi'] > 0 else "red")
            summary_text.append(f"\n\nbalance: ", style="white")
            summary_text.append(f"{trader.get('current_balance', 0):.2f} USDT",
                             style="cyan")
            summary_text.append(f"\nequity: ", style="white")
            summary_text.append(f"{trader.get('equity', 0):.2f} USDT",
                             style="green" if trader.get('equity', 0) > trader.get('current_balance', 0) else "red")

            panel = Panel(summary_text, title="[bold cyan]positionstatistics[/bold cyan]", border_style="cyan")
            self.console.print("\n", panel)

            # Update trader equity with current unrealized PnL
            trader_db = TraderDatabase()
            trader_db.initialize()
            trader_db.update_equity_with_unrealized_pnl(trader_id, summary['total_unrealized_pnl'])
            trader_db.close()

        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
        finally:
            pos_db.close()

    async def _handle_openposition_command(self, args: list):
        """Handle opening a new position (called from /positions command with -o flag)

        Opens a new trading position.

        Args:
            args: Command arguments: <trader_id> <exchange> <symbol> <side> <size> [leverage]
        """
        # Parse arguments
        if len(args) < 5:
            self.console.print("[red]Error: parametersinsufficient[/red]")
            self.console.print("[yellow]Usage: /positions <trader_id> -o <exchange> <symbol> <side> <size> [leverage][/yellow]")
            self.console.print("[dim]Example: /positions 1 -o binance BTCUSDT long 0.5 10[/dim]")
            return

        trader_id = args[0]
        exchange = args[1]
        symbol = args[2]
        side = args[3].lower()

        try:
            size = float(args[4])
        except ValueError:
            self.console.print(f"[red]Error: Invalidpositionsize '{args[4]}'[/red]")
            return

        leverage = float(args[5]) if len(args) > 5 else 1.0

        # Validate inputs
        if side not in ('long', 'short'):
            self.console.print(f"[red]Error: Invaliddirection '{side}'. must be 'long' or 'short'[/red]")
            return

        if size <= 0:
            self.console.print(f"[red]Error: positionsizemust be greater than 0[/red]")
            return

        if leverage <= 0:
            self.console.print(f"[red]Error: leveragemust be greater than 0[/red]")
            return

        # Verify exchange is supported
        try:
            get_exchange_config(exchange)
        except ValueError as e:
            self.console.print(f"[red]Error: {e}[/red]")
            return

        # Verify trader exists
        trader_db = TraderDatabase()
        trader_db.initialize()
        trader = trader_db.get_trader(trader_id)
        trader_db.close()

        if not trader:
            self.console.print(f"[yellow]Trader with ID '{trader_id}' not found[/yellow]")
            return

        # Fetch current price
        try:
            price_service = get_price_service()
            entry_price = await price_service.fetch_current_price(exchange, symbol)
        except Exception as e:
            self.console.print(f"[red]Error: fetchpricefailed {exchange} {symbol}: {e}[/red]")
            return

        # Calculate fee
        try:
            entry_fee = calculate_fee(exchange, size, entry_price)
        except Exception as e:
            self.console.print(f"[red]Error: Calculate feefailed: {e}[/red]")
            return

        # Calculate margin
        margin = (size * entry_price) / leverage

        # Check if trader has sufficient balance
        required_margin = margin + entry_fee
        current_balance = trader.get('current_balance', 0)

        if current_balance < required_margin:
            self.console.print(f"[red]Error: balanceinsufficient[/red]")
            self.console.print(f"  [dim]whenfirstbalance:[/dim] {current_balance:.2f} USDT")
            self.console.print(f"  [dim]required amount:[/dim] {required_margin:.2f} USDT (margin: {margin:.2f} + fee: {entry_fee:.4f})")
            self.console.print(f"  [dim]difference:[/dim] {required_margin - current_balance:.2f} USDT")
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

            self.console.print(f"[green]✓ positionhas beenopen[/green]")
            self.console.print(f"  [dim]ID:[/dim] {position_id}")
            self.console.print(f"  [dim]trader:[/dim] {trader_id}")
            self.console.print(f"  [dim]exchange:[/dim] {exchange}")
            self.console.print(f"  [dim]Trading Pairs:[/dim] {symbol}")
            self.console.print(f"  [dim]direction:[/dim] {side}")
            self.console.print(f"  [dim]entry price:[/dim] {entry_price:.2f}")
            self.console.print(f"  [dim]quantity:[/dim] {size:.4f}")
            self.console.print(f"  [dim]leverage:[/dim] {leverage:.1f}x")
            self.console.print(f"  [dim]margin:[/dim] {margin:.2f} USDT")
            self.console.print(f"  [dim]fee:[/dim] {entry_fee:.4f} USDT")
            self.console.print(f"  [dim]liquidation price:[/dim] {position.liquidation_price:.2f}")
        except Exception as e:
            self.console.print(f"[red]Error: savepositionfailed: {e}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
        finally:
            pos_db.close()

    async def _handle_closeposition_command(self, args: list):
        """Handle closing a position (called from /positions command with -c flag)

        Closes an existing position.

        Args:
            args: Command arguments: <position_id> [price]
        """
        # Parse arguments
        if len(args) < 1:
            self.console.print("[red]Error: parametersinsufficient[/red]")
            self.console.print("[yellow]Usage: /positions <position_id> -c [price][/yellow]")
            self.console.print("[dim]Example: /positions 1 -c[/dim]")
            self.console.print("[dim]Example: /positions 1 -c 45000[/dim]")
            return

        try:
            position_id = int(args[0])
        except ValueError:
            self.console.print(f"[red]Error: Invalidposition ID '{args[0]}'[/red]")
            return

        # Get position from database
        pos_db = PositionDatabase()
        pos_db.initialize()

        try:
            position = pos_db.get_position(position_id)

            if not position:
                self.console.print(f"[yellow]notfound ID as '{position_id}' positions[/yellow]")
                return

            if position.status != PositionStatus.OPEN:
                self.console.print(f"[yellow]position {position_id} not openstatus (status: {position.status.value})[/yellow]")
                return

            # Determine exit price
            if len(args) > 1:
                try:
                    exit_price = float(args[1])
                except ValueError:
                    self.console.print(f"[red]Error: Invalidexitoutprice '{args[1]}'[/red]")
                    return
            else:
                # Fetch current price
                try:
                    price_service = get_price_service()
                    exit_price = await price_service.fetch_current_price(
                        position.exchange,
                        position.symbol
                    )
                    self.console.print(f"[dim]whenfirstprice: {exit_price:.2f}[/dim]")
                except Exception as e:
                    self.console.print(f"[red]Error: fetchpricefailed: {e}[/red]")
                    return

            # Calculate exit fee
            try:
                exit_fee = calculate_fee(position.exchange, position.position_size, exit_price)
            except Exception as e:
                self.console.print(f"[red]Error: Calculate feefailed: {e}[/red]")
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
                self.console.print(f"[green]✓ positionhas beenclose[/green]")
                self.console.print(f"  [dim]ID:[/dim] {position_id}")
                self.console.print(f"  [dim]Trading Pairs:[/dim] {position.symbol}")
                self.console.print(f"  [dim]entry price:[/dim] {position.entry_price:.2f}")
                self.console.print(f"  [dim]exit price:[/dim] {exit_price:.2f}")
                self.console.print(f"  [dim]entryfee:[/dim] {position.entry_fee:.4f} USDT")
                self.console.print(f"  [dim]exitfee:[/dim] {exit_fee:.4f} USDT")
                self.console.print(f"  [dim]totalfee:[/dim] {position.entry_fee + exit_fee:.4f} USDT")
                self.console.print(f"  [dim]Realized P&L: [{pnl_color}]{closed_position.realized_pnl:+.2f} USDT[/{pnl_color}]")
                self.console.print(f"  [dim]ROI: [{pnl_color}]{closed_position.roi:+.2f}%[/{pnl_color}]")
            else:
                self.console.print(f"[red]Error: closefailed[/red]")

        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
        finally:
            pos_db.close()

    async def _handle_positions_command(self, args: list):
        """processing /positions command

        Usage:
        - /positions                           - displayalltraderpositions
        - /positions <trader_id>               - displayspecifytraderpositions
        - /positions <trader_id> -o <params>   - openposition
        - /positions <position_id> -c [price]  - close

        Args:
            args: commandparameters
        """
        # Parse arguments
        open_flag = False
        close_flag = False
        trader_id = None
        position_id = None
        open_params = []
        close_price = None

        i = 0
        while i < len(args):
            arg = args[i]
            if arg == '-o':
                open_flag = True
                i += 1
                # Remaining arguments after -o are open parameters
                open_params = args[i:]
                break
            elif arg == '-c':
                close_flag = True
                i += 1
                # Optional price after -c
                if i < len(args):
                    try:
                        close_price = float(args[i])
                    except ValueError:
                        # Not a price, might be next argument (though unusual)
                        i -= 1
                break
            elif not arg.startswith('-'):
                # Could be trader_id or position_id
                if trader_id is None:
                    trader_id = arg
                elif position_id is None:
                    position_id = arg
                i += 1
            else:
                i += 1

        # Case 1: Open position (-o flag)
        if open_flag:
            if not trader_id:
                self.console.print("[red]Error: openpositionoperateworkneedwantspecifyTrader ID[/red]")
                self.console.print("[yellow]Usage: /positions <trader_id> -o <exchange> <symbol> <side> <size> [leverage][/yellow]")
                return
            # Combine trader_id with open_params and delegate to openposition handler
            full_args = [trader_id] + open_params
            await self._handle_openposition_command(full_args)
            return

        # Case 2: Close position (-c flag)
        if close_flag:
            # Use either trader_id or position_id (position_id takes priority)
            target_id = position_id or trader_id
            if not target_id:
                self.console.print("[red]Error: closeoperateworkneedwantspecifyposition ID[/red]")
                self.console.print("[yellow]Usage: /positions <position_id> -c [price][/yellow]")
                return
            # Combine position_id with optional price
            close_args = [target_id]
            if close_price is not None:
                close_args.append(str(close_price))
            await self._handle_closeposition_command(close_args)
            return

        # Case 3: Show specific trader's positions
        if trader_id:
            await self._show_trader_positions(trader_id)
            return

        # Case 4: Show all traders' positions (default)
        from rich.table import Table
        from rich.panel import Panel
        from rich.text import Text as RichText
        from rich.columns import Columns

        # Initialize databases
        trader_db = TraderDatabase()
        trader_db.initialize()

        pos_db = PositionDatabase()
        pos_db.initialize()

        try:
            # Get all traders
            traders = trader_db.list_traders()

            if not traders:
                self.console.print("[yellow]No trader profiles yet[/yellow]")
                self.console.print("[dim]Use /traders -a command to create new trader profile[/dim]")
                return

            # Fetch current prices and update all positions
            self.console.print("[cyan]Nowfetchalltraderpositionsinformation...[/cyan]")
            price_service = get_price_service()

            # Update positions for all traders
            for trader in traders:
                try:
                    await price_service.update_trader_positions(trader['id'], pos_db)
                except Exception as e:
                    self.console.print(f"[dim]Warning: morenew {trader['id']} positiontimeouterror: {e}[/dim]")

            # Collect positions by trader
            traders_with_positions = []

            for trader in traders:
                trader_id = trader['id']
                positions = pos_db.list_positions(trader_id)

                if positions:
                    # Get summary
                    summary = pos_db.get_trader_positions_summary(trader_id)

                    traders_with_positions.append({
                        'trader': trader,
                        'positions': positions,
                        'summary': summary
                    })

            if not traders_with_positions:
                self.console.print("[yellow]temporarilyNopositionrecords[/yellow]")
                return

            # Display each trader's positions
            for item in traders_with_positions:
                trader = item['trader']
                positions = item['positions']
                summary = item['summary']

                # Create positions table for this trader
                table = Table(
                    title=f"[bold cyan]trader {trader['id']} positions[/bold cyan]",
                    show_header=True,
                    header_style="bold magenta"
                )
                table.add_column("ID", style="cyan", width=6)
                table.add_column("exchange", style="green", width=10)
                table.add_column("Trading Pairs", style="white", width=12)
                table.add_column("direction", style="yellow", width=6)
                table.add_column("leverage", style="magenta", width=6)
                table.add_column("entry price", style="white", width=12)
                table.add_column("whenfirstprice", style="cyan", width=12)
                table.add_column("quantity", style="white", width=10)
                table.add_column("margin", style="white", width=10)
                table.add_column("P&L", style="white", width=12)
                table.add_column("ROI %", style="white", width=10)
                table.add_column("status", style="white", width=10)

                # Sort by PnL
                sorted_positions = sorted(
                    positions,
                    key=lambda p: p.unrealized_pnl if p.status == PositionStatus.OPEN else p.realized_pnl,
                    reverse=True
                )

                for pos in sorted_positions:
                    pnl = pos.unrealized_pnl if pos.status == PositionStatus.OPEN else pos.realized_pnl
                    pnl_color = "green" if pnl > 0 else "red" if pnl < 0 else "white"
                    pnl_str = f"[{pnl_color}]{pnl:+.2f}[/{pnl_color}]"

                    roi_color = "green" if pos.roi > 0 else "red" if pos.roi < 0 else "white"
                    roi_str = f"[{roi_color}]{pos.roi:+.2f}%[/{roi_color}]"

                    status_str = pos.status.value
                    status_color = "green" if pos.status == PositionStatus.OPEN else "yellow"

                    # Get current price from cache
                    current_price = price_service.get_cached_price(pos.exchange, pos.symbol)
                    current_price_str = f"{current_price:.2f}" if current_price else "N/A"

                    table.add_row(
                        str(pos.id),
                        pos.exchange,
                        pos.symbol,
                        pos.position_side.value,
                        f"{pos.leverage:.1f}x",
                        f"{pos.entry_price:.2f}",
                        current_price_str,
                        f"{pos.position_size:.4f}",
                        f"{pos.margin:.2f}",
                        pnl_str,
                        roi_str,
                        f"[{status_color}]{status_str}[/{status_color}]"
                    )

                self.console.print("\n", table)

                # Display summary for this trader
                summary_text = RichText()
                summary_text.append(f"Total positions: {summary['total_positions']}\n", style="white")
                summary_text.append(f"Open: {summary['open_positions']}\n", style="green")
                summary_text.append(f"has beenclose: {summary['closed_positions']}\n", style="yellow")
                summary_text.append(f"Liquidated: {summary['liquidated_positions']}\n", style="red")
                summary_text.append(f"\nUnrealized P&L: ", style="white")
                summary_text.append(f"{summary['total_unrealized_pnl']:+.2f} USDT\n",
                                 style="green" if summary['total_unrealized_pnl'] > 0 else "red")
                summary_text.append(f"Realized P&L: ", style="white")
                summary_text.append(f"{summary['total_realized_pnl']:+.2f} USDT\n",
                                 style="green" if summary['total_realized_pnl'] > 0 else "red")
                summary_text.append(f"Average ROI: ", style="white")
                summary_text.append(f"{summary['average_roi']:+.2f}%",
                                 style="green" if summary['average_roi'] > 0 else "red")
                summary_text.append(f"\n\nbalance: ", style="white")
                summary_text.append(f"{trader.get('current_balance', 0):.2f} USDT",
                                 style="cyan")
                summary_text.append(f"\nequity: ", style="white")
                equity = trader.get('equity', 0)
                balance = trader.get('current_balance', 0)
                equity_color = "green" if equity > balance else "red" if equity < balance else "white"
                summary_text.append(f"{equity:.2f} USDT", style=equity_color)

                panel = Panel(summary_text, title="[bold cyan]positionstatistics[/bold cyan]", border_style="cyan")
                self.console.print("\n", panel)

            # Display overall summary
            total_positions = sum(item['summary']['total_positions'] for item in traders_with_positions)
            total_open = sum(item['summary']['open_positions'] for item in traders_with_positions)
            total_closed = sum(item['summary']['closed_positions'] for item in traders_with_positions)
            total_liquidated = sum(item['summary']['liquidated_positions'] for item in traders_with_positions)
            total_unrealized_pnl = sum(item['summary']['total_unrealized_pnl'] for item in traders_with_positions)
            total_realized_pnl = sum(item['summary']['total_realized_pnl'] for item in traders_with_positions)

            overall_text = RichText()
            overall_text.append(f"tradertotalnumber: {len(traders)}\n", style="cyan")
            overall_text.append(f"Total positionsnumber: {total_positions}\n", style="white")
            overall_text.append(f"Open: {total_open}\n", style="green")
            overall_text.append(f"has beenclose: {total_closed}\n", style="yellow")
            overall_text.append(f"Liquidated: {total_liquidated}\n", style="red")
            overall_text.append(f"\ntotalUnrealized P&L: ", style="white")
            overall_text.append(f"{total_unrealized_pnl:+.2f} USDT\n",
                             style="green" if total_unrealized_pnl > 0 else "red")
            overall_text.append(f"totalRealized P&L: ", style="white")
            overall_text.append(f"{total_realized_pnl:+.2f} USDT\n",
                             style="green" if total_realized_pnl > 0 else "red")

            overall_panel = Panel(overall_text, title="[bold yellow]totalbodystatistics[/bold yellow]", border_style="yellow")
            self.console.print("\n", overall_panel)

        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
        finally:
            pos_db.close()
            trader_db.close()

    async def _handle_optimize_command(self, args: list):
        """Handle the /optimize command - AI self-optimization based on trading history

        Analyzes trader's historical performance and suggests/updates strategy improvements.

        Args:
            args: Command arguments (trader_id)
        """
        import os
        import subprocess

        # Parse trader_id
        if not args:
            self.console.print("[red]Error: pleasespecifyTrader ID[/red]")
            self.console.print("[yellow]Usage: /optimize <trader_id>[/yellow]")
            return

        trader_id = args[0]

        # Initialize databases
        trader_db = TraderDatabase()
        trader_db.initialize()
        pos_db = PositionDatabase()
        pos_db.initialize()

        try:
            # Get trader info
            trader = trader_db.get_trader(trader_id)
            if not trader:
                self.console.print(f"[yellow]Trader with ID '{trader_id}' not found[/yellow]")
                return

            # Get trader file path
            trader_file = trader.get('trader_file', '')
            if not trader_file or not os.path.exists(trader_file):
                self.console.print(f"[red]Error: Trader file not found {trader_file}[/red]")
                return

            # Get position history
            positions_summary = pos_db.get_trader_positions_summary(trader_id)
            all_positions = pos_db.list_positions(trader_id)

            # Show trader info
            chars = trader.get('characteristics', {})
            name = chars.get('name', 'N/A')
            style = trader.get('style', 'N/A').replace('_', ' ').title()
            current_balance = trader.get('current_balance', 0)
            initial_balance = trader.get('initial_balance', 0)

            self.console.print(f"\n[bold cyan]Nowoptimizetrader:[/bold cyan]")
            self.console.print(f"  [dim]ID:[/dim] {trader_id}")
            self.console.print(f"  [dim]Name:[/dim] {name}")
            self.console.print(f"  [dim]Style:[/dim] {style}")
            self.console.print(f"  [dim]File:[/dim] {trader_file}\n")

            # Display current performance summary
            from rich.panel import Panel
            from rich.text import Text

            perf_text = Text()
            perf_text.append(f"initialstartbalance: {initial_balance:.2f} USDT\n", style="white")
            perf_text.append(f"whenfirstbalance: {current_balance:.2f} USDT\n", style="cyan")
            total_pnl = current_balance - initial_balance
            perf_text.append(f"totalP&L: {total_pnl:+.2f} USDT", style="green" if total_pnl >= 0 else "red")

            if total_pnl != 0:
                roi = (total_pnl / initial_balance) * 100
                perf_text.append(f" ({roi:+.2f}%)\n", style="green" if total_pnl >= 0 else "red")
            else:
                perf_text.append("\n")

            perf_text.append(f"Total positions: {positions_summary['total_positions']}\n", style="white")
            perf_text.append(f"has beenclose: {positions_summary['closed_positions']}\n", style="yellow")
            perf_text.append(f"Liquidated: {positions_summary['liquidated_positions']}\n", style="red")
            perf_text.append(f"AverageROI: {positions_summary['average_roi']:.2f}%\n", style="cyan")

            perf_panel = Panel(perf_text, title="[bold yellow]Performance Statistics[/bold yellow]", border_style="yellow")
            self.console.print(perf_panel)

            # Check if there's enough data to optimize
            if positions_summary['total_positions'] == 0:
                self.console.print("[yellow]thistraderstillNotradeeasyrecords，Cannotenterwalkoptimizeanalyze[/yellow]")
                self.console.print("[dim]buildproposalfirstUse /decide commandenterwalkonesometradeeasy，accumulateaccumulatehistoryhistorydataafteragainenterwalkoptimize[/dim]")
                return

            # Find Claude Code executable
            claude_path = shutil.which("claude")
            if not claude_path:
                self.console.print("[red]Error: notfound Claude Code canexecuteFile[/red]")
                self.console.print("[yellow]Please visit https://code.claude.com install Claude Code[/yellow]")
                return

            # Store file modification time
            mtime_before = os.path.getmtime(trader_file)

            # Build position history data for analysis
            position_details = []
            for pos in all_positions:
                detail = {
                    'symbol': pos.symbol,
                    'side': pos.position_side.value,
                    'status': pos.status.value,
                    'entry_price': pos.entry_price,
                    'exit_price': pos.exit_price,
                    'realized_pnl': pos.realized_pnl,
                    'roi': pos.roi,
                    'leverage': pos.leverage,
                    'entry_time': pos.entry_time.isoformat() if pos.entry_time else None,
                    'exit_time': pos.exit_time.isoformat() if pos.exit_time else None,
                }
                position_details.append(detail)

            # Convert to readable format for Claude
            import json
            positions_json = json.dumps(position_details, indent=2, ensure_ascii=False)

            # Prepare comprehensive optimization instructions
            instructions = f"""You are performing a self-optimization analysis for a cryptocurrency trader. Your goal is to analyze their historical performance and suggest/apply improvements to their trading strategy.

**STEP 1: Read and Understand**

Read the TRADERS.md file in the parent directory to understand the trader profile template.

Read the current trader profile.md file in the current directory.

**STEP 2: Analyze Performance Data**

Trader Information:
- ID: {trader_id}
- Name: {name}
- Style: {style}
- Initial Balance: {initial_balance:.2f} USDT
- Current Balance: {current_balance:.2f} USDT
- Total PnL: {total_pnl:+.2f} USDT ({(total_pnl/initial_balance)*100:+.2f}%)

Position Summary:
- Total Positions: {positions_summary['total_positions']}
- Closed: {positions_summary['closed_positions']}
- Liquidated: {positions_summary['liquidated_positions']}
- Average ROI: {positions_summary['average_roi']:.2f}%

Complete Position History:
{positions_json}

**STEP 3: Analysis and Optimization**

Analyze the trading performance and identify:
1. **Win/Loss Patterns**: Which trades succeeded? Which failed? Why?
2. **Risk Management**: Are stop losses effective? Is position sizing appropriate?
3. **Market Conditions**: How does the trader perform in different market regimes?
4. **Strategy Effectiveness**: Which aspects of the strategy work? Which don't?
5. **Leverage Usage**: Is leverage being used responsibly?

**STEP 4: Apply Optimizations**

If you identify areas for improvement, modify the profile.md file:

1. **Keep the same structure** - Maintain all sections from TRADERS.md
2. **Keep the same ID** -Trader ID must remain {trader_id}
3. **Adjust strategy parameters** based on your analysis:
   - Risk tolerance and position sizing
   - Stop loss and take profit levels
   - Leverage limits
   - Trading pair selection
   - Indicator parameters
   - Timeframe preferences

4. **Add lessons learned** in the "Performance Notes" or "Strategy" section

5. **Document changes** - If you make changes, explain WHY in the profile

**STEP 5: Decision**

After your analysis:
- If performance is good with clear strengths: Make minor tweaks or add positive reinforcement notes
- If there are clear issues: Modify the strategy to address them
- If there's insufficient data: Add notes about what data to collect

**IMPORTANT:**
- ONLY modify profile.md if you have a clear, data-driven reason
- Preserve the trader's core identity (name, basic style)
- Focus on parameter tuning and risk management improvements
- Save your changes to profile.md in the current directory

Begin your optimization analysis now."""

            self.console.print("[cyan]Nowcalling Claude Code enterwalkselfIoptimizeanalyze...[/cyan]\n")

            try:
                # Run Claude Code as subprocess with real-time output
                self.console.print("[dim]Claude Code Nowanalyzehistoryhistorydata...[/dim]\n")

                process = subprocess.Popen(
                    [claude_path, "--print", instructions],
                    cwd=str(os.path.dirname(trader_file)),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )

                # Stream output in real-time
                output_lines = []
                try:
                    for line in process.stdout:
                        output_lines.append(line.rstrip())
                        self.console.print(f"[dim]{line.rstrip()}[/dim]")
                except Exception as e:
                    process.kill()
                    raise e

                # Wait for process to complete
                try:
                    return_code = process.wait(timeout=300)
                except subprocess.TimeoutExpired:
                    process.kill()
                    self.console.print("[red]Error: Claude Code Execution timeout（5minutes）[/red]")
                    return

                # Check if file was modified
                mtime_after = os.path.getmtime(trader_file)

                if mtime_after == mtime_before:
                    self.console.print("\n[yellow]analyzecompleted，profileNoneedmodify[/yellow]")
                    self.console.print("[dim]Trader performance statistics[/dim]")
                else:
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
                    success = trader_db.update_trader(trader_id, update_record)

                    if success:
                        self.console.print("\n[green]✓traderprofilehas beenoptimizeandmorenew[/green]")
                        self.console.print(f"[dim]datalibraryrecordshas beensync[/dim]")
                    else:
                        self.console.print("\n[yellow]Warning: Filehas beenmodify，butdatalibrarymorenewfailed[/yellow]")

            except subprocess.TimeoutExpired:
                self.console.print("[red]Error: Claude Code Execution timeout (5minutes)[/red]")
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")
                import traceback
                self.console.print(f"[dim]{traceback.format_exc()}[/dim]")

        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
        finally:
            trader_db.close()
            pos_db.close()

    async def _handle_start_command(self, args: list):
        """startholdcontinuerunningmode

        Args:
            args: [trader_id1, trader_id2, ...] orempty（startall trader）
        """
        # confirmensuredatalibraryhas beeninitialstartchange
        if not hasattr(self, 'trader_db') or self.trader_db is None:
            self.trader_db = TraderDatabase()
            self.trader_db.initialize()

        if not hasattr(self, 'pos_db') or self.pos_db is None:
            self.pos_db = PositionDatabase()
            self.pos_db.initialize()

        # fetchwantadjustdegree of trader ID List
        trader_ids = args if args else None

        # createscheduler（passpassdatalibraryactualexample）
        if not hasattr(self, 'scheduler') or self.scheduler is None:
            from .scheduler import TraderScheduler
            self.scheduler = TraderScheduler(self, self.trader_db, self.pos_db)

        # Start scheduler and actual time instruments table (will block, press Ctrl+C to exit)
        await self.scheduler.start(trader_ids)

        # Instruments table exits, return to REPL

    async def _handle_stop_command(self, args: list):
        """stopstopholdcontinuerunningmode"""
        if not hasattr(self, 'scheduler') or not self.scheduler.running:
            print("schedulernotrunning")
            return

        await self.scheduler.stop()

    async def _handle_status_command(self, args: list):
        """displayschedulerstatus"""
        if not hasattr(self, 'scheduler') or not self.scheduler.running:
            self.console.print("[dim]schedulernotrunning[/dim]")
            self.console.print("[dim]hint: Use /start [trader_ids] startscheduler[/dim]")
            return

        from rich.table import Table
        from rich.panel import Panel

        status = self.scheduler.get_status()

        # totalbodystatusfaceboard
        status_text = f"""
[bold cyan]schedulerstatus[/bold cyan]

runningstatus: [{'green' if status['running'] else 'red'}]{'runningin' if status['running'] else 'has beenstopstop'}[/]
monitorcontrol Trader: {status['total_traders']} (active: {status['enabled_traders']})
queuetask: {status['queue_size']}
"""
        self.console.print(Panel(status_text.strip(), border_style="cyan"))

        # displayqueueextractwant
        queue_summary = status.get('queue_summary', {})
        if queue_summary.get('total_tasks', 0) > 0:
            by_action = queue_summary.get('tasks_by_action', {})
            self.console.print(f"[dim]queuein oftask: {queue_summary['total_tasks']}[/dim]")
            for action, count in by_action.items():
                if count > 0:
                    self.console.print(f"  [dim]- {action}: {count}[/dim]")

        # Trader statustable
        if status['traders']:
            table = Table(title="\n[bold]Trader adjustdegreestatus[/bold]")
            table.add_column("Trader ID", style="cyan")
            table.add_column("status", justify="center")
            table.add_column("last triggered", style="dim")
            table.add_column("triggersendtimenumber", justify="right")
            table.add_column("processingin", justify="center")

            for t in status['traders']:
                trader_id = t['trader_id']
                enabled = t['enabled']
                last_trigger = t['last_trigger']
                total_triggers = t['total_triggers']
                processing = t['processing']

                # statusdisplay
                status_str = "[green]✓[/green]" if enabled else "[red]✗[/red]"

                # last triggeredtime
                if last_trigger:
                    last_str = last_trigger.strftime("%H:%M:%S")
                else:
                    last_str = "-"

                # processinginmarkrecord
                proc_str = "[yellow]is[/yellow]" if processing else ""

                table.add_row(trader_id, status_str, last_str, str(total_triggers), proc_str)

            self.console.print(table)

    async def _handle_config_command(self, args: list):
        """viewormodifyconfiguration

        Args:
            args: [key] [value] or 'list' or 'reset'
        """
        from .scheduler_config import get_scheduler_config

        config = get_scheduler_config()

        if not args:
            # displayallconfiguration
            self._show_all_config(config)
            return

        if args[0] == 'list':
            # listoutallconfiguration
            self._show_all_config(config)

        elif args[0] == 'reset':
            # reset to default
            from rich.prompt import Confirm
            if await self._confirm_async("confirmconfirmwantrepeatplaceallconfigurationasdefault valuequestion？"):
                config.reset_to_defaults()
                self.console.print("[green]✓ configurationhas beenreset to default[/green]")

        elif len(args) == 1:
            # displaysingletradersconfiguration
            key = args[0]
            value = config.get(key)
            if value is None:
                self.console.print(f"[red]notfoundconfiguration: {key}[/red]")
            else:
                all_config = config.get_all()
                info = all_config.get(key, {})
                self.console.print(f"[cyan]{key}[/cyan] = {value}")
                if info.get('description'):
                    self.console.print(f"[dim]type: {info['type']}[/dim]")
                    self.console.print(f"[dim]description: {info['description']}[/dim]")

        elif len(args) >= 2:
            # setconfiguration
            key = args[0]
            value_str = ' '.join(args[1:])

            # trytryparsevalue
            try:
                # trytrydistributeervalue
                if value_str.lower() in ('true', 'false'):
                    value = value_str.lower() == 'true'
                # trytrynumber
                elif '.' in value_str:
                    value = float(value_str)
                else:
                    value = int(value_str)

                config.set(key, value)
                self.console.print(f"[green]✓ has beenset: {key} = {value}[/green]")

            except ValueError:
                # workascharacterstringprocessing
                config.set(key, value_str)
                self.console.print(f"[green]✓ has beenset: {key} = {value_str}[/green]")

    def _show_all_config(self, config):
        """displayallconfiguration

        Args:
            config: SchedulerConfig instance
        """
        from rich.table import Table

        all_config = config.get_all()

        table = Table(title="[bold cyan]schedulerconfiguration[/bold cyan]")
        table.add_column("configurationkey", style="cyan")
        table.add_column("value", style="yellow")
        table.add_column("type", style="dim")
        table.add_column("description", style="dim")

        # dividegroupdisplay
        groups = {
            'scheduler': 'scheduler',
            'trigger.time': 'timetriggersend',
            'trigger.price': 'pricetriggersend',
            'indicator': 'indicator',
            'optimize': 'optimize',
            'priority': 'optimizefirstlevel'
        }

        # pressdividegrouproworder
        sorted_keys = sorted(all_config.keys(), key=lambda k: (
            list(groups.keys()).index(k.split('.')[0]) if k.split('.')[0] in groups else 999,
            k
        ))

        current_group = None
        for key in sorted_keys:
            info = all_config[key]
            group_key = key.split('.')[0] if '.' in key else key

            # adddividegroupmarkquestionwalk
            if group_key in groups and group_key != current_group:
                table.add_row("", "", "", "")
                table.add_row(f"[bold]{groups[group_key]}[/bold]", "", "", "")
                current_group = group_key

            value_str = str(info['value'])
            if len(value_str) > 30:
                value_str = value_str[:27] + "..."

            table.add_row(
                key,
                value_str,
                info['type'],
                info.get('description', '')[:50]
            )

        self.console.print(table)

    async def _confirm_async(self, message: str) -> bool:
        """differentstepconfirmconfirmhint

        Args:
            message: confirmconfirmcancelinformation

        Returns:
            True if confirmed
        """
        from rich.prompt import Confirm

        # in async context inUsesync prompt
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: Confirm.ask(message))

    async def run(self):
        """running CLI mainloopenvironment"""
        self._print_banner()

        while True:
            try:
                with patch_stdout():
                    cmd = await self.session.prompt_async(
                        "cryptobot>",
                    )

                # parseandprocessingcommand
                command, args = self._parse_command(cmd)

                if not command:
                    continue

                if command in ("/quit", "/exit", "quit", "exit"):
                    self.console.print("[yellow]Goodbye！[/yellow]")
                    break

                elif command == "/help":
                    self._print_help()

                elif command == "/market":
                    await self._handle_rest_command(args)

                elif command == "/pairs":
                    await self._handle_pairs_command(args)

                elif command == "/intervals":
                    await self._handle_intervals_command(args)

                elif command == "/traders":
                    await self._handle_traders_command(args)

                elif command == "/indicators":
                    await self._handle_indicators_command(args)

                elif command == "/decide":
                    await self._handle_decide_command(args)

                elif command == "/positions":
                    await self._handle_positions_command(args)

                elif command == "/optimize":
                    await self._handle_optimize_command(args)

                elif command == "/start":
                    await self._handle_start_command(args)

                elif command == "/stop":
                    await self._handle_stop_command(args)

                elif command == "/status":
                    await self._handle_status_command(args)

                elif command == "/config":
                    await self._handle_config_command(args)

                else:
                    self.console.print(
                        f"[red]notknowcommand: {command}. outputenter /help viewhelphelp[/red]"
                    )

            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[yellow]Goodbye！[/yellow]")
                break
            except Exception as e:
                # Use Text comeavoidavoidparseexceptioncancelinformationin of Rich marksign
                from rich.text import Text
                error_text = Text()
                error_text.append("Error: ", style="red")
                error_text.append(str(e))
                self.console.print(error_text)
