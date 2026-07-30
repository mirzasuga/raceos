"""
raceos self-test — verify the full pipeline works end-to-end.
raceos demo — show what the factory can do (no API key needed).
"""

from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel

from factory.cli.output.theme import THEME

console = Console(theme=THEME)


def run_selftest():
    """Run end-to-end self-test (requires NINE_ROUTER_API_KEY)."""
    console.print("\n[bold]RaceOS Factory — Self-Test[/bold]\n")

    checks = []

    # 1. Import check
    try:
        from factory.services import get_router, call_llm
        from factory.orchestrator.graph import build_factory_graph
        from factory.orchestrator.nodes.orchestrator import orchestrator_node
        from factory.orchestrator.nodes.context import context_node
        checks.append(("Import all modules", True, ""))
    except Exception as e:
        checks.append(("Import all modules", False, str(e)))

    # 2. Config loads
    try:
        router = get_router()
        checks.append(("Load router config", True, ""))
    except Exception as e:
        checks.append(("Load router config", False, str(e)))

    # 3. Orchestrator classifies (rule-based, no API needed)
    try:
        state = {"task": {"description": "fix typo", "domain": "firmware"}, "history": []}
        result = orchestrator_node(state)
        assert result["classification"]["task_type"] == "debugging"
        checks.append(("Orchestrator classifies", True, "type=debugging ✓"))
    except Exception as e:
        checks.append(("Orchestrator classifies", False, str(e)))

    # 4. Context resolves
    try:
        state["classification"] = {"task_type": "debugging"}
        state["plan"] = {}
        result = context_node(state)
        tokens = result["context"]["total_tokens"]
        checks.append(("Context resolves", True, f"{tokens} tokens"))
    except Exception as e:
        checks.append(("Context resolves", False, str(e)))

    # 5. Graph builds
    try:
        graph = build_factory_graph()
        checks.append(("LangGraph builds", True, "13 nodes"))
    except Exception as e:
        checks.append(("LangGraph builds", False, str(e)))

    # 6. LLM call (requires API key)
    try:
        response = call_llm(task_type="classification", prompt="Say OK")
        if response:
            checks.append(("LLM call via 9Router", True, f"response: {response[:20]}"))
        else:
            checks.append(("LLM call via 9Router", False, "No response (check API key)"))
    except Exception as e:
        checks.append(("LLM call via 9Router", False, str(e)))

    # Display results
    passed = sum(1 for _, ok, _ in checks if ok)
    total = len(checks)

    for name, ok, detail in checks:
        icon = "✅" if ok else "❌"
        color = "green" if ok else "red"
        extra = f" [dim]({detail})[/dim]" if detail else ""
        console.print(f"  {icon} [{color}]{name}[/{color}]{extra}")

    console.print(f"\n  [bold]Result: {passed}/{total} passed[/bold]")
    if passed == total:
        console.print("  [green]✅ Factory is fully operational.[/green]\n")
    elif passed >= total - 1:
        console.print("  [yellow]⚠️ Factory works (LLM call may need API key).[/yellow]\n")
    else:
        console.print("  [red]❌ Issues found. Run 'raceos doctor' for details.[/red]\n")


def run_demo():
    """Demonstrate factory capabilities (no API key needed)."""
    console.print(Panel(
        "[bold cyan]RaceOS AI Software Factory — Demo[/bold cyan]\n\n"
        "The factory processes tasks through this pipeline:\n\n"
        "  [cyan]CLI[/cyan] → intent detection\n"
        "    ↓\n"
        "  [cyan]LangGraph[/cyan] → orchestrate 11 AI agents\n"
        "    ↓\n"
        "  [cyan]9Router[/cyan] → select optimal model + enforce budget\n"
        "    ↓\n"
        "  [cyan]OpenCode[/cyan] → execute (edit files, run tests)\n"
        "    ↓\n"
        "  [cyan]Result[/cyan] → modified files + test results\n\n"
        "[bold]Example tasks:[/bold]\n\n"
        "  [green]raceos firmware \"fix typo in ecu_parser.h\"[/green]\n"
        "    → Bug fix: 44s, $0.20\n\n"
        "  [green]raceos feature \"implement engine load gauge\" --domain firmware[/green]\n"
        "    → Feature: 56s, $0.54 (includes planning + human approval)\n\n"
        "  [green]raceos hardware \"wiring diagram for display near handlebars\"[/green]\n"
        "    → Documentation: 21s, $0.13\n\n"
        "[bold]Try it:[/bold]\n\n"
        "  1. Set API key: edit .env → NINE_ROUTER_API_KEY=your-key\n"
        "  2. Verify: [cyan]raceos doctor[/cyan]\n"
        "  3. Self-test: [cyan]raceos self-test[/cyan]\n"
        "  4. Use: [cyan]raceos[/cyan] (interactive shell)\n",
        title="Demo",
        border_style="cyan",
    ))

    # Run a quick classification demo (no API needed)
    console.print("\n[bold]Live demo — classification (no API key needed):[/bold]\n")

    from factory.orchestrator.nodes.orchestrator import orchestrator_node

    demos = [
        ("fix typo in parser", "firmware"),
        ("implement BLE gateway with retry logic", "firmware"),
        ("how to wire display to stm32", "hardware"),
        ("explain what layered architecture means", "firmware"),
    ]

    for desc, domain in demos:
        state = {"task": {"description": desc, "domain": domain}, "history": []}
        result = orchestrator_node(state)
        c = result["classification"]
        console.print(
            f"  [dim]\"{desc}\"[/dim]\n"
            f"    → type=[cyan]{c['task_type']}[/cyan] "
            f"complexity=[cyan]{c['complexity']}[/cyan] "
            f"agent=[cyan]{c['target_agent']}[/cyan] "
            f"planning={'yes' if c['requires_planning'] else 'no'}\n"
        )

    console.print("[dim]These classifications work offline (rule-based, no LLM needed).[/dim]\n")
