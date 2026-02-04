"""
LogicGuard MVP - Tree Visualization Module
==========================================

Provides ASCII and Graphviz visualization of reasoning trees.

ASCII Example:
    root [✓ D1 W:28]
    └── step_1 [✓ D2 W:35] ★ PRIMARY
        ├── step_2a [✓ D5 W:70]
        └── step_2b [✗ INVALID: ERR_RULE]

Graphviz: Generates DOT format for professional diagrams.
"""

from typing import List, Dict, Optional, Any
from .types import Node, Status, VerificationResult


# ============================================================
# ASCII Tree Visualization
# ============================================================

def _build_tree_structure(nodes: List[Node]) -> Dict[Optional[str], List[Node]]:
    """Build parent -> children mapping"""
    tree: Dict[Optional[str], List[Node]] = {}
    
    for node in nodes:
        parent = node.parent_id
        if parent not in tree:
            tree[parent] = []
        tree[parent].append(node)
    
    # Sort children by legacy_idx for consistent ordering
    for children in tree.values():
        children.sort(key=lambda n: n.legacy_idx)
    
    return tree


def _status_symbol(status: Status) -> str:
    """Get status symbol"""
    symbols = {
        Status.PRIMARY_MAX: "★",
        Status.SECONDARY_MAX: "◇",
        Status.HISTORICAL_MAX: "○",
        Status.CANDIDATE: "·",
        Status.INVALID: "✗"
    }
    return symbols.get(status, "?")


def _format_node_label(node: Node, show_weight: bool = True, 
                        show_domain: bool = True) -> str:
    """Format node label for ASCII display"""
    parts = [node.node_id]
    
    if node.status == Status.INVALID:
        # Show diagnostic for invalid nodes
        diag = ""
        if node.gate:
            if not node.gate.err_complete:
                diag = "ERR"
            elif not node.gate.levels_valid:
                diag = "LEVELS"
            elif not node.gate.order_valid:
                diag = "ORDER"
        parts.append(f"[✗ {diag}]" if diag else "[✗]")
    else:
        # Valid node
        status_sym = _status_symbol(node.status)
        
        info = []
        if show_domain:
            info.append(f"D{node.raw_scores.current_domain}")
        if show_weight:
            info.append(f"W:{node.final_weight}")
        
        if info:
            parts.append(f"[{status_sym} {' '.join(info)}]")
        else:
            parts.append(f"[{status_sym}]")
        
        # Mark Primary/Secondary
        if node.status == Status.PRIMARY_MAX:
            parts.append("★ PRIMARY")
        elif node.status == Status.SECONDARY_MAX:
            parts.append("◇ SECONDARY")
    
    return " ".join(parts)


def _render_ascii_subtree(tree: Dict[Optional[str], List[Node]], 
                           parent_id: Optional[str],
                           prefix: str,
                           lines: List[str],
                           show_weight: bool = True,
                           show_domain: bool = True) -> None:
    """Recursively render subtree to ASCII lines"""
    children = tree.get(parent_id, [])
    
    for i, node in enumerate(children):
        is_last_child = (i == len(children) - 1)
        
        # Determine connector
        connector = "└── " if is_last_child else "├── "
        new_prefix = prefix + ("    " if is_last_child else "│   ")
        
        # Format and add line
        label = _format_node_label(node, show_weight, show_domain)
        lines.append(f"{prefix}{connector}{label}")
        
        # Recurse to children
        _render_ascii_subtree(tree, node.node_id, new_prefix, 
                               lines, show_weight, show_domain)


def render_ascii_tree(result: VerificationResult, 
                       show_weight: bool = True,
                       show_domain: bool = True) -> str:
    """
    Render verification result as ASCII tree.
    
    Example output:
        root [· D1 W:28]
        └── step_1 [★ D2 W:35] ★ PRIMARY
            ├── step_2a [· D5 W:70]
            └── step_2b [✗ ERR]
    
    Args:
        result: Verification result
        show_weight: Show weight values
        show_domain: Show domain numbers
    
    Returns:
        ASCII tree string
    """
    tree = _build_tree_structure(result.nodes)
    lines: List[str] = []
    
    # Find roots (nodes with no parent)
    roots = tree.get(None, [])
    
    for root in roots:
        # Add root without connector
        label = _format_node_label(root, show_weight, show_domain)
        lines.append(label)
        # Add children
        _render_ascii_subtree(tree, root.node_id, "", lines, show_weight, show_domain)
    
    return "\n".join(lines)


# ============================================================
# Graphviz DOT Visualization
# ============================================================

def _node_color(status: Status) -> str:
    """Get node fill color based on status"""
    colors = {
        Status.PRIMARY_MAX: "#90EE90",     # Light green
        Status.SECONDARY_MAX: "#87CEEB",   # Light blue
        Status.HISTORICAL_MAX: "#FFE4B5",  # Moccasin
        Status.CANDIDATE: "#F5F5F5",       # White smoke
        Status.INVALID: "#FFB6C1"          # Light pink
    }
    return colors.get(status, "#FFFFFF")


def _node_border_color(status: Status) -> str:
    """Get node border color based on status"""
    colors = {
        Status.PRIMARY_MAX: "#228B22",     # Forest green
        Status.SECONDARY_MAX: "#4169E1",   # Royal blue
        Status.HISTORICAL_MAX: "#DAA520",  # Goldenrod
        Status.CANDIDATE: "#808080",       # Gray
        Status.INVALID: "#DC143C"          # Crimson
    }
    return colors.get(status, "#000000")


def _escape_dot(text: str) -> str:
    """Escape special characters for DOT format"""
    return text.replace('"', '\\"').replace('\n', '\\n').replace('<', '&lt;').replace('>', '&gt;')


def render_graphviz(result: VerificationResult, 
                     title: str = "LogicGuard Reasoning Tree",
                     show_content: bool = False,
                     show_weight: bool = True,
                     show_gate: bool = True) -> str:
    """
    Render verification result as Graphviz DOT format.
    
    Args:
        result: Verification result
        title: Graph title
        show_content: Show node content text
        show_weight: Show weight values
        show_gate: Show gate status
    
    Returns:
        DOT format string (can be rendered with Graphviz)
    """
    lines = [
        'digraph LogicGuard {',
        '    rankdir=TB;',
        '    node [shape=box, style="filled,rounded", fontname="Arial"];',
        '    edge [fontname="Arial", fontsize=10];',
        f'    labelloc="t";',
        f'    label="{_escape_dot(title)}";',
        '',
    ]
    
    # Add nodes
    for node in result.nodes:
        # Build label parts
        label_parts = [f"<b>{_escape_dot(node.node_id)}</b>"]
        
        if show_content and node.content:
            content = node.content[:40] + "..." if len(node.content) > 40 else node.content
            label_parts.append(f"<i>{_escape_dot(content)}</i>")
        
        label_parts.append(f"D{node.raw_scores.current_domain} | {node.status.name}")
        
        if show_weight:
            label_parts.append(f"W = {node.final_weight}")
        
        if show_gate and node.gate:
            e = '✓' if node.gate.err_complete else '✗'
            l = '✓' if node.gate.levels_valid else '✗'
            o = '✓' if node.gate.order_valid else '✗'
            label_parts.append(f"Gate: [{e}|{l}|{o}]")
        
        label = "<br/>".join(label_parts)
        
        # Styling
        fill_color = _node_color(node.status)
        border_color = _node_border_color(node.status)
        penwidth = "3" if node.status == Status.PRIMARY_MAX else "1"
        
        lines.append(
            f'    "{node.node_id}" ['
            f'label=<{label}>, '
            f'fillcolor="{fill_color}", '
            f'color="{border_color}", '
            f'penwidth={penwidth}'
            f'];'
        )
    
    lines.append('')
    
    # Add edges
    for node in result.nodes:
        if node.parent_id:
            if node.status == Status.INVALID:
                edge_style = 'style=dashed, color="#DC143C"'
            elif node.status == Status.PRIMARY_MAX:
                edge_style = 'style=bold, color="#228B22", penwidth=2'
            else:
                edge_style = 'color="#808080"'
            
            lines.append(f'    "{node.parent_id}" -> "{node.node_id}" [{edge_style}];')
    
    lines.append('')
    
    # Add legend
    lines.extend([
        '    subgraph cluster_legend {',
        '        label="Legend";',
        '        fontsize=10;',
        '        style=dashed;',
        '        node [shape=plaintext, style=""];',
        '        legend [label=<',
        '            <table border="0" cellborder="1" cellspacing="0">',
        '            <tr><td bgcolor="#90EE90">★ PrimaryMax</td></tr>',
        '            <tr><td bgcolor="#87CEEB">◇ SecondaryMax</td></tr>',
        '            <tr><td bgcolor="#FFE4B5">○ HistoricalMax</td></tr>',
        '            <tr><td bgcolor="#F5F5F5">· Candidate</td></tr>',
        '            <tr><td bgcolor="#FFB6C1">✗ Invalid (Zero-Gate)</td></tr>',
        '            </table>',
        '        >];',
        '    }',
    ])
    
    lines.append('}')
    
    return '\n'.join(lines)


def save_graphviz(result: VerificationResult, 
                   filepath: str,
                   **kwargs) -> str:
    """Save Graphviz DOT to file."""
    dot = render_graphviz(result, **kwargs)
    with open(filepath, 'w') as f:
        f.write(dot)
    return dot


# ============================================================
# Summary with Tree
# ============================================================

def print_tree(result: VerificationResult, **kwargs) -> None:
    """Print ASCII tree to stdout"""
    print(render_ascii_tree(result, **kwargs))


def full_report(result: VerificationResult) -> str:
    """Generate full report with ASCII tree"""
    lines = [
        "=" * 60,
        "LOGICGUARD VERIFICATION REPORT",
        "=" * 60,
        "",
        f"Total nodes:  {len(result.nodes)}",
        f"Valid:        {len(result.nodes) - result.invalid_count}",
        f"Invalid:      {result.invalid_count}",
        f"Primary:      {result.primary_max.node_id if result.primary_max else 'None'}",
        f"Secondary:    {[n.node_id for n in result.secondary_max] or 'None'}",
        "",
        "-" * 60,
        "REASONING TREE:",
        "-" * 60,
        "",
        render_ascii_tree(result),
        "",
        "-" * 60,
        "LEGEND: ★=Primary  ◇=Secondary  ○=Historical  ·=Candidate  ✗=Invalid",
        "=" * 60,
    ]
    return "\n".join(lines)


def print_full_report(result: VerificationResult) -> None:
    """Print full report to stdout"""
    print(full_report(result))
