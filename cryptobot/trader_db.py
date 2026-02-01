"""Trader Database Module

SQLite database for storing and managing trader metadata.
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime


class TraderDatabase:
    """SQLite database for trader metadata storage"""

    def __init__(self, db_path: str = None):
        """Initialize the trader database

        Args:
            db_path: Path to SQLite database file. Defaults to traders.db in project root.
        """
        if db_path is None:
            # Default to traders.db in the project root
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

        # Create traders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS traders (
                id TEXT PRIMARY KEY,
                trader_file TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                characteristics TEXT,
                style TEXT,
                strategy TEXT,
                trading_pairs TEXT,
                timeframes TEXT,
                indicators TEXT,
                information_sources TEXT,
                prompt TEXT,
                diversity_score REAL,
                metadata TEXT,
                initial_balance REAL DEFAULT 10000.0,
                current_balance REAL DEFAULT 10000.0,
                equity REAL DEFAULT 10000.0
            )
        """)

        # Add new columns if table exists but doesn't have them (migration)
        try:
            cursor.execute("ALTER TABLE traders ADD COLUMN initial_balance REAL DEFAULT 10000.0")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute("ALTER TABLE traders ADD COLUMN current_balance REAL DEFAULT 10000.0")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute("ALTER TABLE traders ADD COLUMN equity REAL DEFAULT 10000.0")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Create indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_style ON traders(style)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_created_at ON traders(created_at)
        """)

        # Create new relational tables
        self._create_pairs_table(cursor)
        self._create_intervals_table(cursor)
        self._create_junction_tables(cursor)

        # Populate default intervals
        self._populate_default_intervals(cursor)

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

    def add_trader(self, trader_data: Dict[str, Any]) -> bool:
        """Add a new trader to the database

        Args:
            trader_data: Dictionary containing trader information with keys:
                - id (str): Unique trader identifier
                - trader_file (str): Path to trader markdown file
                - characteristics (dict): Trader characteristics
                - style (str): Trading style
                - strategy (dict): Trading strategy
                - trading_pairs (list): List of trading pairs
                - timeframes (list): List of timeframes
                - indicators (list): List of indicators
                - information_sources (list): List of information sources
                - prompt (str, optional): Original user prompt
                - diversity_score (float, optional): Diversity score
                - metadata (dict, optional): Additional metadata
                - initial_balance (float, optional): Initial balance (default: 10000.0)
                - current_balance (float, optional): Current balance (default: 10000.0)
                - equity (float, optional): Current equity (default: 10000.0)

        Returns:
            True if trader was added successfully, False otherwise
        """
        if not self.conn:
            self.initialize()

        # Extract pairs and intervals for relational storage
        trading_pairs = trader_data.pop('trading_pairs', [])
        timeframes = trader_data.pop('timeframes', [])

        cursor = self.conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO traders (
                    id, trader_file, characteristics, style, strategy,
                    trading_pairs, timeframes, indicators, information_sources,
                    prompt, diversity_score, metadata, initial_balance, current_balance, equity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trader_data['id'],
                trader_data['trader_file'],
                json.dumps(trader_data.get('characteristics', {})),
                trader_data.get('style', ''),
                json.dumps(trader_data.get('strategy', {})),
                json.dumps([]),  # Empty array for deprecated field
                json.dumps([]),  # Empty array for deprecated field
                json.dumps(trader_data.get('indicators', [])),
                json.dumps(trader_data.get('information_sources', [])),
                trader_data.get('prompt', ''),
                trader_data.get('diversity_score'),
                json.dumps(trader_data.get('metadata', {})),
                trader_data.get('initial_balance', 10000.0),
                trader_data.get('current_balance', 10000.0),
                trader_data.get('equity', 10000.0)
            ))

            # Create relational associations
            trader_id = trader_data['id']
            if trading_pairs:
                self.add_trader_pairs(trader_id, trading_pairs)
            if timeframes:
                self.add_trader_intervals(trader_id, timeframes)

            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Trader with this ID already exists
            return False
        except Exception as e:
            self.conn.rollback()
            raise e

    def get_trader(self, trader_id: str) -> Optional[Dict[str, Any]]:
        """Get a trader by ID

        Args:
            trader_id: Unique trader identifier

        Returns:
            Dictionary with trader data, or None if not found
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM traders WHERE id = ?", (trader_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return self._row_to_dict(row)

    def list_traders(self, limit: int = None, offset: int = 0) -> List[Dict[str, Any]]:
        """List all traders

        Args:
            limit: Maximum number of traders to return
            offset: Number of traders to skip

        Returns:
            List of trader dictionaries
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()
        query = "SELECT * FROM traders ORDER BY created_at DESC"

        if limit:
            query += " LIMIT ? OFFSET ?"
            cursor.execute(query, (limit, offset))
        else:
            cursor.execute(query)

        rows = cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_all_trader_summaries(self) -> List[Dict[str, Any]]:
        """Get summary information for all traders

        Returns a lightweight list with basic info for all traders.
        Useful for diversity analysis.

        Returns:
            List of trader summary dictionaries
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, trader_file, created_at, style, characteristics
            FROM traders
            ORDER BY created_at DESC
        """)

        rows = cursor.fetchall()
        summaries = []
        for row in rows:
            summary = {
                'id': row['id'],
                'trader_file': row['trader_file'],
                'created_at': row['created_at'],
                'style': row['style'],
                'characteristics': json.loads(row['characteristics']) if row['characteristics'] else {}
            }
            summaries.append(summary)

        return summaries

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a database row to a dictionary

        Args:
            row: SQLite row object

        Returns:
            Dictionary with parsed JSON fields
        """
        trader_dict = dict(row)
        trader_id = trader_dict['id']

        # Parse JSON fields (except trading_pairs, timeframes - fetched from relations)
        for field in ['characteristics', 'strategy', 'indicators', 'information_sources', 'metadata']:
            if trader_dict.get(field):
                try:
                    trader_dict[field] = json.loads(trader_dict[field])
                except json.JSONDecodeError:
                    trader_dict[field] = {}
            else:
                trader_dict[field] = {} if field in ['characteristics', 'strategy', 'metadata'] else []

        # Fetch trading_pairs from relational table
        trader_dict['trading_pairs'] = [
            p['symbol'] for p in self.get_trader_pairs(trader_id)
        ]

        # Fetch timeframes from relational table
        trader_dict['timeframes'] = [
            i['code'] for i in self.get_trader_intervals(trader_id)
        ]

        return trader_dict

    def delete_trader(self, trader_id: str) -> bool:
        """Delete a trader from the database

        Args:
            trader_id: Unique trader identifier

        Returns:
            True if trader was deleted, False if not found
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM traders WHERE id = ?", (trader_id,))
        self.conn.commit()

        return cursor.rowcount > 0

    def update_trader(self, trader_id: str, updates: Dict[str, Any]) -> bool:
        """Update trader information

        Args:
            trader_id: Unique trader identifier
            updates: Dictionary of fields to update

        Returns:
            True if trader was updated, False if not found
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()

        # Build update query dynamically
        allowed_fields = [
            'characteristics', 'style', 'strategy', 'trading_pairs',
            'timeframes', 'indicators', 'information_sources', 'prompt',
            'diversity_score', 'metadata', 'initial_balance', 'current_balance', 'equity'
        ]

        update_fields = []
        values = []

        for field in allowed_fields:
            if field in updates:
                update_fields.append(f"{field} = ?")
                # Serialize dict/list fields as JSON
                if field in ['characteristics', 'strategy', 'trading_pairs',
                            'timeframes', 'indicators', 'information_sources', 'metadata']:
                    values.append(json.dumps(updates[field]))
                else:
                    values.append(updates[field])

        if not update_fields:
            return False

        values.append(trader_id)

        query = f"UPDATE traders SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(query, values)
        self.conn.commit()

        return cursor.rowcount > 0

    def search_traders(self, **filters) -> List[Dict[str, Any]]:
        """Search traders by various criteria

        Args:
            **filters: Key-value pairs for filtering (e.g., style="swing_trading")

        Returns:
            List of matching trader dictionaries
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()

        # Build WHERE clause
        conditions = []
        values = []

        for key, value in filters.items():
            if key in ['style', 'prompt']:
                conditions.append(f"{key} = ?")
                values.append(value)
            elif key == 'id':
                conditions.append("id LIKE ?")
                values.append(f"%{value}%")

        query = "SELECT * FROM traders"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC"

        cursor.execute(query, values)
        rows = cursor.fetchall()

        return [self._row_to_dict(row) for row in rows]

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics

        Returns:
            Dictionary with statistics about the database
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()

        # Total traders
        cursor.execute("SELECT COUNT(*) as count FROM traders")
        total = cursor.fetchone()['count']

        # Traders by style
        cursor.execute("""
            SELECT style, COUNT(*) as count
            FROM traders
            GROUP BY style
            ORDER BY count DESC
        """)
        by_style = {row['style']: row['count'] for row in cursor.fetchall()}

        # Latest trader
        cursor.execute("""
            SELECT id, created_at
            FROM traders
            ORDER BY created_at DESC
            LIMIT 1
        """)
        latest = cursor.fetchone()

        return {
            'total_traders': total,
            'by_style': by_style,
            'latest_trader': {
                'id': latest['id'],
                'created_at': latest['created_at']
            } if latest else None
        }

    def update_balance_and_equity(
        self,
        trader_id: str,
        balance_change: float = 0.0,
        equity_change: float = None
    ) -> bool:
        """Update trader's balance and equity

        Args:
            trader_id: Unique trader identifier
            balance_change: Amount to add/subtract from current_balance (can be negative)
            equity_change: Amount to set equity to (if None, equity = current_balance + unrealized_pnl)

        Returns:
            True if updated, False if trader not found
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()

        # Get current values
        cursor.execute("SELECT current_balance, equity FROM traders WHERE id = ?", (trader_id,))
        row = cursor.fetchone()

        if not row:
            return False

        current_balance = row['current_balance']
        new_balance = current_balance + balance_change

        # Calculate equity
        if equity_change is not None:
            new_equity = equity_change
        else:
            # If equity_change not provided, set equity equal to balance
            # (Callers should update equity separately with unrealized PnL if needed)
            new_equity = new_balance

        # Update
        cursor.execute("""
            UPDATE traders
            SET current_balance = ?, equity = ?
            WHERE id = ?
        """, (new_balance, new_equity, trader_id))

        self.conn.commit()
        return cursor.rowcount > 0

    def update_equity_with_unrealized_pnl(
        self,
        trader_id: str,
        unrealized_pnl: float
    ) -> bool:
        """Update trader's equity including unrealized PnL from open positions

        Args:
            trader_id: Unique trader identifier
            unrealized_pnl: Total unrealized PnL from all open positions

        Returns:
            True if updated, False if trader not found
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()

        # Get current balance
        cursor.execute("SELECT current_balance FROM traders WHERE id = ?", (trader_id,))
        row = cursor.fetchone()

        if not row:
            return False

        current_balance = row['current_balance']
        new_equity = current_balance + unrealized_pnl

        # Update equity
        cursor.execute("""
            UPDATE traders
            SET equity = ?
            WHERE id = ?
        """, (new_equity, trader_id))

        self.conn.commit()
        return cursor.rowcount > 0

    # =============================================================================
    # Pairs and Intervals Relational Tables
    # =============================================================================

    def _create_pairs_table(self, cursor):
        """Create pairs table"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pairs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                exchange TEXT NOT NULL,
                base_currency TEXT,
                quote_currency TEXT,
                contract_type TEXT DEFAULT 'perpetual',
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pairs_symbol ON pairs(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pairs_exchange ON pairs(exchange)")

    def _create_intervals_table(self, cursor):
        """Create intervals table"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS intervals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                seconds INTEGER NOT NULL,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_intervals_code ON intervals(code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_intervals_seconds ON intervals(seconds)")

    def _create_junction_tables(self, cursor):
        """Create many-to-many junction tables"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trader_pairs (
                trader_id TEXT NOT NULL,
                pair_id INTEGER NOT NULL,
                is_primary BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (trader_id, pair_id),
                FOREIGN KEY (trader_id) REFERENCES traders(id) ON DELETE CASCADE,
                FOREIGN KEY (pair_id) REFERENCES pairs(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tp_trader ON trader_pairs(trader_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tp_pair ON trader_pairs(pair_id)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trader_intervals (
                trader_id TEXT NOT NULL,
                interval_id INTEGER NOT NULL,
                purpose TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (trader_id, interval_id),
                FOREIGN KEY (trader_id) REFERENCES traders(id) ON DELETE CASCADE,
                FOREIGN KEY (interval_id) REFERENCES intervals(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ti_trader ON trader_intervals(trader_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ti_interval ON trader_intervals(interval_id)")

    def _populate_default_intervals(self, cursor):
        """Populate intervals table with default values"""
        intervals = [
            ('1m', '1 minute', 60, 'minute'),
            ('3m', '3 minutes', 180, 'minute'),
            ('5m', '5 minutes', 300, 'minute'),
            ('15m', '15 minutes', 900, 'minute'),
            ('30m', '30 minutes', 1800, 'minute'),
            ('1h', '1 hour', 3600, 'hour'),
            ('2h', '2 hours', 7200, 'hour'),
            ('4h', '4 hours', 14400, 'hour'),
            ('6h', '6 hours', 21600, 'hour'),
            ('12h', '12 hours', 43200, 'hour'),
            ('1d', '1 day', 86400, 'day'),
            ('1w', '1 week', 604800, 'week'),
            ('1M', '1 month', 2592000, 'month'),
        ]

        cursor.executemany(
            "INSERT OR IGNORE INTO intervals (code, name, seconds, category) VALUES (?, ?, ?, ?)",
            intervals
        )

    def sync_pairs_from_exchange(self, exchange: str, markets: list) -> int:
        """Sync pairs from CCXT exchange data

        Args:
            exchange: Exchange name (e.g., 'binance')
            markets: List of market dicts from CCXT

        Returns:
            Number of pairs synced
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()
        synced = 0

        for market in markets:
            symbol = market['symbol']
            # Normalize symbol (remove CCXT formatting)
            normalized = symbol.replace('/', '').replace(':', '').replace('-', '')

            try:
                cursor.execute("""
                    INSERT INTO pairs (symbol, exchange, base_currency, quote_currency)
                    VALUES (?, ?, ?, ?)
                """, (
                    normalized,
                    exchange,
                    market.get('base'),
                    market.get('quote') or 'USDT'
                ))
                synced += 1
            except sqlite3.IntegrityError:
                # Pair exists, update it
                cursor.execute("""
                    UPDATE pairs
                    SET exchange = ?, base_currency = ?, quote_currency = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE symbol = ?
                """, (exchange, market.get('base'), market.get('quote') or 'USDT', normalized))
                synced += 1

        self.conn.commit()
        return synced

    def get_pair_by_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get pair by symbol"""
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM pairs WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_pairs(self, exchange: str = None) -> List[Dict[str, Any]]:
        """Get all pairs, optionally filtered by exchange"""
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()
        if exchange:
            cursor.execute("SELECT * FROM pairs WHERE exchange = ? ORDER BY symbol", (exchange,))
        else:
            cursor.execute("SELECT * FROM pairs ORDER BY symbol")
        return [dict(row) for row in cursor.fetchall()]

    def get_all_intervals(self) -> List[Dict[str, Any]]:
        """Get all intervals ordered by seconds"""
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM intervals ORDER BY seconds")
        return [dict(row) for row in cursor.fetchall()]

    def add_trader_pairs(self, trader_id: str, pair_symbols: List[str], exchange: str = 'binance'):
        """Associate pairs with a trader

        Args:
            trader_id: Trader ID
            pair_symbols: List of pair symbols (e.g., ['BTCUSDT', 'ETHUSDT'])
            exchange: Exchange name (default: 'binance')
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()

        for symbol in pair_symbols:
            # Get or create pair
            pair = self.get_pair_by_symbol(symbol)
            if not pair:
                cursor.execute("""
                    INSERT INTO pairs (symbol, exchange)
                    VALUES (?, ?)
                """, (symbol, exchange))
                pair_id = cursor.lastrowid
            else:
                pair_id = pair['id']

            # Create association
            try:
                cursor.execute("""
                    INSERT INTO trader_pairs (trader_id, pair_id)
                    VALUES (?, ?)
                """, (trader_id, pair_id))
            except sqlite3.IntegrityError:
                pass  # Already exists

        self.conn.commit()

    def add_trader_intervals(self, trader_id: str, interval_codes: List[str]):
        """Associate intervals with a trader

        Args:
            trader_id: Trader ID
            interval_codes: List of interval codes (e.g., ['1h', '4h', '1d'])
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()

        for code in interval_codes:
            # Get interval
            cursor.execute("SELECT id FROM intervals WHERE code = ?", (code,))
            row = cursor.fetchone()

            if row:
                interval_id = row['id']
                try:
                    cursor.execute("""
                        INSERT INTO trader_intervals (trader_id, interval_id)
                        VALUES (?, ?)
                    """, (trader_id, interval_id))
                except sqlite3.IntegrityError:
                    pass  # Already exists

        self.conn.commit()

    def get_trader_pairs(self, trader_id: str) -> List[Dict[str, Any]]:
        """Get all pairs for a trader"""
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT p.*
            FROM pairs p
            JOIN trader_pairs tp ON p.id = tp.pair_id
            WHERE tp.trader_id = ?
            ORDER BY p.symbol
        """, (trader_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_trader_intervals(self, trader_id: str) -> List[Dict[str, Any]]:
        """Get all intervals for a trader"""
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT i.*
            FROM intervals i
            JOIN trader_intervals ti ON i.id = ti.interval_id
            WHERE ti.trader_id = ?
            ORDER BY i.seconds
        """, (trader_id,))
        return [dict(row) for row in cursor.fetchall()]
