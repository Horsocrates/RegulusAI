#!/usr/bin/env python3
"""
Regulus Logic Censor — Conference Demo
=======================================

Interactive Rich CLI demonstrating Coq-verified fallacy detection.

156 fallacies | 6 domains | 23 failure modes | 509 Coq theorems

Usage:
    uv run python -m regulus.fallacies.demo_cli              # Interactive mode
    uv run python -m regulus.fallacies.demo_cli --examples   # Run showcase examples
    uv run python -m regulus.fallacies.demo_cli --stats      # Show taxonomy stats

Author: Regulus AI
Based on: theory-of-systems-coq (Horsocrates)
"""

from __future__ import annotations

import sys
import time
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from rich.columns import Columns
from rich.rule import Rule
from rich.align import Align
from rich.padding import Padding
from rich import box

from regulus.fallacies.taxonomy import (
    FALLACIES,
    FALLACIES_BY_DOMAIN,
    FALLACIES_BY_TYPE,
    FAILURE_MODES,
    Domain,
    Fallacy,
    FallacyType,
    FailureMode,
    Severity,
)
from regulus.fallacies.detector import (
    DetectionResult,
    Signals,
    detect,
    detect_all,
    extract_signals,
)

import os
import sys as _sys

# Force UTF-8 on Windows
if _sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        _sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        _sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

console = Console(force_terminal=True)


# =============================================================================
#                           BRANDING & HEADER
# =============================================================================

LOGO = """[bold cyan]
  REGULUS
  Logic Censor[/bold cyan]"""

LOGO_WIDE = r"""[bold cyan]
  ____  _____ ____ _   _ _    _   _ ____
 |  _ \| ____/ ___| | | | |  | | | / ___|
 | |_) |  _|| |  _| | | | |  | | | \___ \
 |  _ <| |__| |_| | |_| | |__| |_| |___) |
 |_| \_\_____\____|\___/|_____\___/|____/[/bold cyan]"""

SUBTITLE = (
    "[dim]Logic Censor \u2014 Coq-Verified Fallacy Detection[/dim]"
)
SUBTITLE2 = (
    "[dim cyan]156 fallacies | 6 domains | 23 failure modes | 509 theorems[/dim cyan]"
)


def print_header():
    console.print()
    try:
        console.print(LOGO_WIDE)
    except Exception:
        console.print(LOGO)
    console.print(Align.center(SUBTITLE))
    console.print(Align.center(SUBTITLE2))
    console.print()


# =============================================================================
#                           SIGNAL DISPLAY
# =============================================================================

def _signal_icon(val: bool) -> str:
    return "[green]●[/green]" if val else "[dim]○[/dim]"


def render_signals(sig: Signals) -> Panel:
    """Render signal extraction results as a panel."""
    lines = []
    signal_map = [
        ("attacks_person", "Attacks Person", sig.attacks_person),
        ("addresses_argument", "Addresses Argument", sig.addresses_argument),
        ("considers_counter", "Counter-Evidence", sig.considers_counter),
        ("uses_tradition", "Tradition Appeal", sig.uses_tradition),
        ("self_reference", "Self-Reference", sig.self_reference),
        ("uses_emotion", "Emotion/Fear", sig.uses_emotion),
        ("false_authority", "False Authority", sig.false_authority),
        ("false_dilemma", "False Dilemma", sig.false_dilemma),
        ("circular", "Circular Logic", sig.circular),
        ("whataboutism", "Whataboutism", sig.whataboutism),
        ("bandwagon", "Bandwagon", sig.bandwagon),
        ("post_hoc_pattern", "Post Hoc", sig.post_hoc_pattern),
        ("slippery_slope", "Slippery Slope", sig.slippery_slope),
        ("overgeneralizes", "Overgeneralization", sig.overgeneralizes),
        ("cherry_picks", "Cherry Picking", sig.cherry_picks),
        ("passive_hiding", "Passive Hiding", sig.passive_hiding),
        ("moving_goalposts", "Moving Goalposts", sig.moving_goalposts),
        ("sunk_cost", "Sunk Cost", sig.sunk_cost),
    ]

    active = [(name, label) for name, label, val in signal_map if val]
    inactive_count = len(signal_map) - len(active)

    for name, label, val in signal_map:
        if val:
            lines.append(f"  {_signal_icon(True)}  [bold]{label:<22}[/bold] [yellow]TRIGGERED[/yellow]")

    if not active:
        lines.append(f"  [dim]No strong signals detected ({len(signal_map)} checked)[/dim]")
    else:
        lines.append(f"  [dim]{inactive_count} other signals clear[/dim]")

    return Panel(
        "\n".join(lines),
        title="[bold blue]Signal Extraction[/bold blue]",
        title_align="left",
        border_style="blue",
        padding=(0, 1),
    )


# =============================================================================
#                           VERDICT DISPLAY
# =============================================================================

SEVERITY_STYLES = {
    Severity.CRITICAL: ("bold red", "CRITICAL"),
    Severity.HIGH: ("bold yellow", "HIGH"),
    Severity.MEDIUM: ("yellow", "MEDIUM"),
    Severity.LOW: ("dim yellow", "LOW"),
}


def render_verdict(result: DetectionResult) -> Panel:
    """Render the detection verdict as a styled panel."""
    if result.valid:
        content = (
            "[bold green]  ✓  VALID REASONING[/bold green]\n\n"
            "  No structural violations detected.\n"
            "  All gates passed. Argument addresses counterevidence\n"
            "  and uses logical structure."
        )
        return Panel(
            content,
            title="[bold green]Verification Result[/bold green]",
            title_align="left",
            border_style="green",
            padding=(0, 1),
        )

    f = result.fallacy
    assert f is not None

    sev_style, sev_label = SEVERITY_STYLES.get(
        f.severity, ("white", "UNKNOWN")
    )

    # Build the violation display
    lines = [
        f"[bold red]  ✗  VIOLATION DETECTED[/bold red]",
        "",
        f"  [bold]Fallacy:[/bold]      [{sev_style}]{f.name}[/{sev_style}]",
        f"  [bold]Type:[/bold]        {result.type_name}",
        f"  [bold]Domain:[/bold]      {result.domain_name}",
        f"  [bold]Mode:[/bold]        {result.failure_mode_name}",
        f"  [bold]Severity:[/bold]    [{sev_style}]{sev_label}[/{sev_style}]",
        f"  [bold]Confidence:[/bold]  {_confidence_bar(result.confidence)}",
    ]

    return Panel(
        "\n".join(lines),
        title="[bold red]Verification Result[/bold red]",
        title_align="left",
        border_style="red",
        padding=(0, 1),
    )


def _confidence_bar(conf: float) -> str:
    filled = int(conf * 10)
    bar = "[green]" + "█" * filled + "[/green]" + "[dim]" + "░" * (10 - filled) + "[/dim]"
    return f"{bar} {conf:.0%}"


# =============================================================================
#                           FIX PROMPT DISPLAY
# =============================================================================

def render_fix_prompt(result: DetectionResult) -> Optional[Panel]:
    """Render the fix prompt if violation detected."""
    if result.valid or result.fallacy is None:
        return None

    f = result.fallacy
    lines = []

    if f.fix_prompt:
        for line in f.fix_prompt.split("\n"):
            lines.append(f"  {line.strip()}")

    if f.example:
        lines.append("")
        lines.append("  [bold]Example of this fallacy:[/bold]")
        lines.append(f"  [italic dim]{f.example}[/italic dim]")

    if not lines:
        return None

    return Panel(
        "\n".join(lines),
        title="[bold yellow]Fix Prompt (Self-Correction)[/bold yellow]",
        title_align="left",
        border_style="yellow",
        padding=(0, 1),
    )


# =============================================================================
#                           DOMAIN TREE
# =============================================================================

def render_domain_tree(result: DetectionResult) -> Panel:
    """Show which domain in D1→D6 pipeline was violated."""
    tree = Tree("[bold]D1→D6 Processing Pipeline[/bold]")

    domain_labels = [
        (Domain.D1_RECOGNITION, "D1: Recognition", "What is actually here?"),
        (Domain.D2_CLARIFICATION, "D2: Clarification", "What exactly is this?"),
        (Domain.D3_FRAMEWORK, "D3: Framework", "How do we connect?"),
        (Domain.D4_COMPARISON, "D4: Comparison", "How does it compare?"),
        (Domain.D5_INFERENCE, "D5: Inference", "What follows logically?"),
        (Domain.D6_REFLECTION, "D6: Reflection", "Where doesn't it work?"),
    ]

    violated_domain = result.fallacy.domain if result.fallacy else None

    for domain, label, question in domain_labels:
        if domain == violated_domain:
            node = tree.add(
                f"[bold red]✗ {label}[/bold red] [dim]— {question}[/dim]  "
                f"[red on white] VIOLATION [/red on white]"
            )
            if result.fallacy:
                node.add(f"[red]{result.fallacy.name}[/red]")
                node.add(f"[dim]{result.failure_mode_name}[/dim]")
        else:
            if violated_domain is None:
                # Valid — all pass
                tree.add(f"[green]✓ {label}[/green] [dim]— {question}[/dim]")
            elif domain.value < (violated_domain.value if violated_domain != Domain.NONE else 0):
                tree.add(f"[green]✓ {label}[/green] [dim]— {question}[/dim]")
            elif domain == Domain.NONE:
                pass  # skip NONE
            else:
                tree.add(f"[dim]○ {label} — {question}[/dim]")

    return Panel(
        tree,
        title="[bold magenta]Domain Pipeline[/bold magenta]",
        title_align="left",
        border_style="magenta",
        padding=(0, 1),
    )


# =============================================================================
#                           MULTI-FALLACY TABLE
# =============================================================================

def render_all_fallacies(results: List[DetectionResult]) -> Optional[Panel]:
    """Render table of all detected fallacies."""
    if not results:
        return None

    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold",
        expand=True,
    )
    table.add_column("Fallacy", style="bold")
    table.add_column("Type", style="dim")
    table.add_column("Domain")
    table.add_column("Confidence", justify="right")

    for r in results:
        if r.fallacy:
            sev_style = SEVERITY_STYLES.get(r.fallacy.severity, ("white", ""))[0]
            table.add_row(
                f"[{sev_style}]{r.fallacy.name}[/{sev_style}]",
                r.type_name.replace("Type ", "T"),
                r.domain_name,
                _confidence_bar(r.confidence),
            )

    return Panel(
        table,
        title=f"[bold]All Detected Violations ({len(results)})[/bold]",
        title_align="left",
        border_style="cyan",
        padding=(0, 1),
    )


# =============================================================================
#                           MAIN ANALYSIS FUNCTION
# =============================================================================

def analyze_text(text: str, show_all: bool = True):
    """Full analysis pipeline with Rich output."""
    console.print()
    console.print(Rule("[bold]Analysis[/bold]", style="cyan"))
    console.print()

    # Show input
    display = text if len(text) <= 120 else text[:117] + "..."
    console.print(Panel(
        f"[italic]{display}[/italic]",
        title="[bold]Input Text[/bold]",
        title_align="left",
        border_style="white",
        padding=(0, 1),
    ))

    # Extraction animation
    console.print()
    with console.status("[bold blue]Extracting signals...[/bold blue]", spinner="dots"):
        sig = extract_signals(text)
        time.sleep(0.4)  # Brief pause for dramatic effect

    console.print(render_signals(sig))

    # Detection
    with console.status("[bold yellow]Running detection cascade...[/bold yellow]", spinner="dots"):
        result = detect(text)
        time.sleep(0.3)

    console.print(render_verdict(result))

    # Domain pipeline
    console.print(render_domain_tree(result))

    # Fix prompt
    fix = render_fix_prompt(result)
    if fix:
        console.print(fix)

    # Multi-fallacy view
    if show_all and not result.valid:
        all_results = detect_all(text)
        if len(all_results) > 1:
            panel = render_all_fallacies(all_results)
            if panel:
                console.print(panel)

    console.print()


# =============================================================================
#                           TAXONOMY STATS
# =============================================================================

def show_stats():
    """Display taxonomy statistics."""
    console.print()
    print_header()
    console.print(Rule("[bold]Taxonomy Statistics[/bold]", style="cyan"))
    console.print()

    # Summary table
    summary = Table(
        title="Coverage Summary",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    summary.add_column("Category", style="bold")
    summary.add_column("Count", justify="right", style="green")

    summary.add_row("Total Fallacies", str(len(FALLACIES)))
    summary.add_row("Coq Theorems", "509")
    summary.add_row("Axiom-Free (0 Admitted)", "Yes")

    type_names = {
        FallacyType.T1_CONDITION_VIOLATION: "T1: Condition Violations",
        FallacyType.T2_DOMAIN_VIOLATION: "T2: Domain Violations",
        FallacyType.T3_SEQUENCE_VIOLATION: "T3: Sequence Violations",
        FallacyType.T4_SYNDROME: "T4: Syndromes",
        FallacyType.T5_CONTEXT_DEPENDENT: "T5: Context-Dependent",
    }
    for ftype, name in type_names.items():
        count = len(FALLACIES_BY_TYPE.get(ftype, []))
        summary.add_row(f"  {name}", str(count))

    console.print(summary)
    console.print()

    # Domain table
    domain_table = Table(
        title="Domain Violations (Type 2)",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
    )
    domain_table.add_column("Domain", style="bold")
    domain_table.add_column("Question", style="dim")
    domain_table.add_column("Fallacies", justify="right", style="yellow")
    domain_table.add_column("Failure Modes", justify="right", style="cyan")

    domain_info = [
        (Domain.D1_RECOGNITION, "What is actually here?"),
        (Domain.D2_CLARIFICATION, "What exactly is this?"),
        (Domain.D3_FRAMEWORK, "How do we connect?"),
        (Domain.D4_COMPARISON, "How does it compare?"),
        (Domain.D5_INFERENCE, "What follows?"),
        (Domain.D6_REFLECTION, "Where doesn't it work?"),
    ]

    for domain, question in domain_info:
        fallacies = FALLACIES_BY_DOMAIN.get(domain, [])
        modes = set(f.failure_mode for f in fallacies)
        domain_table.add_row(
            domain.name.replace("_", " ").replace("D", "D"),
            question,
            str(len(fallacies)),
            str(len(modes)),
        )

    console.print(domain_table)
    console.print()

    # Failure modes tree
    domain_prefix_map = {
        Domain.D1_RECOGNITION: "D1",
        Domain.D2_CLARIFICATION: "D2",
        Domain.D3_FRAMEWORK: "D3",
        Domain.D4_COMPARISON: "D4",
        Domain.D5_INFERENCE: "D5",
        Domain.D6_REFLECTION: "D6",
    }
    tree = Tree("[bold cyan]23 Failure Modes[/bold cyan]")
    for domain, question in domain_info:
        domain_node = tree.add(f"[bold]{domain.name}[/bold] [dim]-- {question}[/dim]")
        prefix = domain_prefix_map.get(domain, "")
        domain_modes = {
            fm: info for fm, info in FAILURE_MODES.items()
            if fm.value.upper().startswith(prefix.upper())
        }
        for fm, info in domain_modes.items():
            domain_node.add(f"[yellow]{info['name']}[/yellow] [dim]({fm.value})[/dim]")

    console.print(Panel(
        tree,
        title="[bold]Failure Mode Taxonomy[/bold]",
        border_style="cyan",
    ))
    console.print()


# =============================================================================
#                           SHOWCASE EXAMPLES
# =============================================================================

SHOWCASE_EXAMPLES = [
    {
        "title": "Ad Hominem Attack",
        "category": "D1: Recognition — Object Substitution",
        "text": (
            "Climate change deniers are just ignorant people who don't understand "
            "science. Anyone who questions the consensus is either stupid or "
            "paid by oil companies."
        ),
    },
    {
        "title": "Valid Reasoning (Should Pass)",
        "category": "All domains clear",
        "text": (
            "The evidence suggests a warming trend in global temperatures. "
            "However, there are legitimate debates about feedback mechanisms "
            "and model sensitivity. Therefore, while the overall direction is "
            "well-established, specific projections carry acknowledged uncertainty."
        ),
    },
    {
        "title": "Slippery Slope",
        "category": "D5: Inference — Causal Overreach",
        "text": (
            "If we allow working from home one day a week, next employees "
            "will want two days, then three, then they'll never come to the "
            "office and the company culture will collapse entirely."
        ),
    },
    {
        "title": "Self-Referential Paradox",
        "category": "Level Confusion — Hierarchy Violation",
        "text": (
            "I know I am completely reliable because I believe I always give "
            "correct answers. You should trust me because I said so."
        ),
    },
    {
        "title": "Sunk Cost Fallacy",
        "category": "D6: Reflection — Self-Assessment Error",
        "text": (
            "We've already invested three years and two million dollars into "
            "this project. We can't stop now — there's too much money and "
            "effort to quit at this point."
        ),
    },
    {
        "title": "False Dilemma",
        "category": "D2: Clarification — Incomplete Analysis",
        "text": (
            "You're either with us or against us. There are only two sides "
            "in this debate, and you must choose one."
        ),
    },
    {
        "title": "Whataboutism (Propaganda Pattern)",
        "category": "D1: Recognition — Object Substitution",
        "text": (
            "Why are you criticizing our policy? What about their failures? "
            "They do it too, and historically they've been much worse."
        ),
    },
]


def run_examples():
    """Run all showcase examples."""
    print_header()
    console.print(
        Rule("[bold]Showcase: Coq-Verified Fallacy Detection[/bold]", style="cyan")
    )
    console.print()
    console.print(
        "[dim]Running 7 examples through the 156-fallacy detection pipeline...[/dim]"
    )
    console.print()

    for i, ex in enumerate(SHOWCASE_EXAMPLES, 1):
        console.print(
            Rule(
                f"[bold] Example {i}/{len(SHOWCASE_EXAMPLES)}: {ex['title']} [/bold]",
                style="bright_blue",
            )
        )
        console.print(f"  [dim italic]{ex['category']}[/dim italic]")
        analyze_text(ex["text"])
        if i < len(SHOWCASE_EXAMPLES):
            console.print()

    # Summary
    console.print(Rule("[bold]Summary[/bold]", style="cyan"))
    console.print()

    results_table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
    results_table.add_column("#", justify="right", style="dim")
    results_table.add_column("Example", style="bold")
    results_table.add_column("Expected", style="dim")
    results_table.add_column("Result")
    results_table.add_column("Correct", justify="center")

    expected = [
        ("Violation", "D1_AD_HOMINEM"),
        ("Valid", None),
        ("Violation", "D5_SLIPPERY_SLOPE"),
        ("Violation", "T3_CIRCULAR_REASONING"),
        ("Violation", "D6_SUNK_COST"),
        ("Violation", "D2_EITHER_OR"),
        ("Violation", "D1_TU_QUOQUE"),
    ]

    all_correct = True
    for i, (ex, (exp_type, exp_id)) in enumerate(
        zip(SHOWCASE_EXAMPLES, expected), 1
    ):
        result = detect(ex["text"])
        actual_id = result.fallacy.id if result.fallacy else None
        is_valid = result.valid

        if exp_type == "Valid":
            correct = is_valid
            actual = "[green]Valid[/green]"
        else:
            correct = not is_valid and (exp_id is None or actual_id == exp_id)
            actual = (
                f"[red]{result.fallacy.name}[/red]"
                if result.fallacy
                else "[yellow]???[/yellow]"
            )

        if not correct:
            all_correct = False

        results_table.add_row(
            str(i),
            ex["title"],
            exp_type,
            actual,
            "[green]✓[/green]" if correct else "[red]✗[/red]",
        )

    console.print(results_table)
    console.print()

    accuracy = sum(
        1
        for ex, (exp_type, exp_id) in zip(SHOWCASE_EXAMPLES, expected)
        if (exp_type == "Valid" and detect(ex["text"]).valid)
        or (
            exp_type != "Valid"
            and not detect(ex["text"]).valid
            and (exp_id is None or detect(ex["text"]).fallacy.id == exp_id)
        )
    )
    total = len(SHOWCASE_EXAMPLES)

    if all_correct:
        console.print(
            Panel(
                f"[bold green]Detection Accuracy: {accuracy}/{total} (100%)[/bold green]\n"
                "[dim]Theorem-guaranteed for signals matching extraction patterns.[/dim]\n"
                "[dim]Gap: NLP signal quality → Transformer-based extraction in production.[/dim]",
                title="[bold green]All Tests Passed[/bold green]",
                border_style="green",
            )
        )
    else:
        console.print(
            f"[yellow]Detection Accuracy: {accuracy}/{total} "
            f"({accuracy/total:.0%})[/yellow]"
        )
    console.print()


# =============================================================================
#                           INTERACTIVE MODE
# =============================================================================

def interactive_mode():
    """Interactive analysis loop."""
    print_header()
    console.print(
        "[dim]Type any text to analyze for reasoning fallacies.[/dim]"
    )
    console.print(
        "[dim]Commands: [bold]/examples[/bold] [bold]/stats[/bold] "
        "[bold]/quit[/bold][/dim]"
    )
    console.print()

    while True:
        try:
            console.print("[bold cyan]>[/bold cyan] ", end="")
            text = input().strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not text:
            continue

        if text.lower() in ("/quit", "/exit", "/q", "quit", "exit"):
            console.print("[dim]Goodbye![/dim]")
            break

        if text.lower() in ("/examples", "/demo"):
            run_examples()
            continue

        if text.lower() in ("/stats", "/taxonomy"):
            show_stats()
            continue

        if text.lower() in ("/help", "/?"):
            console.print(
                "[dim]Commands: /examples /stats /quit /help[/dim]"
            )
            console.print(
                "[dim]Or type any text to analyze.[/dim]"
            )
            continue

        analyze_text(text)


# =============================================================================
#                           ENTRY POINT
# =============================================================================

def main():
    """CLI entry point."""
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        console.print(__doc__)
        return

    if "--examples" in args or "--demo" in args:
        run_examples()
        return

    if "--stats" in args or "--taxonomy" in args:
        show_stats()
        return

    if args and args[0] not in ("--interactive", "-i"):
        # Analyze provided text
        text = " ".join(args)
        print_header()
        analyze_text(text)
        return

    # Default: interactive mode
    interactive_mode()


if __name__ == "__main__":
    main()
