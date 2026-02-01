"""Position Database Module

SQLite database for storing and managing contract trading positions.
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime

from .position import Position, PositionSide, PositionStatus


class PositionDatabase:
    """SQLite database for position storage"""

    def __init__(self, db_path: str = None):
        """Initialize the position database

        Args:
            db_path: Path to SQLite database file. Defaults to traders.db in project root.
        """
        if db_path is None:
            # Default to traders.db in the project root (same as trader_db)
            project_root = Path(__file__).parent.parent
            db_path = str(project_root / "traders.db")

        self.db_path = db_path
        self.conn = None

    def initialize(self):
        """Initialize database and create tables if they don't exist"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

        cursor = self.conn.cursor()

        # Enable foreign key constraints (required for CASCADE delete to work)
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Create positions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trader_id TEXT NOT NULL,
                exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                position_side TEXT NOT NULL,
                status TEXT NOT NULL,
                leverage REAL DEFAULT 1.0,
                entry_price REAL NOT NULL,
                entry_time TIMESTAMP NOT NULL,
                entry_fee REAL DEFAULT 0.0,
                exit_price REAL,
                exit_time TIMESTAMP,
                exit_fee REAL DEFAULT 0.0,
                position_size REAL NOT NULL,
                margin REAL NOT NULL,
                contract_size REAL DEFAULT 1.0,
                unrealized_pnl REAL DEFAULT 0.0,
                realized_pnl REAL DEFAULT 0.0,
                roi REAL DEFAULT 0.0,
                stop_loss_price REAL,
                take_profit_price REAL,
                liquidation_price REAL,
                notes TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trader_id) REFERENCES traders(id) ON DELETE CASCADE
            )
        """)

        # Create indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_trader_id ON positions(trader_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol)
        """)

        self.conn.commit()

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        """Context manager entry"""
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

    def add_position(self, position: Position) -> int:
        """Add a new position to the database

        Args:
            position: Position object to add

        Returns:
            ID of the inserted position

        Raises:
            sqlite3.IntegrityError: If trader_id doesn't exist
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()

        now = datetime.now()
        position.created_at = now
        position.updated_at = now

        try:
            cursor.execute("""
                INSERT INTO positions (
                    trader_id, exchange, symbol, position_side, status,
                    leverage, entry_price, entry_time, entry_fee,
                    exit_price, exit_time, exit_fee,
                    position_size, margin, contract_size,
                    unrealized_pnl, realized_pnl, roi,
                    stop_loss_price, take_profit_price, liquidation_price,
                    notes, metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position.trader_id,
                position.exchange,
                position.symbol,
                position.position_side.value if isinstance(position.position_side, PositionSide) else position.position_side,
                position.status.value if isinstance(position.status, PositionStatus) else position.status,
                position.leverage,
                position.entry_price,
                position.entry_time.isoformat() if position.entry_time else now.isoformat(),
                position.entry_fee,
                position.exit_price,
                position.exit_time.isoformat() if position.exit_time else None,
                position.exit_fee,
                position.position_size,
                position.margin,
                position.contract_size,
                position.unrealized_pnl,
                position.realized_pnl,
                position.roi,
                position.stop_loss_price,
                position.take_profit_price,
                position.liquidation_price,
                position.notes,
                position.metadata,
                position.created_at.isoformat(),
                position.updated_at.isoformat()
            ))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            self.conn.rollback()
            raise e
        except Exception as e:
            self.conn.rollback()
            raise e

    def get_position(self, position_id: int) -> Optional[Position]:
        """Get a position by ID

        Args:
            position_id: Position ID

        Returns:
            Position object or None if not found
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM positions WHERE id = ?", (position_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return Position.from_db_row(row)

    def list_positions(
        self,
        trader_id: str = None,
        status: str = None,
        symbol: str = None,
        limit: int = None,
        offset: int = 0
    ) -> List[Position]:
        """List positions with optional filters

        Args:
            trader_id: Filter by trader ID
            status: Filter by status (open, closed, liquidated)
            symbol: Filter by symbol
            limit: Maximum number of positions to return
            offset: Number of positions to skip

        Returns:
            List of Position objects
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()

        # Build query with filters
        query = "SELECT * FROM positions WHERE 1=1"
        params = []

        if trader_id:
            query += " AND trader_id = ?"
            params.append(trader_id)

        if status:
            query += " AND status = ?"
            params.append(status)

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        query += " ORDER BY created_at DESC"

        if limit:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [Position.from_db_row(row) for row in rows]

    def close_position(
        self,
        position_id: int,
        exit_price: float,
        exit_fee: float = None
    ) -> bool:
        """Close a position and calculate final PnL

        Args:
            position_id: Position ID
            exit_price: Exit price
            exit_fee: Trading fee paid on exit (optional, will be calculated if not provided)

        Returns:
            True if position was closed, False if not found

        Raises:
            ValueError: If position already closed or invalid exit_price
        """
        if not self.conn:
            self.initialize()

        # Get the position
        position = self.get_position(position_id)
        if not position:
            return False

        if position.status != PositionStatus.OPEN:
            raise ValueError(f"Position {position_id} is not open (status: {position.status.value})")

        if exit_price <= 0:
            raise ValueError("Exit price must be positive")

        # Calculate exit fee if not provided
        if exit_fee is None:
            from .fees import calculate_fee
            exit_fee = calculate_fee(position.exchange, position.position_size, exit_price)

        # Calculate realized PnL
        # Note: Leverage affects margin requirement but NOT the PnL calculation
        # If you open a 1 BTC position with 10x leverage:
        # - You control 1 BTC worth of position
        # - Price change of 1 USDT = 1 USDT PnL change (not 10 USDT)
        price_diff = exit_price - position.entry_price
        if position.position_side == PositionSide.LONG:
            pnl = position.position_size * price_diff
        else:
            pnl = position.position_size * (-price_diff)

        realized_pnl = pnl - position.entry_fee - exit_fee

        # Update position
        cursor = self.conn.cursor()
        exit_time = datetime.now()

        cursor.execute("""
            UPDATE positions
            SET status = 'closed',
                exit_price = ?,
                exit_time = ?,
                exit_fee = ?,
                realized_pnl = ?,
                unrealized_pnl = 0,
                roi = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            exit_price,
            exit_time.isoformat(),
            exit_fee,
            realized_pnl,
            position.calculate_roi(realized_pnl),
            exit_time.isoformat(),
            position_id
        ))

        self.conn.commit()
        return cursor.rowcount > 0

    def update_position_pnl(self, position_id: int, current_price: float) -> bool:
        """Update position's unrealized PnL and ROI based on current price

        Args:
            position_id: Position ID
            current_price: Current market price

        Returns:
            True if updated, False if position not found or not open
        """
        if not self.conn:
            self.initialize()

        position = self.get_position(position_id)
        if not position or position.status != PositionStatus.OPEN:
            return False

        # Calculate unrealized PnL and ROI
        unrealized_pnl = position.calculate_unrealized_pnl(current_price)
        roi = position.calculate_roi(unrealized_pnl)

        # Update database
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE positions
            SET unrealized_pnl = ?,
                roi = ?,
                updated_at = ?
            WHERE id = ?
        """, (unrealized_pnl, roi, datetime.now().isoformat(), position_id))

        self.conn.commit()
        return cursor.rowcount > 0

    def get_trader_positions_summary(self, trader_id: str) -> Dict[str, Any]:
        """Get summary statistics for a trader's positions

        Args:
            trader_id: Trader ID

        Returns:
            Dictionary with position statistics
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()

        # Get all positions for trader
        positions = self.list_positions(trader_id)

        if not positions:
            return {
                'total_positions': 0,
                'open_positions': 0,
                'closed_positions': 0,
                'liquidated_positions': 0,
                'total_unrealized_pnl': 0.0,
                'total_realized_pnl': 0.0,
                'average_roi': 0.0,
            }

        # Calculate statistics
        open_positions = [p for p in positions if p.status == PositionStatus.OPEN]
        closed_positions = [p for p in positions if p.status == PositionStatus.CLOSED]
        liquidated_positions = [p for p in positions if p.status == PositionStatus.LIQUIDATED]

        total_unrealized_pnl = sum(p.unrealized_pnl for p in open_positions)
        total_realized_pnl = sum(p.realized_pnl for p in closed_positions + liquidated_positions)

        # Calculate average ROI for closed positions
        closed_with_roi = [p for p in closed_positions if p.margin > 0]
        average_roi = sum(p.roi for p in closed_with_roi) / len(closed_with_roi) if closed_with_roi else 0.0

        return {
            'total_positions': len(positions),
            'open_positions': len(open_positions),
            'closed_positions': len(closed_positions),
            'liquidated_positions': len(liquidated_positions),
            'total_unrealized_pnl': total_unrealized_pnl,
            'total_realized_pnl': total_realized_pnl,
            'average_roi': average_roi,
            'open_position_details': [
                {
                    'id': p.id,
                    'symbol': p.symbol,
                    'side': p.position_side.value,
                    'entry_price': p.entry_price,
                    'unrealized_pnl': p.unrealized_pnl,
                    'roi': p.roi,
                }
                for p in open_positions
            ]
        }

    def delete_position(self, position_id: int) -> bool:
        """Delete a position from the database

        Args:
            position_id: Position ID

        Returns:
            True if deleted, False if not found
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM positions WHERE id = ?", (position_id,))
        self.conn.commit()

        return cursor.rowcount > 0

    def update_position_status(
        self,
        position_id: int,
        status: PositionStatus,
        exit_price: float = None,
        exit_time: datetime = None,
        realized_pnl: float = None
    ) -> bool:
        """Update position status (for closing or liquidating)

        Args:
            position_id: Position ID
            status: New status (CLOSED or LIQUIDATED)
            exit_price: Exit price (required for closed/liquidated positions)
            exit_time: Exit timestamp (defaults to current time)
            realized_pnl: Final realized PnL

        Returns:
            True if updated, False if position not found
        """
        if not self.conn:
            self.initialize()

        position = self.get_position(position_id)
        if not position:
            return False

        if exit_time is None:
            exit_time = datetime.now()

        cursor = self.conn.cursor()

        # Build update query dynamically
        update_fields = ["status = ?", "updated_at = ?"]
        params = [status.value, exit_time.isoformat()]

        if exit_price is not None:
            update_fields.append("exit_price = ?")
            params.append(exit_price)

        update_fields.append("exit_time = ?")
        params.append(exit_time.isoformat())

        if realized_pnl is not None:
            update_fields.append("realized_pnl = ?")
            params.append(realized_pnl)

            # Also update ROI if we have realized PnL
            if position.margin > 0:
                roi = (realized_pnl / position.margin) * 100
                update_fields.append("roi = ?")
                params.append(roi)

        # For liquidated/closed positions, reset unrealized PnL
        if status in [PositionStatus.CLOSED, PositionStatus.LIQUIDATED]:
            update_fields.append("unrealized_pnl = 0")

        params.append(position_id)

        query = f"UPDATE positions SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(query, params)

        self.conn.commit()
        return cursor.rowcount > 0
