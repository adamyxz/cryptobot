"""Activity Log Database Module

SQLite database for logging trader decision and optimization processes.
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime


class ActivityLogDatabase:
    """SQLite database for logging trader activity (decisions and optimizations)"""

    def __init__(self, db_path: str = None):
        """Initialize the activity log database

        Args:
            db_path: Path to SQLite database file. Defaults to activity_logs.db in project root.
        """
        if db_path is None:
            # Default to activity_logs.db in the project root
            project_root = Path(__file__).parent.parent
            db_path = str(project_root / "activity_logs.db")

        self.db_path = db_path
        self.conn = None

    def initialize(self):
        """Initialize database and create tables if they don't exist"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

        cursor = self.conn.cursor()

        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Create decision_logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trader_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                phase1_prompt TEXT,
                phase1_response TEXT,
                phase1_thinking TEXT,
                phase2_prompt TEXT,
                phase2_response TEXT,
                phase2_thinking TEXT,
                final_decision TEXT,
                indicator_data TEXT,
                market_context TEXT,
                positions_context TEXT,
                error_message TEXT,
                execution_time_ms REAL,
                status TEXT,
                trigger_source TEXT,
                metadata TEXT
            )
        """)

        # Create optimization_logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS optimization_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trader_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                before_strategy TEXT,
                after_strategy TEXT,
                performance_data TEXT,
                position_history TEXT,
                optimization_prompt TEXT,
                claude_response TEXT,
                changes_made TEXT,
                error_message TEXT,
                execution_time_ms REAL,
                status TEXT,
                metadata TEXT
            )
        """)

        # Create indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_decision_trader_id ON decision_logs(trader_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_decision_timestamp ON decision_logs(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_decision_status ON decision_logs(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_optimization_trader_id ON optimization_logs(trader_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_optimization_timestamp ON optimization_logs(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_optimization_status ON optimization_logs(status)
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

    # =========================================================================
    # Decision Logging Methods
    # =========================================================================

    def log_decision(
        self,
        trader_id: str,
        phase1_prompt: str = None,
        phase1_response: str = None,
        phase1_thinking: str = None,
        phase2_prompt: str = None,
        phase2_response: str = None,
        phase2_thinking: str = None,
        final_decision: str = None,
        indicator_data: Dict = None,
        market_context: Dict = None,
        positions_context: Dict = None,
        error_message: str = None,
        execution_time_ms: float = None,
        status: str = "SUCCESS",
        trigger_source: str = "manual",
        metadata: Dict = None
    ) -> int:
        """Log a decision process

        Args:
            trader_id: Trader ID
            phase1_prompt: Initial phase prompt sent to AI
            phase1_response: AI's initial analysis response
            phase1_thinking: AI's detailed thinking process in phase 1
            phase2_prompt: Final decision prompt sent to AI
            phase2_response: AI's final decision response
            phase2_thinking: AI's detailed thinking process in phase 2
            final_decision: The actual decision made (e.g., "OPEN_LONG BTC", "HOLD")
            indicator_data: Market/indicator data collected (dict)
            market_context: Market data at decision time (dict)
            positions_context: Open positions at decision time (dict)
            error_message: Error message if decision failed
            execution_time_ms: Time taken to execute decision in milliseconds
            status: Status of the decision (SUCCESS, ERROR, PARTIAL)
            trigger_source: What triggered this decision (manual, scheduler, trigger)
            metadata: Additional metadata (dict)

        Returns:
            The ID of the inserted log entry
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO decision_logs (
                    trader_id, phase1_prompt, phase1_response, phase1_thinking,
                    phase2_prompt, phase2_response, phase2_thinking,
                    final_decision, indicator_data, market_context, positions_context,
                    error_message, execution_time_ms, status, trigger_source, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trader_id,
                phase1_prompt,
                phase1_response,
                phase1_thinking,
                phase2_prompt,
                phase2_response,
                phase2_thinking,
                final_decision,
                json.dumps(indicator_data) if indicator_data else None,
                json.dumps(market_context) if market_context else None,
                json.dumps(positions_context) if positions_context else None,
                error_message,
                execution_time_ms,
                status,
                trigger_source,
                json.dumps(metadata) if metadata else None
            ))

            self.conn.commit()
            return cursor.lastrowid
        except Exception as e:
            self.conn.rollback()
            raise e

    def get_decision_logs(
        self,
        trader_id: str = None,
        limit: int = 100,
        offset: int = 0,
        status: str = None
    ) -> List[Dict[str, Any]]:
        """Get decision logs with optional filtering

        Args:
            trader_id: Filter by trader ID (optional)
            limit: Maximum number of logs to return
            offset: Number of logs to skip
            status: Filter by status (optional)

        Returns:
            List of decision log dictionaries
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()

        # Build query
        query = "SELECT * FROM decision_logs WHERE 1=1"
        params = []

        if trader_id:
            query += " AND trader_id = ?"
            params.append(trader_id)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [self._decision_row_to_dict(row) for row in rows]

    def get_decision_log(self, log_id: int) -> Optional[Dict[str, Any]]:
        """Get a single decision log by ID

        Args:
            log_id: Log entry ID

        Returns:
            Decision log dictionary or None if not found
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM decision_logs WHERE id = ?", (log_id,))
        row = cursor.fetchone()

        return self._decision_row_to_dict(row) if row else None

    def _decision_row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a decision log database row to a dictionary

        Args:
            row: SQLite row object

        Returns:
            Dictionary with parsed JSON fields
        """
        log_dict = dict(row)

        # Parse JSON fields
        json_fields = ['indicator_data', 'market_context', 'positions_context', 'metadata']
        for field in json_fields:
            if log_dict.get(field):
                try:
                    log_dict[field] = json.loads(log_dict[field])
                except json.JSONDecodeError:
                    log_dict[field] = None
            else:
                log_dict[field] = None

        return log_dict

    # =========================================================================
    # Optimization Logging Methods
    # =========================================================================

    def log_optimization(
        self,
        trader_id: str,
        before_strategy: Dict = None,
        after_strategy: Dict = None,
        performance_data: Dict = None,
        position_history: List = None,
        optimization_prompt: str = None,
        claude_response: str = None,
        changes_made: List = None,
        error_message: str = None,
        execution_time_ms: float = None,
        status: str = "SUCCESS",
        metadata: Dict = None
    ) -> int:
        """Log an optimization process

        Args:
            trader_id: Trader ID
            before_strategy: Strategy before optimization (dict)
            after_strategy: Strategy after optimization (dict)
            performance_data: Performance summary (dict)
            position_history: List of position details (list)
            optimization_prompt: The prompt sent to Claude Code
            claude_response: Claude's analysis and suggestions
            changes_made: List of changes applied (list of strings)
            error_message: Error message if optimization failed
            execution_time_ms: Time taken to execute optimization in milliseconds
            status: Status of the optimization (SUCCESS, ERROR, NO_CHANGES)
            metadata: Additional metadata (dict)

        Returns:
            The ID of the inserted log entry
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO optimization_logs (
                    trader_id, before_strategy, after_strategy, performance_data,
                    position_history, optimization_prompt, claude_response,
                    changes_made, error_message, execution_time_ms, status, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trader_id,
                json.dumps(before_strategy) if before_strategy else None,
                json.dumps(after_strategy) if after_strategy else None,
                json.dumps(performance_data) if performance_data else None,
                json.dumps(position_history) if position_history else None,
                optimization_prompt,
                claude_response,
                json.dumps(changes_made) if changes_made else None,
                error_message,
                execution_time_ms,
                status,
                json.dumps(metadata) if metadata else None
            ))

            self.conn.commit()
            return cursor.lastrowid
        except Exception as e:
            self.conn.rollback()
            raise e

    def get_optimization_logs(
        self,
        trader_id: str = None,
        limit: int = 100,
        offset: int = 0,
        status: str = None
    ) -> List[Dict[str, Any]]:
        """Get optimization logs with optional filtering

        Args:
            trader_id: Filter by trader ID (optional)
            limit: Maximum number of logs to return
            offset: Number of logs to skip
            status: Filter by status (optional)

        Returns:
            List of optimization log dictionaries
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()

        # Build query
        query = "SELECT * FROM optimization_logs WHERE 1=1"
        params = []

        if trader_id:
            query += " AND trader_id = ?"
            params.append(trader_id)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [self._optimization_row_to_dict(row) for row in rows]

    def get_optimization_log(self, log_id: int) -> Optional[Dict[str, Any]]:
        """Get a single optimization log by ID

        Args:
            log_id: Log entry ID

        Returns:
            Optimization log dictionary or None if not found
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM optimization_logs WHERE id = ?", (log_id,))
        row = cursor.fetchone()

        return self._optimization_row_to_dict(row) if row else None

    def _optimization_row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert an optimization log database row to a dictionary

        Args:
            row: SQLite row object

        Returns:
            Dictionary with parsed JSON fields
        """
        log_dict = dict(row)

        # Parse JSON fields
        json_fields = ['before_strategy', 'after_strategy', 'performance_data', 'position_history', 'changes_made', 'metadata']
        for field in json_fields:
            if log_dict.get(field):
                try:
                    log_dict[field] = json.loads(log_dict[field])
                except json.JSONDecodeError:
                    log_dict[field] = None
            else:
                log_dict[field] = None

        return log_dict

    # =========================================================================
    # Statistics and Analysis
    # =========================================================================

    def get_decision_statistics(self, trader_id: str = None) -> Dict[str, Any]:
        """Get decision statistics

        Args:
            trader_id: Filter by trader ID (optional)

        Returns:
            Dictionary with decision statistics
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()

        # Build query
        if trader_id:
            cursor.execute("""
                SELECT
                    COUNT(*) as total_decisions,
                    SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful_decisions,
                    SUM(CASE WHEN status = 'ERROR' THEN 1 ELSE 0 END) as failed_decisions,
                    AVG(execution_time_ms) as avg_execution_time_ms,
                    MAX(timestamp) as last_decision_time
                FROM decision_logs
                WHERE trader_id = ?
            """, (trader_id,))
        else:
            cursor.execute("""
                SELECT
                    COUNT(*) as total_decisions,
                    SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful_decisions,
                    SUM(CASE WHEN status = 'ERROR' THEN 1 ELSE 0 END) as failed_decisions,
                    AVG(execution_time_ms) as avg_execution_time_ms,
                    MAX(timestamp) as last_decision_time
                FROM decision_logs
            """)

        row = cursor.fetchone()

        return {
            'total_decisions': row['total_decisions'] or 0,
            'successful_decisions': row['successful_decisions'] or 0,
            'failed_decisions': row['failed_decisions'] or 0,
            'avg_execution_time_ms': row['avg_execution_time_ms'] or 0,
            'last_decision_time': row['last_decision_time']
        }

    def get_optimization_statistics(self, trader_id: str = None) -> Dict[str, Any]:
        """Get optimization statistics

        Args:
            trader_id: Filter by trader ID (optional)

        Returns:
            Dictionary with optimization statistics
        """
        if not self.conn:
            self.initialize()

        cursor = self.conn.cursor()

        # Build query
        if trader_id:
            cursor.execute("""
                SELECT
                    COUNT(*) as total_optimizations,
                    SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful_optimizations,
                    SUM(CASE WHEN status = 'ERROR' THEN 1 ELSE 0 END) as failed_optimizations,
                    SUM(CASE WHEN status = 'NO_CHANGES' THEN 1 ELSE 0 END) as no_changes_optimizations,
                    AVG(execution_time_ms) as avg_execution_time_ms,
                    MAX(timestamp) as last_optimization_time
                FROM optimization_logs
                WHERE trader_id = ?
            """, (trader_id,))
        else:
            cursor.execute("""
                SELECT
                    COUNT(*) as total_optimizations,
                    SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful_optimizations,
                    SUM(CASE WHEN status = 'ERROR' THEN 1 ELSE 0 END) as failed_optimizations,
                    SUM(CASE WHEN status = 'NO_CHANGES' THEN 1 ELSE 0 END) as no_changes_optimizations,
                    AVG(execution_time_ms) as avg_execution_time_ms,
                    MAX(timestamp) as last_optimization_time
                FROM optimization_logs
            """)

        row = cursor.fetchone()

        return {
            'total_optimizations': row['total_optimizations'] or 0,
            'successful_optimizations': row['successful_optimizations'] or 0,
            'failed_optimizations': row['failed_optimizations'] or 0,
            'no_changes_optimizations': row['no_changes_optimizations'] or 0,
            'avg_execution_time_ms': row['avg_execution_time_ms'] or 0,
            'last_optimization_time': row['last_optimization_time']
        }
