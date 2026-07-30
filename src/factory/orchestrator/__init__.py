# LangGraph workflow orchestration.
"""
Factory orchestrator — the LangGraph DAG that connects all AI agents.

Usage:
    from factory.orchestrator.graph import build_factory_graph, invoke_factory

    # Build graph
    graph = build_factory_graph()

    # Or use convenience function
    result = invoke_factory("fix typo in ecu_parser.h", domain="firmware")
"""

from factory.orchestrator.graph import build_factory_graph, invoke_factory
from factory.orchestrator.state import FactoryState

__all__ = ["build_factory_graph", "invoke_factory", "FactoryState"]
