"""Trading Tools for AI

Provides function-based tools that AI can call directly to execute trading actions.
This is more reliable than parsing text-based decisions.
"""

from typing import Optional, Literal, Dict, Any
from datetime import datetime
from dataclasses import dataclass
import asyncio


@dataclass
class PositionResult:
    """Result of a position operation"""
    success: bool
    message: str
    position_id: Optional[int] = None
    trader_id: Optional[str] = None
    exchange: Optional[str] = None
    symbol: Optional[str] = None
    side: Optional[str] = None
    size: Optional[float] = None
    entry_price: Optional[float] = None
    leverage: Optional[float] = None
    margin: Optional[float] = None
    pnl: Optional[float] = None
    error: Optional[str] = None


class TradingTools:
    """Trading tools that AI can call directly

    This class provides methods for AI to execute trading actions.
    Each method validates parameters and returns structured results.
    """

    def __init__(self, console, position_db, trader_db):
        """Initialize trading tools

        Args:
            console: Rich console for output
            position_db: PositionDatabase instance
            trader_db: TraderDatabase instance
        """
        self.console = console
        self.position_db = position_db
        self.trader_db = trader_db

    async def open_position(
        self,
        trader_id: str,
        exchange: str,
        symbol: str,
        side: Literal["long", "short"],
        size: float,
        leverage: Optional[float] = None
    ) -> PositionResult:
        """Open a new trading position

        Args:
            trader_id: Trader ID
            exchange: Exchange name (binance, okx, bybit, bitget)
            symbol: Trading pair symbol (e.g., BTCUSDT, ETHUSDT)
            side: Position side - "long" or "short"
            size: Position size in base currency (e.g., 0.1 for BTC)
            leverage: Optional leverage multiplier (e.g., 5 for 5x). Defaults to 1.

        Returns:
            PositionResult with operation details
        """
        from .exchanges import get_exchange_config
        from .price_service import get_price_service
        from .fees import calculate_fee
        from .position import Position, PositionSide, PositionStatus

        # Validate inputs
        if side not in ("long", "short"):
            return PositionResult(
                success=False,
                message=f"Invalid side: {side}. Must be 'long' or 'short'",
                error=f"INVALID_SIDE: {side}"
            )

        if size <= 0:
            return PositionResult(
                success=False,
                message=f"Size must be positive: {size}",
                error=f"INVALID_SIZE: {size}"
            )

        if leverage is not None and leverage <= 0:
            return PositionResult(
                success=False,
                message=f"Leverage must be positive: {leverage}",
                error=f"INVALID_LEVERAGE: {leverage}"
            )

        if leverage is None:
            leverage = 1.0

        # Validate exchange
        try:
            get_exchange_config(exchange)
        except ValueError as e:
            return PositionResult(
                success=False,
                message=f"Invalid exchange: {e}",
                error=str(e)
            )

        # Verify trader exists
        trader = self.trader_db.get_trader(trader_id)
        if not trader:
            return PositionResult(
                success=False,
                message=f"Trader not found: {trader_id}",
                error=f"TRADER_NOT_FOUND: {trader_id}"
            )

        # Fetch current price
        try:
            price_service = get_price_service()
            entry_price = await price_service.fetch_current_price(exchange, symbol)
        except Exception as e:
            return PositionResult(
                success=False,
                message=f"Failed to fetch price for {exchange} {symbol}: {e}",
                error=f"PRICE_FETCH_ERROR: {e}"
            )

        # Calculate fee
        try:
            entry_fee = calculate_fee(exchange, size, entry_price)
        except Exception as e:
            return PositionResult(
                success=False,
                message=f"Failed to calculate fee: {e}",
                error=f"FEE_CALCULATION_ERROR: {e}"
            )

        # Calculate margin
        margin = (size * entry_price) / leverage

        # Check balance
        required_margin = margin + entry_fee
        current_balance = trader.get('current_balance', 0)

        if current_balance < required_margin:
            return PositionResult(
                success=False,
                message=f"Insufficient balance: have ${current_balance:.2f}, need ${required_margin:.2f}",
                error=f"INSUFFICIENT_BALANCE: have ${current_balance:.2f}, need ${required_margin:.2f}"
            )

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
            unrealized_pnl=0.0,
        )

        # Calculate liquidation price
        position.liquidation_price = position.calculate_liquidation_price()

        try:
            # Save to database
            position_id = self.position_db.add_position(position)

            # Update trader balance
            balance_change = -(margin + entry_fee)
            self.trader_db.update_balance_and_equity(trader_id, balance_change=balance_change)

            self.console.print(f"[green]✓ Position opened via AI tool call[/green]")
            self.console.print(f"  [dim]ID: {position_id}[/dim]")
            self.console.print(f"  [dim]Trader: {trader_id}[/dim]")
            self.console.print(f"  [dim]{exchange} {symbol} {side} {size} @ {leverage}x[/dim]")

            return PositionResult(
                success=True,
                message=f"Opened {side} position: {exchange} {symbol} {size} @ {entry_price:.2f}",
                position_id=position_id,
                trader_id=trader_id,
                exchange=exchange,
                symbol=symbol,
                side=side,
                size=size,
                entry_price=entry_price,
                leverage=leverage,
                margin=margin
            )

        except Exception as e:
            return PositionResult(
                success=False,
                message=f"Failed to save position: {e}",
                error=f"DATABASE_ERROR: {e}"
            )

    async def close_position(
        self,
        position_id: int,
        price: Optional[float] = None
    ) -> PositionResult:
        """Close an existing position

        Args:
            position_id: Position ID to close
            price: Optional close price. If not provided, uses current market price

        Returns:
            PositionResult with operation details
        """
        from .price_service import get_price_service
        from .position import PositionStatus
        from .fees import calculate_fee

        # Get position
        position = self.position_db.get_position(position_id)
        if not position:
            return PositionResult(
                success=False,
                message=f"Position not found: {position_id}",
                error=f"POSITION_NOT_FOUND: {position_id}"
            )

        if position.status != PositionStatus.OPEN:
            return PositionResult(
                success=False,
                message=f"Position already closed: {position_id}",
                error=f"POSITION_ALREADY_CLOSED: {position_id}"
            )

        # Get close price
        if price is None:
            try:
                price_service = get_price_service()
                price = await price_service.fetch_current_price(position.exchange, position.symbol)
            except Exception as e:
                return PositionResult(
                    success=False,
                    message=f"Failed to fetch close price: {e}",
                    error=f"PRICE_FETCH_ERROR: {e}"
                )

        try:
            # Calculate exit fee
            exit_fee = calculate_fee(position.exchange, position.position_size, price)

            # Use position_db's close_position method to handle the closing
            success = self.position_db.close_position(position_id, price, exit_fee)

            if not success:
                return PositionResult(
                    success=False,
                    message=f"Failed to close position in database",
                    error=f"DATABASE_ERROR: close_position returned False"
                )

            # Get the updated position to retrieve PnL
            updated_position = self.position_db.get_position(position_id)
            pnl = updated_position.realized_pnl if updated_position else 0.0

            # Update trader balance and equity
            self.trader_db.update_balance_and_equity(
                position.trader_id,
                balance_change=position.margin + pnl,
                equity_change=pnl
            )

            self.console.print(f"[green]✓ Position closed via AI tool call[/green]")
            self.console.print(f"  [dim]ID: {position_id}[/dim]")
            self.console.print(f"  [dim]P&L: ${pnl:+.2f}[/dim]")

            return PositionResult(
                success=True,
                message=f"Closed position {position_id} at {price:.2f}, P&L: ${pnl:+.2f}",
                position_id=position_id,
                trader_id=position.trader_id,
                symbol=position.symbol,
                side=position.position_side.value,
                size=position.position_size,
                entry_price=position.entry_price,
                pnl=pnl,
                error=None
            )

        except ValueError as e:
            return PositionResult(
                success=False,
                message=f"Failed to close position: {e}",
                error=f"CLOSE_ERROR: {e}"
            )
        except Exception as e:
            return PositionResult(
                success=False,
                message=f"Failed to close position: {e}",
                error=f"CLOSE_ERROR: {e}"
            )

    async def close_all_positions(
        self,
        trader_id: str
    ) -> PositionResult:
        """Close all open positions for a trader

        Args:
            trader_id: Trader ID

        Returns:
            PositionResult with operation details
        """
        positions = self.position_db.list_positions(trader_id, status='open')

        if not positions:
            return PositionResult(
                success=True,
                message=f'No open positions for trader {trader_id}',
                trader_id=trader_id
            )

        closed_count = 0
        total_pnl = 0.0

        for pos in positions:
            result = await self.close_position(pos.id)
            if result.success:
                closed_count += 1
                # Extract PnL from result
                if result.pnl is not None:
                    total_pnl += result.pnl

        return PositionResult(
            success=True,
            message=f'Closed {closed_count}/{len(positions)} positions, total P&L: $+{total_pnl:.2f}' if total_pnl >= 0 else f'Closed {closed_count}/{len(positions)} positions, total P&L: ${total_pnl:.2f}',
            trader_id=trader_id
        )

    def hold(self, trader_id: str) -> PositionResult:
        """No action - hold current positions

        Args:
            trader_id: Trader ID

        Returns:
            PositionResult with hold confirmation
        """
        return PositionResult(
            success=True,
            message=f'No action taken for trader {trader_id}',
            trader_id=trader_id
        )


# Tool descriptions for AI
TOOL_DESCRIPTIONS = """
## Available Trading Tools

You have direct access to the following trading functions. Call them to execute trades:

### 1. open_position()
Open a new trading position.

**Parameters:**
- trader_id (str): Trader ID
- exchange (str): Exchange name - "binance", "okx", "bybit", or "bitget"
- symbol (str): Trading pair - e.g., "BTCUSDT", "ETHUSDT"
- side (str): Position side - "long" or "short"
- size (float): Position size in base currency (e.g., 0.1 for BTC, 1.0 for ETH)
- leverage (float, optional): Leverage multiplier (e.g., 5 for 5x). Default is 1.

**Example:**
```python
result = await open_position(
    trader_id="12",
    exchange="binance",
    symbol="BTCUSDT",
    side="short",
    size=0.085,
    leverage=10
)
```

**Returns:** PositionResult object with `.message` attribute:
- success (bool): Whether the operation succeeded
- message (str): Human-readable result message
- position_id (int): ID of the created position (if successful)
- error (str): Error details (if failed)

**Example usage:**
```python
result = await open_position(...)
if result.success:
    print(result.message)  # Access via .message attribute
else:
    print(f"Error: {result.error}")
```

---

### 2. close_position()
Close an existing position.

**Parameters:**
- position_id (int): Position ID to close
- price (float, optional): Close price. If not provided, uses current market price

**Example:**
```python
result = await close_position(position_id=123)
```

**Returns:** PositionResult object with `.message` attribute containing P&L information

---

### 3. close_all_positions()
Close all open positions for a trader.

**Parameters:**
- trader_id (str): Trader ID

**Example:**
```python
result = await close_all_positions(trader_id="12")
```

**Returns:** PositionResult object with `.message` attribute containing summary of closed positions

---

### 4. hold()
Take no action - hold current positions.

**Parameters:**
- trader_id (str): Trader ID

**Example:**
```python
result = hold(trader_id="12")
```

**Returns:** PositionResult object with `.message` attribute confirming hold action

---

## Important Notes

1. **Size Guidelines**: Position size should be 1-10% of trader's balance
2. **Symbol Format**: Use correct format like "BTCUSDT", "ETHUSDT" - do NOT duplicate suffixes
3. **Leverage**: Optional parameter - defaults to 1x if not specified
4. **Error Handling**: Always check the `success` field in results
5. **Async Functions**: open_position(), close_position(), and close_all_positions() are async - use `await`

## Decision Format

After analyzing the market, call one of the above functions directly. Do NOT output text commands like "OPEN_SHORT ...". Instead, call the function and set the result as the final `result` variable:

```python
# WRONG:
OPEN_SHORT binance BTCUSDT 0.085 10

# RIGHT:
result = await open_position(
    trader_id="12",
    exchange="binance",
    symbol="BTCUSDT",
    side="short",
    size=0.085,
    leverage=10
)

# All functions return PositionResult objects with a .message attribute
# You can access the message like this:
result.message  # e.g., "Opened short position: binance BTCUSDT 0.085 @ 43250.00"
```
"""
