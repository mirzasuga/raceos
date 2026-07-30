# OpenCode executor integration.
"""
Execution layer for the AI Software Factory.

Spawns OpenCode as a subprocess with structured context,
domain-specific constraints, and controlled tool access.

Usage:
    from factory.executor.client import OpenCodeClient
    from factory.executor.contracts import ExecutionRequest, Operation
    from factory.executor.adapters import get_adapter

    adapter = get_adapter("firmware")
    client = OpenCodeClient()
    result = client.execute(ExecutionRequest(
        task_id="TASK-001",
        operation=Operation.IMPLEMENT,
        description="Add error handling to parser",
        constraints=adapter.constraints,
        working_dir=adapter.working_dir,
    ))
"""

from factory.executor.adapters import get_adapter, list_domains
from factory.executor.client import OpenCodeClient
from factory.executor.contracts import ExecutionRequest, ExecutionResult, Operation

__all__ = [
    "OpenCodeClient",
    "ExecutionRequest",
    "ExecutionResult",
    "Operation",
    "get_adapter",
    "list_domains",
]
