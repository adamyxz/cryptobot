"""Scheduler Configuration Management

Manages scheduler configuration stored in database.
"""

import sqlite3
import json
from pathlib import Path
from typing import Any, Optional


class SchedulerConfig:
    """Scheduler configuration manager with database storage"""

    # Default configuration values
    DEFAULT_CONFIG = {
        # Scheduler settings
        'scheduler.check_interval': ('30', 'int', 'Check interval in seconds'),
        'scheduler.max_concurrent_tasks': ('3', 'int', 'Maximum concurrent tasks'),
        'scheduler.task_timeout_minutes': ('10', 'int', 'Task timeout in minutes'),

        # Trigger settings
        'trigger.time.enabled': ('true', 'bool', 'Enable time-based triggers'),
        'trigger.price.enabled': ('true', 'bool', 'Enable price-based triggers'),
        'trigger.price.change_threshold': ('0.04', 'float', 'Price change threshold (4%)'),

        # Indicator settings
        'indicator.limit': ('0', 'int', 'Indicator data limit (0 = unlimited)'),
        'indicator.exchange': ('okx', 'string', 'Default exchange for indicators (okx, binance, etc.)'),

        # Optimization settings
        'optimize.enabled': ('false', 'bool', 'Enable automatic optimization'),
        'optimize.min_positions': ('5', 'int', 'Minimum positions before optimization'),
        'optimize.interval_hours': ('24', 'int', 'Optimization interval in hours'),

        # Priority settings
        'priority.low_balance_threshold': ('5000', 'float', 'Low balance threshold'),
        'priority.low_balance_priority': ('2', 'int', 'Priority for low balance traders'),
        'priority.scalping_priority': ('3', 'int', 'Priority for scalping traders'),

        # Trader constraints
        'trader.pairs.max': ('10', 'int', 'Maximum number of trading pairs per trader'),
        'trader.intervals.min_seconds': ('300', 'int', 'Minimum interval in seconds (5 minutes)'),
        'trader.intervals.max': ('5', 'int', 'Maximum number of intervals per trader'),
    }

    def __init__(self, db_path: str = None):
        """Initialize scheduler config

        Args:
            db_path: Path to database file. Defaults to traders.db in project root.
        """
        if db_path is None:
            project_root = Path(__file__).parent.parent
            db_path = str(project_root / "traders.db")

        self.db_path = db_path
        self.conn = None
        self._init_config_table()
        self._load_defaults()

    def _init_config_table(self):
        """Create configuration table if it doesn't exist"""
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                type TEXT NOT NULL,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()

    def _load_defaults(self):
        """Load default configuration values"""
        cursor = self.conn.cursor()

        for key, (default_value, value_type, description) in self.DEFAULT_CONFIG.items():
            # Check if key exists
            cursor.execute("SELECT value FROM scheduler_config WHERE key = ?", (key,))
            if cursor.fetchone() is None:
                # Insert default value
                cursor.execute("""
                    INSERT INTO scheduler_config (key, value, type, description)
                    VALUES (?, ?, ?, ?)
                """, (key, default_value, value_type, description))

        self.conn.commit()

        # Force disable auto-optimization (it causes UI issues)
        # Users can manually enable it via /config if needed
        cursor.execute("""
            UPDATE scheduler_config
            SET value = 'false'
            WHERE key = 'optimize.enabled'
        """)
        self.conn.commit()

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT value, type FROM scheduler_config WHERE key = ?", (key,))
        row = cursor.fetchone()

        if row is None:
            return default

        value, value_type = row
        return self._parse_value(value, value_type)

    def set(self, key: str, value: Any, value_type: str = None, description: str = None):
        """Set configuration value

        Args:
            key: Configuration key
            value: Configuration value
            value_type: Type of value ('int', 'float', 'bool', 'string'). Auto-detected if None.
            description: Optional description
        """
        cursor = self.conn.cursor()

        # Auto-detect type if not specified
        if value_type is None:
            if isinstance(value, bool):
                value_type = 'bool'
            elif isinstance(value, int):
                value_type = 'int'
            elif isinstance(value, float):
                value_type = 'float'
            else:
                value_type = 'string'

        # Convert value to string
        str_value = self._format_value(value, value_type)

        # Check if key exists
        cursor.execute("SELECT key FROM scheduler_config WHERE key = ?", (key,))
        exists = cursor.fetchone() is not None

        if exists:
            # Update existing
            if description:
                cursor.execute("""
                    UPDATE scheduler_config
                    SET value = ?, type = ?, description = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE key = ?
                """, (str_value, value_type, description, key))
            else:
                cursor.execute("""
                    UPDATE scheduler_config
                    SET value = ?, type = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE key = ?
                """, (str_value, value_type, key))
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO scheduler_config (key, value, type, description)
                VALUES (?, ?, ?, ?)
            """, (key, str_value, value_type, description or ''))

        self.conn.commit()

    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer configuration value"""
        value = self.get(key)
        if value is None:
            return default
        return int(value)

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get float configuration value"""
        value = self.get(key)
        if value is None:
            return default
        return float(value)

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value"""
        value = self.get(key)
        if value is None:
            return default
        return str(value).lower() in ('true', '1', 'yes', 'on')

    def get_string(self, key: str, default: str = '') -> str:
        """Get string configuration value"""
        value = self.get(key)
        if value is None:
            return default
        return str(value)

    def get_all(self) -> dict:
        """Get all configuration values

        Returns:
            Dict mapping keys to (value, type, description) tuples
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT key, value, type, description FROM scheduler_config")
        rows = cursor.fetchall()

        result = {}
        for key, value, value_type, description in rows:
            parsed_value = self._parse_value(value, value_type)
            result[key] = {
                'value': parsed_value,
                'type': value_type,
                'description': description
            }

        return result

    def delete(self, key: str) -> bool:
        """Delete a configuration key

        Args:
            key: Configuration key to delete

        Returns:
            True if key was deleted, False if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM scheduler_config WHERE key = ?", (key,))
        self.conn.commit()
        return cursor.rowcount > 0

    def reset_to_defaults(self):
        """Reset all configuration to defaults"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM scheduler_config")
        self.conn.commit()
        self._load_defaults()

    def _parse_value(self, value: str, value_type: str) -> Any:
        """Parse string value to appropriate type

        Args:
            value: String value
            value_type: Type of value

        Returns:
            Parsed value
        """
        if value_type == 'int':
            return int(value)
        elif value_type == 'float':
            return float(value)
        elif value_type == 'bool':
            return value.lower() in ('true', '1', 'yes', 'on')
        else:
            return value

    def _format_value(self, value: Any, value_type: str) -> str:
        """Format value to string for storage

        Args:
            value: Value to format
            value_type: Type of value

        Returns:
            String representation
        """
        if value_type == 'bool':
            return 'true' if value else 'false'
        else:
            return str(value)

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Global instance
_default_config: Optional[SchedulerConfig] = None


def get_scheduler_config(db_path: str = None) -> SchedulerConfig:
    """Get the global scheduler configuration instance

    Args:
        db_path: Database path (only used on first call)

    Returns:
        SchedulerConfig instance
    """
    global _default_config
    if _default_config is None:
        _default_config = SchedulerConfig(db_path)
    return _default_config
