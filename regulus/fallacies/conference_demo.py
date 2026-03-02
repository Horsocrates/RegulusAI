#!/usr/bin/env python3
"""
Regulus Logic Censor — Kyiv AI Day Conference Demo
===================================================

Curated examples for live demonstration at the conference.
Each example is designed to showcase a different capability.

Usage:
    uv run python -m regulus.fallacies.conference_demo

Scenario:
    The demo shows how an AI "Logic Censor" can detect reasoning
    errors in real-time — in LLM outputs, political speeches,
    marketing copy, and everyday arguments.
"""

from __future__ import annotations

import sys
import time
import os

# Force UTF-8 on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.align import Align
from rich import box

from regulus.fallacies.demo_cli import (
    analyze_text,
    print_header,
    render_signals,
    render_verdict,
    render_domain_tree,
    render_fix_prompt,
    render_all_fallacies,
    console,
)
from regulus.fallacies.detector import detect, detect_all, extract_signals

# =============================================================================
#                      CONFERENCE SHOWCASE SCENARIOS
# =============================================================================

SCENARIOS = [
    # ---- Scenario 1: LLM Hallucination (audience knows this pain) ----
    {
        "title": "LLM Hallucination Detection",
        "context": "ChatGPT-style confident nonsense",
        "icon": "robot",
        "text": (
            "The Python programming language was created by James Gosling "
            "in 1995 at Sun Microsystems. This is a well-established fact "
            "and there is no dispute about this."
        ),
        "why_impressive": (
            "Catches overconfident hallucination — no counterevidence, "
            "no hedging. The detector flags Confirmation Bias (D6) because "
            "the statement claims certainty without acknowledging any limits."
        ),
    },

    # ---- Scenario 2: Valid scientific reasoning (proves we don't just flag everything) ----
    {
        "title": "Valid Scientific Reasoning",
        "context": "Well-structured argument that SHOULD pass",
        "icon": "check",
        "text": (
            "Large language models demonstrate impressive zero-shot capabilities. "
            "However, recent studies show they struggle with multi-step logical "
            "reasoning and can produce confident but incorrect outputs. "
            "Therefore, while useful as assistants, they require verification "
            "layers for safety-critical applications."
        ),
        "why_impressive": (
            "Correctly PASSES — has logical connectors ('Therefore'), "
            "counterevidence ('However, studies show...'), and acknowledges "
            "limitations. This proves the detector isn't just flagging everything."
        ),
    },

    # ---- Scenario 3: Political manipulation (whataboutism) ----
    {
        "title": "Political Whataboutism",
        "context": "Classic propaganda deflection technique",
        "icon": "loudspeaker",
        "text": (
            "Why are you questioning our AI regulation approach? "
            "What about the Americans — they don't regulate AI at all! "
            "They do it too, and they've been much worse historically."
        ),
        "why_impressive": (
            "Detects Tu Quoque / Whataboutism at D1 (Recognition). "
            "Instead of addressing the criticism, the argument substitutes "
            "the object — pointing at someone else's behavior. "
            "Also catches Appeal to Tradition from 'historically'."
        ),
    },

    # ---- Scenario 4: Startup pitch fallacy (audience relates to this) ----
    {
        "title": "Startup Pitch Sunk Cost",
        "context": "Common VC/founder reasoning trap",
        "icon": "money",
        "text": (
            "We've already invested two years and three million dollars into "
            "this approach. The team has come this far and there's too much "
            "effort to quit now. We need to keep going with the current "
            "architecture."
        ),
        "why_impressive": (
            "Catches Sunk Cost Fallacy at D6 (Reflection). Past investment "
            "is irrelevant to future decisions — only future costs and "
            "benefits matter. Common trap in startup pivoting decisions."
        ),
    },

    # ---- Scenario 5: AI Self-Reference Paradox (meta & philosophically cool) ----
    {
        "title": "AI Self-Reference Paradox",
        "context": "What if an AI reasons about itself?",
        "icon": "loop",
        "text": (
            "I know I am a reliable AI system because I believe I always give "
            "correct answers. Trust me — my self-assessment confirms my accuracy."
        ),
        "why_impressive": (
            "Catches the Self-Reference Paradox — an evaluator cannot "
            "evaluate itself without creating a level confusion. "
            "This is the SAME structure as the Liar's Paradox and "
            "Godel's Incompleteness Theorem. Formally proven in Coq."
        ),
    },
]


# =============================================================================
#                           PRESENTATION MODE
# =============================================================================

def run_conference_demo():
    """Run the conference presentation demo."""
    print_header()

    console.print(
        Panel(
            "[bold]Kyiv AI Day Spring 2026[/bold]\n"
            "[dim]March 7, 2026[/dim]\n\n"
            "[bold cyan]Regulus: Logic Censor for AI[/bold cyan]\n"
            "[dim]Detecting reasoning fallacies with Coq-verified guarantees[/dim]\n\n"
            "[dim]156 fallacies across 6 cognitive domains[/dim]\n"
            "[dim]23 failure modes, each formally proven in Coq[/dim]\n"
            "[dim]509 theorems, 0 unproven axioms[/dim]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    console.print()

    for i, scenario in enumerate(SCENARIOS, 1):
        # Wait for keypress between scenarios
        if i > 1:
            console.print()
            console.print(
                "[dim]Press Enter for next example...[/dim]",
                end="",
            )
            try:
                input()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Demo ended.[/dim]")
                return

        # Scenario header
        console.print(
            Rule(
                f"[bold bright_cyan] Scenario {i}/{len(SCENARIOS)}: "
                f"{scenario['title']} [/bold bright_cyan]",
                style="bright_cyan",
            )
        )
        console.print(f"  [italic dim]{scenario['context']}[/italic dim]")
        console.print()

        # Run analysis
        analyze_text(scenario["text"], show_all=True)

        # Why it's impressive
        console.print(
            Panel(
                f"[dim]{scenario['why_impressive']}[/dim]",
                title="[bold]Why This Matters[/bold]",
                title_align="left",
                border_style="bright_black",
                padding=(0, 1),
            )
        )

    # Final slide
    console.print()
    console.print(Rule("[bold cyan]Summary[/bold cyan]", style="cyan"))
    console.print()

    summary_table = Table(
        box=box.DOUBLE_EDGE,
        show_header=True,
        header_style="bold cyan",
        title="Detection Results",
        title_style="bold",
    )
    summary_table.add_column("#", justify="right", style="dim")
    summary_table.add_column("Scenario", style="bold")
    summary_table.add_column("Result")
    summary_table.add_column("Domain")

    for i, scenario in enumerate(SCENARIOS, 1):
        r = detect(scenario["text"])
        if r.valid:
            summary_table.add_row(
                str(i),
                scenario["title"],
                "[green]VALID[/green]",
                "[green]All clear[/green]",
            )
        else:
            summary_table.add_row(
                str(i),
                scenario["title"],
                f"[red]{r.fallacy.name}[/red]" if r.fallacy else "[red]???[/red]",
                r.domain_name,
            )

    console.print(summary_table)
    console.print()

    console.print(
        Panel(
            "[bold]What makes this different?[/bold]\n\n"
            "  [cyan]1.[/cyan] Not heuristics — formal proofs (509 Coq theorems)\n"
            "  [cyan]2.[/cyan] Not a blacklist — structural analysis (6 domains x 23 failure modes)\n"
            "  [cyan]3.[/cyan] Not punishment — correction (fix prompts guide AI back on track)\n"
            "  [cyan]4.[/cyan] Not just detection — prevention (Zero-Gate blocks bad reasoning)\n\n"
            "[bold cyan]Regulus: make dishonesty structurally impossible.[/bold cyan]\n\n"
            "[dim]github.com/Horsocrates/theory-of-systems-coq[/dim]\n"
            "[dim]156 fallacies | 509 theorems | 0 Admitted[/dim]",
            border_style="cyan",
            title="[bold cyan]Regulus Logic Censor[/bold cyan]",
            padding=(1, 2),
        )
    )
    console.print()


# =============================================================================
#                           QUICK MODE (no pauses)
# =============================================================================

def run_quick():
    """Run all scenarios without pauses (for testing)."""
    print_header()
    console.print(Rule("[bold]Conference Demo — Quick Run[/bold]", style="cyan"))

    for i, scenario in enumerate(SCENARIOS, 1):
        console.print(
            Rule(
                f"[bold] {i}. {scenario['title']} [/bold]",
                style="bright_blue",
            )
        )
        analyze_text(scenario["text"])

    console.print("[bold green]All 5 scenarios complete.[/bold green]")
    console.print()


# =============================================================================
#                           ENTRY POINT
# =============================================================================

def main():
    args = sys.argv[1:]

    if "--quick" in args or "-q" in args:
        run_quick()
    elif "--help" in args or "-h" in args:
        console.print(__doc__)
    else:
        run_conference_demo()


if __name__ == "__main__":
    main()
