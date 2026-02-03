"""Trader Database Module

SQLite database for storing and managing trader metadata.
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
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

        Raises:
            ValueError: If validation fails (too many pairs/intervals, interval below minimum)
        """
        if not self.conn:
            self.initialize()

        # Extract pairs and intervals for relational storage
        trading_pairs = trader_data.pop('trading_pairs', [])
        timeframes = trader_data.pop('timeframes', [])

        # Truncate to constraints and get warnings
        truncated_pairs, truncated_intervals, warnings = self._truncate_to_constraints(
            trading_pairs, timeframes
        )

        # Store warnings in metadata for later display
        if warnings:
            metadata = trader_data.get('metadata', {})
            metadata['_constraint_warnings'] = warnings
            trader_data['metadata'] = metadata

        trading_pairs = truncated_pairs
        timeframes = truncated_intervals

        # Sync profile.md file if truncation occurred
        if warnings and trader_data.get('trader_file'):
            self._sync_profile_md(
                trader_data['trader_file'],
                trading_pairs,
                timeframes
            )

        # Validate against config constraints (should pass now after truncation)
        self._validate_pairs_and_intervals(trading_pairs, timeframes)

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

    def _truncate_to_constraints(
        self,
        trading_pairs: List[str],
        timeframes: List[str]
    ) -> Tuple[List[str], List[str], List[str]]:
        """Truncate trading pairs and timeframes to fit within config constraints.

        This is a fallback mechanism when Claude Code generates a trader that exceeds
        the configured constraints. It intelligently trims the lists while preserving
        the most important items (earlier items are considered higher priority).

        Args:
            trading_pairs: List of trading pair symbols
            timeframes: List of timeframe codes

        Returns:
            Tuple of (truncated_pairs, truncated_intervals, warning_messages)
        """
        from .scheduler_config import get_scheduler_config

        config = get_scheduler_config(self.db_path)
        warnings = []

        # Get constraints
        max_pairs = config.get_int('trader.pairs.max', 10)
        max_intervals = config.get_int('trader.intervals.max', 5)
        min_seconds = config.get_int('trader.intervals.min_seconds', 300)

        # Truncate pairs if needed
        truncated_pairs = trading_pairs
        if len(trading_pairs) > max_pairs:
            truncated_pairs = trading_pairs[:max_pairs]
            removed = trading_pairs[max_pairs:]
            warnings.append(
                f"Trading pairs count truncated from {len(trading_pairs)} to {max_pairs} "
                f"(removed: {', '.join(removed)})"
            )

        # Truncate intervals if needed
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()

        # Get interval seconds for filtering
        interval_seconds = {}
        if timeframes:
            placeholders = ','.join(['?' for _ in timeframes])
            cursor.execute(
                f"SELECT code, seconds FROM intervals WHERE code IN ({placeholders})",
                timeframes
            )
            for row in cursor.fetchall():
                interval_seconds[row['code']] = row['seconds']

        # Filter out intervals below minimum
        valid_intervals = []
        removed_intervals = []
        for tf in timeframes:
            seconds = interval_seconds.get(tf)
            if seconds is None:
                removed_intervals.append(f"{tf} (invalid)")
            elif seconds < min_seconds:
                min_readable = self._seconds_to_readable(min_seconds)
                current_readable = self._seconds_to_readable(seconds)
                removed_intervals.append(f"{tf} ({current_readable} < {min_readable})")
            else:
                valid_intervals.append(tf)

        if removed_intervals:
            warnings.append(f"Removed intervals below minimum: {', '.join(removed_intervals)}")

        # Truncate intervals count if needed
        truncated_intervals = valid_intervals
        if len(valid_intervals) > max_intervals:
            truncated_intervals = valid_intervals[:max_intervals]
            removed = valid_intervals[max_intervals:]
            warnings.append(
                f"Intervals count truncated from {len(valid_intervals)} to {max_intervals} "
                f"(removed: {', '.join(removed)})"
            )

        return truncated_pairs, truncated_intervals, warnings

    def _validate_pairs_and_intervals(
        self,
        trading_pairs: List[str],
        timeframes: List[str]
    ) -> Tuple[bool, Optional[str]]:
        """Validate trading pairs and intervals against config constraints

        Args:
            trading_pairs: List of trading pair symbols
            timeframes: List of timeframe codes

        Raises:
            ValueError: If validation fails with descriptive message
        """
        from .scheduler_config import get_scheduler_config

        config = get_scheduler_config(self.db_path)

        # Validate pairs count
        max_pairs = config.get_int('trader.pairs.max', 10)
        if len(trading_pairs) > max_pairs:
            raise ValueError(
                f"Trading pairs count exceeds limit: {len(trading_pairs)} > {max_pairs}. "
                f"Adjust trader.pairs.max in /config"
            )

        # Validate intervals count and minimum
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()

        # Get interval seconds for validation
        interval_seconds = {}
        if timeframes:
            placeholders = ','.join(['?' for _ in timeframes])
            cursor.execute(
                f"SELECT code, seconds FROM intervals WHERE code IN ({placeholders})",
                timeframes
            )
            for row in cursor.fetchall():
                interval_seconds[row['code']] = row['seconds']

        # Check minimum interval
        min_seconds = config.get_int('trader.intervals.min_seconds', 300)
        for timeframe in timeframes:
            seconds = interval_seconds.get(timeframe)
            if seconds is None:
                raise ValueError(f"Invalid interval: {timeframe}")
            if seconds < min_seconds:
                # Convert seconds to readable format
                min_readable = self._seconds_to_readable(min_seconds)
                current_readable = self._seconds_to_readable(seconds)
                raise ValueError(
                    f"Interval too small: {timeframe} ({current_readable}) < minimum {min_readable}. "
                    f"Adjust trader.intervals.min_seconds in /config"
                )

        # Validate intervals count
        max_intervals = config.get_int('trader.intervals.max', 5)
        if len(timeframes) > max_intervals:
            raise ValueError(
                f"Intervals count exceeds limit: {len(timeframes)} > {max_intervals}. "
                f"Adjust trader.intervals.max in /config"
            )

    def _seconds_to_readable(self, seconds: int) -> str:
        """Convert seconds to readable timeframe string

        Args:
            seconds: Timeframe in seconds

        Returns:
            Readable string (e.g., "5m", "1h", "1d")
        """
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m"
        elif seconds < 86400:
            return f"{seconds // 3600}h"
        elif seconds < 604800:
            return f"{seconds // 86400}d"
        else:
            return f"{seconds // 604800}w"

    def _sync_profile_md(
        self,
        trader_file: str,
        trading_pairs: List[str],
        timeframes: List[str]
    ) -> None:
        """Synchronize profile.md file with truncated trading pairs and timeframes.

        Updates the profile.md file to match the database-stored values after
        constraint truncation.

        Args:
            trader_file: Path to the trader profile.md file
            trading_pairs: Truncated list of trading pairs
            timeframes: Truncated list of timeframe codes
        """
        import re
        from pathlib import Path

        profile_path = Path(trader_file)
        if not profile_path.exists():
            return

        try:
            content = profile_path.read_text(encoding='utf-8')

            # Update Preferred Pairs line
            if trading_pairs:
                pairs_str = ', '.join(trading_pairs)
                # Pattern to match: - **Preferred Pairs:** `...`
                new_content = re.sub(
                    r'- \*\*Preferred Pairs:\*\* `[^`]*`',
                    f'- **Preferred Pairs:** `{pairs_str}`',
                    content
                )
                if new_content == content:
                    # If no Preferred Pairs found, try to update Primary Assets
                    new_content = re.sub(
                        r'- \*\*Primary Assets:\*\* `[^`]*`',
                        f'- **Primary Assets:** `{pairs_str}`',
                        content
                    )
                content = new_content

            # Update Timeframes - more complex, need to reconstruct the section
            if timeframes:
                # Convert timeframe codes to readable format
                timeframe_readable = []
                for tf in timeframes:
                    if tf.endswith('m'):
                        timeframe_readable.append(f"{tf[:-1]}-minute")
                    elif tf.endswith('h'):
                        timeframe_readable.append(f"{tf[:-1]}-hour")
                    elif tf.endswith('d'):
                        timeframe_readable.append("daily")
                    elif tf.endswith('w'):
                        timeframe_readable.append("weekly")
                    elif tf == '1M':
                        timeframe_readable.append("monthly")
                    else:
                        timeframe_readable.append(tf)

                # Build new timeframe description
                if len(timeframe_readable) == 1:
                    tf_desc = timeframe_readable[0]
                elif len(timeframe_readable) == 2:
                    tf_desc = f"{timeframe_readable[0]} and {timeframe_readable[1]}"
                else:
                    tf_desc = ', '.join(timeframe_readable[:-1]) + ', and ' + timeframe_readable[-1]

                # Update Analysis Timeframe
                content = re.sub(
                    r'- \*\*Analysis Timeframe:\*\* `[^`]*`',
                    f'- **Analysis Timeframe:** `{tf_desc}`',
                    content
                )

                # Update Entry Timeframe (use the smallest timeframe)
                if timeframe_readable:
                    entry_tf = timeframe_readable[0]
                    content = re.sub(
                        r'- \*\*Entry Timeframe:\*\* `[^`]*`',
                        f'- **Entry Timeframe:** `{entry_tf} for precision timing`',
                        content
                    )

            # Add truncation notice at the end of file
            truncation_notice = """

---

**NOTE:** This trader's trading pairs and/or timeframes have been automatically adjusted to comply with system constraints. The values stored in the database are the authoritative configuration for this trader.
"""
            if 'NOTE:' not in content:
                content += truncation_notice

            # Write back to file
            profile_path.write_text(content, encoding='utf-8')

        except Exception as e:
            # Don't fail the whole operation if profile update fails
            # Just log the error silently
            pass

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

    def add_trader_pairs(self, trader_id: str, pair_symbols: List[str], exchange: str = None):
        """Associate pairs with a trader

        Args:
            trader_id: Trader ID
            pair_symbols: List of pair symbols (e.g., ['BTCUSDT', 'ETHUSDT'])
            exchange: Exchange name (default: from config, usually 'okx')

        Raises:
            ValueError: If total pairs exceed maximum allowed
        """
        if not self.conn:
            self.initialize()

        # Get default exchange from config if not provided
        if exchange is None:
            from .scheduler_config import get_scheduler_config
            config = get_scheduler_config(self.db_path)
            exchange = config.get_string('indicator.exchange', 'okx')

        # Validate pairs count against config
        max_pairs = config.get_int('trader.pairs.max', 10)

        # Get existing pairs count
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as count FROM trader_pairs WHERE trader_id = ?",
            (trader_id,)
        )
        existing_count = cursor.fetchone()['count']

        # Check if adding would exceed limit
        if existing_count + len(pair_symbols) > max_pairs:
            raise ValueError(
                f"Trading pairs count exceeds limit: {existing_count + len(pair_symbols)} > {max_pairs}. "
                f"Adjust trader.pairs.max in /config"
            )

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

        Raises:
            ValueError: If intervals exceed maximum, or interval is below minimum
        """
        if not self.conn:
            self.initialize()

        # Validate intervals against config
        from .scheduler_config import get_scheduler_config

        config = get_scheduler_config(self.db_path)
        max_intervals = config.get_int('trader.intervals.max', 5)
        min_seconds = config.get_int('trader.intervals.min_seconds', 300)

        cursor = self.conn.cursor()

        # Get existing intervals count
        cursor.execute(
            "SELECT COUNT(*) as count FROM trader_intervals WHERE trader_id = ?",
            (trader_id,)
        )
        existing_count = cursor.fetchone()['count']

        # Check if adding would exceed limit
        if existing_count + len(interval_codes) > max_intervals:
            raise ValueError(
                f"Intervals count exceeds limit: {existing_count + len(interval_codes)} > {max_intervals}. "
                f"Adjust trader.intervals.max in /config"
            )

        # Validate minimum interval
        placeholders = ','.join(['?' for _ in interval_codes])
        cursor.execute(
            f"SELECT code, seconds FROM intervals WHERE code IN ({placeholders})",
            interval_codes
        )
        interval_seconds = {row['code']: row['seconds'] for row in cursor.fetchall()}

        for code in interval_codes:
            seconds = interval_seconds.get(code)
            if seconds is None:
                raise ValueError(f"Invalid interval: {code}")
            if seconds < min_seconds:
                min_readable = self._seconds_to_readable(min_seconds)
                current_readable = self._seconds_to_readable(seconds)
                raise ValueError(
                    f"Interval too small: {code} ({current_readable}) < minimum {min_readable}. "
                    f"Adjust trader.intervals.min_seconds in /config"
                )
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
