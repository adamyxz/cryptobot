"""Priority Queue for Trader Tasks

Implements a priority-based task queue for scheduling trader decisions and optimizations.
"""

import heapq
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass(order=True)
class PriorityTask:
    """Priority task for trader scheduling

    Attributes:
        priority: Task priority (lower number = higher priority, 1-10)
        trader_id: Trader identifier
        action: Action type ('decide' or 'optimize')
        created_at: Task creation timestamp
        metadata: Additional metadata (trigger reason, etc.)
    """

    priority: int
    trader_id: str = field(compare=False)
    action: str = field(compare=False)
    created_at: datetime = field(compare=False, default_factory=datetime.now)
    metadata: Dict[str, Any] = field(compare=False, default_factory=dict)

    def __repr__(self) -> str:
        return (f"PriorityTask(trader_id={self.trader_id}, action={self.action}, "
                f"priority={self.priority}, trigger={self.metadata.get('trigger', 'N/A')})")


class TraderPriorityQueue:
    """Priority queue for managing trader tasks

    Tasks are executed in priority order (lower priority number first).
    Tasks with the same priority are executed in FIFO order.
    """

    def __init__(self):
        """Initialize the priority queue"""
        self.queue: List[tuple] = []  # (priority, counter, task)
        self.task_counter = 0  # Ensures FIFO for same-priority tasks

    def add_task(
        self,
        trader_id: str,
        action: str,
        priority: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PriorityTask:
        """Add a task to the queue

        Args:
            trader_id: Trader ID
            action: 'decide' or 'optimize'
            priority: Priority level (1-10, 1=highest). If None, auto-calculated.
            metadata: Additional metadata (e.g., {'trigger': 'price_change'})

        Returns:
            The created PriorityTask object
        """
        if priority is None:
            priority = self._calculate_priority(trader_id, action)

        # Validate priority range
        priority = max(1, min(10, priority))

        task = PriorityTask(
            priority=priority,
            trader_id=trader_id,
            action=action,
            metadata=metadata or {}
        )

        # Use counter as second sort key for FIFO ordering
        heapq.heappush(self.queue, (task.priority, self.task_counter, task))
        self.task_counter += 1

        return task

    def get_next_task(self) -> Optional[PriorityTask]:
        """Get the next task from the queue

        Returns:
            PriorityTask object or None if queue is empty
        """
        if not self.queue:
            return None

        _, _, task = heapq.heappop(self.queue)
        return task

    def peek(self) -> Optional[PriorityTask]:
        """Look at the next task without removing it

        Returns:
            PriorityTask object or None if queue is empty
        """
        if not self.queue:
            return None

        return self.queue[0][2]

    def is_empty(self) -> bool:
        """Check if queue is empty

        Returns:
            True if queue has no tasks
        """
        return len(self.queue) == 0

    def size(self) -> int:
        """Get current queue size

        Returns:
            Number of tasks in queue
        """
        return len(self.queue)

    def clear(self):
        """Clear all tasks from the queue"""
        self.queue.clear()
        self.task_counter = 0

    def get_tasks_by_trader(self, trader_id: str) -> List[PriorityTask]:
        """Get all tasks for a specific trader

        Args:
            trader_id: Trader ID

        Returns:
            List of tasks for the trader (not removed from queue)
        """
        return [task for _, _, task in self.queue if task.trader_id == trader_id]

    def remove_trader_tasks(self, trader_id: str) -> int:
        """Remove all tasks for a specific trader

        Args:
            trader_id: Trader ID

        Returns:
            Number of tasks removed
        """
        original_size = len(self.queue)
        self.queue = [(p, c, t) for p, c, t in self.queue
                      if t.trader_id != trader_id]
        # Rebuild heap since we modified the list
        heapq.heapify(self.queue)
        return original_size - len(self.queue)

    def _calculate_priority(self, trader_id: str, action: str) -> int:
        """Calculate task priority based on trader and action

        Args:
            trader_id: Trader ID
            action: 'decide' or 'optimize'

        Returns:
            Priority level (1-10)
        """
        # Base priorities
        if action == 'decide':
            base_priority = 5
        elif action == 'optimize':
            base_priority = 8  # Optimization is lower priority
        else:
            base_priority = 5

        # TODO: Enhance with trader-specific logic
        # Could consider:
        # - Trader equity (low balance = higher priority)
        # - Trading style (scalping = higher priority)
        # - Historical performance
        # - Time since last decision

        return base_priority

    def get_queue_summary(self) -> Dict[str, Any]:
        """Get a summary of queue status

        Returns:
            Dictionary with queue statistics
        """
        tasks_by_action = {'decide': 0, 'optimize': 0}
        tasks_by_trader = {}

        for _, _, task in self.queue:
            # Count by action
            action = task.action
            if action not in tasks_by_action:
                tasks_by_action[action] = 0
            tasks_by_action[action] += 1

            # Count by trader
            trader = task.trader_id
            if trader not in tasks_by_trader:
                tasks_by_trader[trader] = 0
            tasks_by_trader[trader] += 1

        return {
            'total_tasks': len(self.queue),
            'tasks_by_action': tasks_by_action,
            'tasks_by_trader': tasks_by_trader,
            'next_task': str(self.peek()) if not self.is_empty() else None
        }
