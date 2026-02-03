# CryptoBot

A modern cryptocurrency trading CLI tool for perpetual futures with AI-powered strategy generation, position management, and automated scheduling.

## Features

- **Multi-Exchange Support**: Binance, OKX, Bybit, Bitget via CCXT
- **Perpetual Futures Focus**: Full support for leverage, long/short positions, funding rates
- **AI-Powered Trader Generation**: Create unique, diverse trading strategy profiles
- **Position Management**: Full lifecycle management with P&L tracking
- **Automated Scheduling**: Run multiple traders with configurable monitoring intervals
- **Liquidation Monitoring**: Real-time alerts for position liquidation events
- **Indicator System**: Modular market data collection with CSV output
- **Rich Visualizations**: Beautiful terminal charts and tables

## Installation

```bash
# Clone the repository
git clone https://github.com/adamyxz/cryptobot.git
cd cryptobot

# Install with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

## Quick Start

```bash
# Start the CLI
python -m cryptobot

# Or using the installed command
cryptobot
```

## Commands

### Core Commands

| Command | Description |
|---------|-------------|
| `/start [trader_ids...]` | Start automated scheduler (optionally specify traders) |
| `/stop` | Stop the scheduler |
| `/status` | View scheduler status and active positions |
| `/config [key] [value]` | View/modify configuration |

### Market Data

| Command | Description |
|---------|-------------|
| `/market [exchange] [symbol] [interval] [limit]` | Get historical K-line data |
| `/pairs [exchange]` | List available perpetual futures pairs |
| `/intervals` | Show supported time intervals |

### Trader Management

| Command | Description |
|---------|-------------|
| `/traders -a [prompt] [-t <count>]` | Generate new AI trader profile(s) |
| `/traders [trader_id ...]` | View trader profiles |
| `/traders <id> -m <prompt>` | Modify existing trader |
| `/traders <id> -d` | Delete trader profile |
| `/decide <trader_id>` | Get AI trading decision for a trader |

### Position Management

| Command | Description |
|---------|-------------|
| `/positions [trader_id|position_id]` | View positions |
| `/positions <trader_id> -o <params>` | Open new position |
| `/positions <position_id> -c [price]` | Close position |

### Indicator System

| Command | Description |
|---------|-------------|
| `/indicators -a <prompt>` | Generate new indicator script |
| `/indicators [filename]` | View indicator code |
| `/indicators <name> -d` | Delete indicator |
| `/indicators <name> -t <args...>` | Test indicator |
| `/indicators <name> -m <prompt>` | Modify indicator |

### Other

| Command | Description |
|---------|-------------|
| `/optimize <trader_id>` | AI self-optimization for trader |
| `/help` | Show detailed help |
| `/quit` or `/exit` | Exit program |

## Examples

```bash
# Start scheduler with specific traders
/start 1 2 3

# Get market data
/market okx ETHUSDT 1h 100

# Generate a new aggressive scalper trader
/traders -a Create an aggressive scalper focusing on BTC with high frequency

# Get AI decision for trader #5
/decide 5

# Open a long position
/positions 5 -o symbol=BTCUSDT side=long entry=45000 quantity=0.1 leverage=2

# Generate a funding rate indicator
/indicators -a Create an indicator that fetches funding rate history

# View all positions
/positions
```

## Supported Exchanges

| Exchange | CCXT Class | Market Type |
|----------|------------|-------------|
| Binance | `binanceusdm` | Perpetual Futures |
| OKX | `okx` | Perpetual Swaps |
| Bybit | `bybit` | Derivatives |
| Bitget | `bitget` | Futures |

## Supported Intervals

- **Minutes**: `1m`, `3m`, `5m`, `15m`, `30m`
- **Hours**: `1h`, `2h`, `4h`, `6h`, `12h`
- **Days/Weeks/Months**: `1d`, `1w`, `1M`

## Project Structure

```
cryptobot/
├── cryptobot/              # Main package
│   ├── __init__.py
│   ├── __main__.py         # Entry point
│   ├── cli.py              # CLI core logic
│   ├── ccxt_adapter.py     # CCXT integration
│   ├── display.py          # Visualization
│   ├── exchanges.py        # Exchange interface
│   ├── trader_db.py        # Trader profile database
│   ├── position_db.py      # Position database
│   ├── position.py         # Position models
│   ├── fees.py             # Fee calculation
│   ├── scheduler.py        # Task scheduler
│   ├── scheduler_config.py # Scheduler configuration
│   ├── scheduler_dashboard.py # Scheduler UI
│   ├── trading_tools.py    # Trading utilities
│   ├── activity_log_db.py  # Activity logging
│   ├── liquidation_monitor.py # Liquidation monitoring
│   ├── price_service.py    # Real-time price service
│   ├── priority_queue.py   # Priority queue
│   └── triggers/           # Trigger system
│       ├── base.py
│       ├── price_trigger.py
│       ├── time_trigger.py
│       └── trigger_manager.py
├── indicators/             # Indicator scripts
│   ├── __init__.py
│   ├── base.py
│   ├── fetch_open_interest.py
│   ├── fetch_orderbook.py
│   ├── fundingratehistory.py
│   ├── longshortratio.py
│   ├── market_data.py
│   └── INDICATORS.md       # Indicator development guide
├── traders/                # Trader profiles (gitignored)
│   └── TRADERS.md          # Trader generation guide
├── main.py                 # Alternative entry point
├── pyproject.toml          # Project configuration
└── README.md              # This file
```

## Configuration

Configuration is stored in `~/.cryptobot/config.json`:

```json
{
  "scheduler": {
    "check_interval_minutes": 5,
    "decide_command": "/decide {trader_id}"
  },
  "indicator": {
    "exchange": "okx",
    "symbol": "BTCUSDT",
    "interval": "1m",
    "limit": 100
  }
}
```

Modify using `/config <key> <value>` in the CLI.

## Trader System

Traders are AI-generated strategy profiles that define:
- Entry/exit conditions
- Risk management rules
- Position sizing and leverage
- Asset preferences and timeframes
- Trading philosophy and psychology

All traders support **perpetual futures** with both LONG and SHORT positions.

### Creating Traders

```bash
# Generate a single trader
/traders -a Create a momentum-based day trader for altcoins

# Generate multiple traders at once
/traders -a Generate diverse arbitrage strategies -t 3
```

## Position Management

Positions include full lifecycle tracking:
- Real-time P&L calculation
- Liquidation monitoring with alerts
- Funding rate tracking
- Fee calculation
- Status management (OPEN, CLOSED, LIQUIDATED)

## Indicator System

Indicators are modular Python scripts that fetch market data in CSV format. They are used by the `/decide` command to gather additional context for AI decision-making.

See `indicators/INDICATORS.md` for detailed development guidelines.

## Requirements

- Python 3.14+
- ccxt >= 4.0.0
- prompt-toolkit >= 3.0.47
- rich >= 13.7.1

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues and questions, please open an issue on the GitHub repository.
