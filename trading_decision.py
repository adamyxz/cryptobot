#!/usr/bin/env python3
"""Trading Decision Execution Script for Trader 12"""

import asyncio
import sys
from datetime import datetime

# Add the cryptobot package to the path
sys.path.insert(0, '/Users/yxz/dev/cryptobot')

from cryptobot.trading_tools import TradingTools
from cryptobot.scheduler_config import get_scheduler_config


async def main():
    from rich.console import Console
    from cryptobot.position_db import PositionDatabase
    from cryptobot.trader_db import TraderDatabase

    console = Console()
    config = get_scheduler_config()

    # Initialize databases
    position_db = PositionDatabase()
    trader_db = TraderDatabase()

    # Initialize trading tools
    tools = TradingTools(console, position_db, trader_db)

    # Market Analysis
    """
    MARKET DATA ANALYSIS:

    Price Action (ETHUSDT):
    - Recent price range: $2353.67 - $2260.09 (last ~40 periods)
    - Current price: ~$2284 (most recent close)
    - Recent trend: Strong bearish downtrend

    Key Observations:
    1. Persistent downtrend from $2353 high to $2260 low (~4% decline)
    2. Multiple consecutive red candles with no reversal
    3. Lower lows and lower highs pattern
    4. Volume spikes during sell-offs confirm bearish momentum
    5. Weak bounce from $2260 support suggests more downside

    Funding Rate Analysis:
    - Recent funding rates negative: -0.010402, -0.011239, -0.000368
    - Negative funding confirms short dominance
    - Aligns with bearish price action

    Long/Short Ratio:
    - All data shows 0.0 (unreliable)

    Current Positions:
    - ETHUSDT: Entry $2278.65, Unrealized P&L: -$15.92 (underwater)
    - BTCUSDT: Entry $78070.1, Unrealized P&L: -$1.01 (breakeven)
    - Total Unrealized: -$16.93

    DECISION: CLOSE ALL POSITIONS + OPEN SHORT
    Reasoning:
    1. Strong bearish trend continues with no reversal signal
    2. Current ETH position is underwater - cut losses early
    3. Negative funding rates support short positioning
    4. Open new short to capitalize on continued downward momentum
    5. Risk/Reward: Tight stop above $2300, target $2250
    """

    trader_id = "12"
    exchange = config.get_string('indicator.exchange', 'okx')
    balance = 7634.69

    console.print("\n[bold cyan]=== TRADING DECISION: TRADER 12 ===[/bold cyan]")
    console.print(f"[dim]Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]")
    console.print(f"[dim]Exchange: {exchange}[/dim]")
    console.print(f"[dim]Balance: ${balance:.2f}[/dim]")
    console.print("")
    console.print("[yellow]ANALYSIS:[/yellow]")
    console.print("  - ETH showing strong bearish downtrend ($2353 -> $2284)")
    console.print("  - Multiple lower lows with no reversal signal")
    console.print("  - Negative funding rates confirm short dominance")
    console.print("  - Current ETH position underwater (-$15.92)")
    console.print("  - Volume spikes during sell-offs confirm momentum")
    console.print("")
    console.print("[yellow]ACTION:[/yellow]")
    console.print("  Step 1: Close all existing positions")
    console.print("  Step 2: Open new SHORT position on ETHUSDT")
    console.print("")
    console.print("[green]NEW POSITION DETAILS:[/green]")

    # Position sizing: 4.5% of balance = ~$343
    # At $2280, that's approximately 0.15 ETH
    size = 0.15
    leverage = 5

    console.print(f"  Symbol: ETHUSDT")
    console.print(f"  Side: SHORT")
    console.print(f"  Size: {size} ETH")
    console.print(f"  Leverage: {leverage}x")
    console.print(f"  Position Value: ~${size * 2280:.2f}")
    console.print("")

    # Step 1: Close all positions
    console.print("[yellow]Step 1: Closing all positions...[/yellow]")
    close_result = await tools.close_all_positions(trader_id=trader_id)
    console.print(f"  {close_result.message}")
    console.print("")

    # Step 2: Open new short position
    console.print("[yellow]Step 2: Opening new SHORT position...[/yellow]")
    result = await tools.open_position(
        trader_id=trader_id,
        exchange=exchange,
        symbol="ETHUSDT",
        side="short",
        size=size,
        leverage=leverage
    )

    console.print("")
    console.print("[bold]" + "="*50 + "[/bold]")
    console.print(f"[bold]RESULT:[/bold] {result.message}")
    if result.success:
        console.print(f"[green]✓ Position ID: {result.position_id}[/green]")
        console.print(f"[green]✓ Entry Price: ${result.entry_price:.2f}[/green]")
        console.print(f"[green]✓ Margin: ${result.margin:.2f}[/green]")
    else:
        console.print(f"[red]✗ Error: {result.error}[/red]")


if __name__ == "__main__":
    asyncio.run(main())
