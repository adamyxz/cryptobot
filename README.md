# CryptoBot

A modern cryptocurrency trading CLI tool for accessing perpetual futures (perpetual swaps) market data from multiple exchanges using CCXT.

## Features

- **Historical Data**: REST API access to historical candlestick data
- **Multiple Exchanges**: Support for Binance, OKX, Bybit, and Bitget
- **Perpetual Futures**: Focus on perpetual swap markets (not spot)
- **Rich Visualizations**: Beautiful terminal charts and tables
- **Trader Management**: AI-powered trading strategy profile generation

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd cryptobot

# Install dependencies
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

### Data Commands

- `/rest [exchange] [symbol] [interval] [limit]` - Fetch historical K-line data (REST API)
- `/pairs [exchange]` - List available perpetual futures trading pairs
- `/intervals` - Show supported time intervals

### Trader Commands

- `/traders [id] [prompt]` - View/modify trader profiles
- `/traders [id] -d` - Delete a trader profile
- `/newtrader [prompt]` - Generate new AI-powered trader profile

### System Commands

- `/help` - Show help information
- `/quit` or `/exit` - Exit the program

## Examples

```bash
# Get historical data for BTCUSDT on Binance (default: 30 candles)
/rest

# Get historical data for ETHUSDT on OKX (100 candles)
/rest okx ETHUSDT 1h 100

# Show all perpetual futures pairs on Bitget
/pairs bitget
```

## Supported Exchanges

| Exchange | CCXT Class | Market Type | Example Symbol |
|----------|------------|-------------|----------------|
| Binance | `binanceusdm` | Perpetual Futures | `BTCUSDT` |
| OKX | `okx` | Perpetual Swaps | `BTCUSDT` |
| Bybit | `bybit` | Derivatives | `BTCUSDT` |
| Bitget | `bitget` | Futures | `BTCUSDT` |

## Supported Intervals

- **Minutes**: `1m`, `3m`, `5m`, `15m`, `30m`
- **Hours**: `1h`, `2h`, `4h`, `6h`, `12h`
- **Days/Weeks/Months**: `1d`, `1w`, `1M`

## Data Source

All market data is sourced from **perpetual futures** (perpetual swaps) markets, not spot markets. This provides:

- Higher liquidity
- Lower spreads
- Better for short-term trading strategies
- Access to advanced order types

## Architecture

The CLI is built on top of:

- **CCXT**: Unified cryptocurrency exchange API
- **Rich**: Terminal formatting and visualization
- **Prompt Toolkit**: Interactive command-line interface

## Project Structure

```
cryptobot/
├── cryptobot/
│   ├── __init__.py
│   ├── cli.py              # Main CLI logic
│   ├── exchanges.py        # Exchange interface (legacy compatibility)
│   ├── ccxt_adapter.py     # CCXT integration module
│   ├── display.py          # Visualization layer
│   └── trader_db.py        # Trader profile database
├── traders/                # Trader profile storage
│   ├── TRADERS.md          # Trader profile template
│   ├── TraderName_1/       # Individual trader folder
│   │   └── profile.md      # Trader profile document
│   └── TraderName_2/       # Another trader
│       └── profile.md
├── tests/                  # Test suite
├── pyproject.toml          # Project configuration
└── README.md              # This file
```

## Configuration

No configuration file required. The CLI uses sensible defaults:

- Default exchange: `binance`
- Default symbol: `BTCUSDT`
- Default interval: `1m`

## Requirements

- Python 3.14+
- ccxt >= 4.0.0
- prompt-toolkit >= 3.0.47
- rich >= 13.7.1

## License

[Add your license here]

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Migration Notes

This project has been migrated from direct exchange APIs to CCXT. See `MIGRATION_SUMMARY.md` for detailed information about the migration.

## Support

For issues and questions, please open an issue on the GitHub repository.
