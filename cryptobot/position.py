"""Position Model for Contract Trading

Defines position data structures and calculation methods for perpetual futures trading.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime


class PositionSide(Enum):
    """Position side (long or short)"""
    LONG = "long"
    SHORT = "short"


class PositionStatus(Enum):
    """Position status"""
    OPEN = "open"
    CLOSED = "closed"
    LIQUIDATED = "liquidated"


@dataclass
class Position:
    """Contract trading position model

    Attributes:
        id: Position ID (auto-assigned by database)
        trader_id: Associated trader ID
        exchange: Exchange name (binance, okx, bybit, bitget)
        symbol: Trading symbol (e.g., BTCUSDT)
        position_side: Long or short
        status: Open, closed, or liquidated
        leverage: Leverage multiplier (default 1.0)
        entry_price: Entry price
        entry_time: Position entry timestamp
        entry_fee: Trading fee paid on entry
        exit_price: Exit price (for closed positions)
        exit_time: Position exit timestamp
        exit_fee: Trading fee paid on exit
        position_size: Position size in base currency (e.g., BTC amount)
        margin: Margin in USDT
        contract_size: Contract size (default 1.0)
        unrealized_pnl: Current unrealized PnL
        realized_pnl: Final realized PnL (for closed positions)
        roi: Return on investment percentage
        stop_loss_price: Stop loss price (optional)
        take_profit_price: Take profit price (optional)
        liquidation_price: Calculated liquidation price
        notes: User notes
        metadata: Additional metadata (JSON string)
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    id: Optional[int] = None
    trader_id: str = ""
    exchange: str = ""
    symbol: str = ""
    position_side: PositionSide = PositionSide.LONG
    status: PositionStatus = PositionStatus.OPEN
    leverage: float = 1.0
    entry_price: float = 0.0
    entry_time: Optional[datetime] = None
    entry_fee: float = 0.0
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_fee: float = 0.0
    position_size: float = 0.0
    margin: float = 0.0
    contract_size: float = 1.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    roi: float = 0.0
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    liquidation_price: Optional[float] = None
    notes: Optional[str] = None
    metadata: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def calculate_unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized PnL based on current price

        Args:
            current_price: Current market price

        Returns:
            Unrealized PnL (profit/loss minus entry fees)
        """
        if self.status != PositionStatus.OPEN:
            return 0.0

        price_diff = current_price - self.entry_price

        if self.position_side == PositionSide.LONG:
            # Long: profit when price goes up
            pnl = self.position_size * price_diff * self.leverage
        else:
            # Short: profit when price goes down
            pnl = self.position_size * (-price_diff) * self.leverage

        # Subtract entry fee
        return pnl - self.entry_fee

    def calculate_roi(self, pnl: float) -> float:
        """Calculate Return on Investment percentage

        Args:
            pnl: Profit or loss amount

        Returns:
            ROI percentage
        """
        if self.margin == 0:
            return 0.0
        return (pnl / self.margin) * 100

    def calculate_liquidation_price(self) -> float:
        """Calculate liquidation price

        For long positions:
            liq_price = entry_price * (1 - 1/leverage + maintenance_margin)

        For short positions:
            liq_price = entry_price * (1 + 1/leverage - maintenance_margin)

        Uses maintenance margin of 0.005 (0.5%) as typical for USDT pairs.

        Returns:
            Liquidation price
        """
        maintenance_margin = 0.005  # 0.5% maintenance margin

        if self.position_side == PositionSide.LONG:
            liq_price = self.entry_price * (1 - 1/self.leverage + maintenance_margin)
        else:
            liq_price = self.entry_price * (1 + 1/self.leverage - maintenance_margin)

        return max(0.0, liq_price)

    def is_liquidated(self, current_price: float) -> bool:
        """Check if position would be liquidated at current price

        Args:
            current_price: Current market price

        Returns:
            True if liquidated, False otherwise
        """
        if self.liquidation_price is None:
            self.liquidation_price = self.calculate_liquidation_price()

        if self.position_side == PositionSide.LONG:
            # Long position liquidated when price drops below liq price
            return current_price <= self.liquidation_price
        else:
            # Short position liquidated when price rises above liq price
            return current_price >= self.liquidation_price

    def to_dict(self) -> Dict[str, Any]:
        """Convert position to dictionary

        Returns:
            Dictionary representation of position
        """
        return {
            'id': self.id,
            'trader_id': self.trader_id,
            'exchange': self.exchange,
            'symbol': self.symbol,
            'position_side': self.position_side.value if isinstance(self.position_side, PositionSide) else self.position_side,
            'status': self.status.value if isinstance(self.status, PositionStatus) else self.status,
            'leverage': self.leverage,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time.isoformat() if self.entry_time else None,
            'entry_fee': self.entry_fee,
            'exit_price': self.exit_price,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'exit_fee': self.exit_fee,
            'position_size': self.position_size,
            'margin': self.margin,
            'contract_size': self.contract_size,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'roi': self.roi,
            'stop_loss_price': self.stop_loss_price,
            'take_profit_price': self.take_profit_price,
            'liquidation_price': self.liquidation_price,
            'notes': self.notes,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Position':
        """Create Position from dictionary

        Args:
            data: Dictionary with position data

        Returns:
            Position instance
        """
        # Convert enum strings back to enums
        position_side = data.get('position_side', 'long')
        if isinstance(position_side, str):
            position_side = PositionSide(position_side)

        status = data.get('status', 'open')
        if isinstance(status, str):
            status = PositionStatus(status)

        # Parse datetime strings
        entry_time = data.get('entry_time')
        if entry_time and isinstance(entry_time, str):
            entry_time = datetime.fromisoformat(entry_time)

        exit_time = data.get('exit_time')
        if exit_time and isinstance(exit_time, str):
            exit_time = datetime.fromisoformat(exit_time)

        created_at = data.get('created_at')
        if created_at and isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        updated_at = data.get('updated_at')
        if updated_at and isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        return cls(
            id=data.get('id'),
            trader_id=data.get('trader_id', ''),
            exchange=data.get('exchange', ''),
            symbol=data.get('symbol', ''),
            position_side=position_side,
            status=status,
            leverage=data.get('leverage', 1.0),
            entry_price=data.get('entry_price', 0.0),
            entry_time=entry_time,
            entry_fee=data.get('entry_fee', 0.0),
            exit_price=data.get('exit_price'),
            exit_time=exit_time,
            exit_fee=data.get('exit_fee', 0.0),
            position_size=data.get('position_size', 0.0),
            margin=data.get('margin', 0.0),
            contract_size=data.get('contract_size', 1.0),
            unrealized_pnl=data.get('unrealized_pnl', 0.0),
            realized_pnl=data.get('realized_pnl', 0.0),
            roi=data.get('roi', 0.0),
            stop_loss_price=data.get('stop_loss_price'),
            take_profit_price=data.get('take_profit_price'),
            liquidation_price=data.get('liquidation_price'),
            notes=data.get('notes'),
            metadata=data.get('metadata'),
            created_at=created_at,
            updated_at=updated_at,
        )

    @classmethod
    def from_db_row(cls, row: Any) -> 'Position':
        """Create Position from database row (sqlite3.Row)

        Args:
            row: SQLite row object

        Returns:
            Position instance
        """
        data = dict(row)

        # Convert position_side and status to enums
        position_side = PositionSide(data['position_side'])
        status = PositionStatus(data['status'])

        # Parse entry_time and exit_time
        entry_time = data.get('entry_time')
        if entry_time and isinstance(entry_time, str):
            entry_time = datetime.fromisoformat(entry_time)

        exit_time = data.get('exit_time')
        if exit_time and isinstance(exit_time, str):
            exit_time = datetime.fromisoformat(exit_time)

        created_at = data.get('created_at')
        if created_at and isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        updated_at = data.get('updated_at')
        if updated_at and isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        return cls(
            id=data['id'],
            trader_id=data['trader_id'],
            exchange=data['exchange'],
            symbol=data['symbol'],
            position_side=position_side,
            status=status,
            leverage=data['leverage'],
            entry_price=data['entry_price'],
            entry_time=entry_time,
            entry_fee=data['entry_fee'],
            exit_price=data.get('exit_price'),
            exit_time=exit_time,
            exit_fee=data['exit_fee'],
            position_size=data['position_size'],
            margin=data['margin'],
            contract_size=data['contract_size'],
            unrealized_pnl=data['unrealized_pnl'],
            realized_pnl=data['realized_pnl'],
            roi=data['roi'],
            stop_loss_price=data.get('stop_loss_price'),
            take_profit_price=data.get('take_profit_price'),
            liquidation_price=data.get('liquidation_price'),
            notes=data.get('notes'),
            metadata=data.get('metadata'),
            created_at=created_at,
            updated_at=updated_at,
        )
