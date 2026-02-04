"""
Regulus AI - Rich Tree Renderer
================================

Rich-based visual rendering of reasoning trees with colored status markers.

Visual markers:
    [green]★[/green]  PrimaryMax
    [red]✗[/red]      Invalid (with gate error code)
    [yellow]○[/yellow] SecondaryMax
    [dim]·[/dim]       Candidate
    [dim cyan]○[/dim cyan] HistoricalMax
"""

from __future__ import annotations

from typing import Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from ..core.types import Domain, IntegrityGate, Node, Status, VerificationResult
from .console import _build_tree_structure, _status_symbol


# Status -> Rich style mapping
_STATUS_STYLES: Dict[Status, str] = {
    Status.PRIMARY_MAX: "bold green",
    Status.SECONDARY_MAX: "yellow",
    Status.HISTORICAL_MAX: "dim cyan",
    Status.CANDIDATE: "dim",
    Status.INVALID: "bold red",
}


class ReasoningTreeRenderer:
    """Rich-based visual renderer for Regulus reasoning trees."""

    def __init__(self) -> None:
        self._console = Console()

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------

    def render_final(self, result: VerificationResult) -> Tree:
        """
        Build a complete Rich Tree from a VerificationResult.

        Walks the node tree using the existing _build_tree_structure()
        helper and creates a rich.tree.Tree with colored labels.
        """
        tree_map = _build_tree_structure(result.nodes)
        roots = tree_map.get(None, [])

        root_tree = Tree("[bold]Reasoning Chain[/bold]")

        for root_node in roots:
            label = self._format_rich_label(root_node)
            branch = root_tree.add(label)
            self._add_children_recursive(branch, tree_map, root_node.node_id)

        return root_tree

    def show_domain_panel(self, current_domain: Domain) -> Panel:
        """Create a Panel showing domain name, guiding question, and trigger."""
        content = Text()
        content.append(f"{current_domain.name}\n", style="bold")
        content.append(f"Question: {current_domain.question}\n", style="italic")
        content.append(
            f"Failure trigger: {current_domain.zero_gate_trigger}",
            style="dim red",
        )
        return Panel(content, title="Current Domain", border_style="blue")

    def render_to_console(self, result: VerificationResult) -> None:
        """Print the full Rich tree with header and summary to the console."""
        console = self._console

        # Header panel
        if result.primary_max:
            status_text = "VALID — PrimaryMax found"
            status_style = "green"
        else:
            status_text = "FAILED — No PrimaryMax"
            status_style = "red"

        console.print(
            Panel(
                Text(
                    f"Regulus AI Verification: {status_text}",
                    style=f"bold {status_style}",
                ),
                border_style=status_style,
            )
        )

        # Reasoning tree
        tree = self.render_final(result)
        console.print(tree)

        # Summary table
        table = Table(title="Verification Summary")
        table.add_column("Property", style="cyan")
        table.add_column("Value")
        table.add_row("Total nodes", str(len(result.nodes)))
        table.add_row("Valid", str(len(result.nodes) - result.invalid_count))
        table.add_row("Invalid", str(result.invalid_count))
        table.add_row(
            "Primary",
            result.primary_max.node_id if result.primary_max else "None",
        )
        table.add_row(
            "Secondary",
            ", ".join(n.node_id for n in result.secondary_max) or "None",
        )
        console.print(table)

        # Legend
        legend = Text()
        legend.append("Legend: ", style="bold")
        legend.append("★ Primary  ", style="bold green")
        legend.append("○ Secondary  ", style="yellow")
        legend.append("○ Historical  ", style="dim cyan")
        legend.append("· Candidate  ", style="dim")
        legend.append("✗ Invalid", style="bold red")
        console.print(Panel(legend, border_style="dim"))

    # ----------------------------------------------------------
    # Private helpers
    # ----------------------------------------------------------

    def _format_rich_label(self, node: Node) -> Text:
        """Format a node into a styled Rich Text label."""
        style = _STATUS_STYLES.get(node.status, "")
        symbol = _status_symbol(node.status)

        if node.status == Status.INVALID:
            err_code = self._gate_error_code(node.gate)
            label = f"{symbol} {node.node_id} [ERR: {err_code}] W:0"
        else:
            domain_str = f"D{node.raw_scores.current_domain}"
            label = f"{symbol} {node.node_id} [{domain_str} W:{node.final_weight}]"
            if node.status == Status.PRIMARY_MAX:
                label += " PRIMARY"
            elif node.status == Status.SECONDARY_MAX:
                label += " SECONDARY"
            elif node.status == Status.HISTORICAL_MAX:
                label += " HISTORICAL"

        return Text(label, style=style)

    def _add_children_recursive(
        self,
        rich_branch: Tree,
        tree_map: Dict[Optional[str], List[Node]],
        parent_id: str,
    ) -> None:
        """Recursively add child nodes to a Rich Tree branch."""
        children = tree_map.get(parent_id, [])
        for child in children:
            label = self._format_rich_label(child)
            sub_branch = rich_branch.add(label)
            self._add_children_recursive(sub_branch, tree_map, child.node_id)

    @staticmethod
    def _gate_error_code(gate: IntegrityGate | None) -> str:
        """Extract a short error code from a failed gate."""
        if gate is None:
            return "NONE"
        if not gate.err_complete:
            return "ERR"
        if not gate.levels_valid:
            return "LEVELS"
        if not gate.order_valid:
            return "ORDER"
        return "UNKNOWN"
