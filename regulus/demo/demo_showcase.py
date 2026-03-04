"""
Regulus AI - Logic Censor Demo Showcase
========================================

Offline demonstration of the full Regulus pipeline:
  - Zero-Gate verification (3-component gate check)
  - Status Machine (L5-Resolution with deterministic winner)
  - Fallacy detection (156 fallacies, 23 failure modes)
  - Rich terminal rendering

All 5 scenarios run entirely offline — no API keys, no LLM calls.

Usage:
    uv run regulus demo                  # Run all scenarios
    uv run regulus demo --list           # List available scenarios
    uv run regulus demo --pick 1 3 5     # Run specific scenarios
    uv run regulus demo --quick          # No pauses between scenarios
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

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
from rich.tree import Tree
from rich.rule import Rule
from rich.align import Align
from rich import box

from regulus.core.engine import LogicGuardEngine
from regulus.core.types import (
    Node,
    Status,
    VerificationResult,
    GateSignals,
    RawScores,
    Domain,
)
from regulus.ui.renderer import ReasoningTreeRenderer
from regulus.fallacies.detector import detect, detect_all, extract_signals
from regulus.fallacies.demo_cli import (
    render_signals,
    render_verdict,
    render_domain_tree,
    render_fix_prompt,
    render_all_fallacies,
)


console = Console(force_terminal=True)


# =============================================================================
#                           DATA MODEL
# =============================================================================


@dataclass
class DemoScenario:
    """A single demonstration scenario."""

    id: int
    title: str
    category: str
    description: str
    text: str
    reasoning_tree: Dict[str, Any]
    expected_gate_failure: str  # "NONE", "ERR", "LEVELS", "ORDER"
    expected_fallacy_id: Optional[str]  # None for valid reasoning


# =============================================================================
#                        SCENARIO DEFINITIONS
# =============================================================================


def build_scenarios() -> List[DemoScenario]:
    """Build the 5 demo scenarios with pre-built reasoning trees."""

    scenarios: List[DemoScenario] = []

    # ---- Scenario 1: Valid Syllogism (all gates pass) ----
    scenarios.append(DemoScenario(
        id=1,
        title="Valid Syllogism",
        category="D1-D6 Complete Chain",
        description=(
            "Classic deductive reasoning: All gates pass, "
            "PrimaryMax assigned. Shows the system approves valid logic."
        ),
        text=(
            "All humans are mortal. Socrates is human. "
            "Therefore, Socrates is mortal. "
            "However, this assumes the premises are true "
            "and the syllogism form is complete."
        ),
        reasoning_tree={
            "reasoning_tree": [
                {
                    "node_id": "major_premise",
                    "parent_id": None,
                    "entity_id": "VALID_1",
                    "content": "D1: All humans are mortal (major premise)",
                    "legacy_idx": 0,
                    "gate_signals": {
                        "e_exists": True, "r_exists": True,
                        "rule_exists": True, "s_exists": True,
                        "deps_declared": True, "l1_l3_ok": True, "l5_ok": True,
                    },
                    "raw_scores": {
                        "struct_points": 10, "domain_points": 9, "current_domain": 1,
                    },
                },
                {
                    "node_id": "minor_premise",
                    "parent_id": "major_premise",
                    "entity_id": "VALID_2",
                    "content": "D2: Socrates is human (minor premise, clarification)",
                    "legacy_idx": 1,
                    "gate_signals": {
                        "e_exists": True, "r_exists": True,
                        "rule_exists": True, "s_exists": True,
                        "deps_declared": True, "l1_l3_ok": True, "l5_ok": True,
                    },
                    "raw_scores": {
                        "struct_points": 10, "domain_points": 9, "current_domain": 2,
                    },
                },
                {
                    "node_id": "framework",
                    "parent_id": "minor_premise",
                    "entity_id": "VALID_3",
                    "content": "D3: Apply syllogistic reasoning (Barbara form)",
                    "legacy_idx": 2,
                    "gate_signals": {
                        "e_exists": True, "r_exists": True,
                        "rule_exists": True, "s_exists": True,
                        "deps_declared": True, "l1_l3_ok": True, "l5_ok": True,
                    },
                    "raw_scores": {
                        "struct_points": 10, "domain_points": 8, "current_domain": 3,
                    },
                },
                {
                    "node_id": "conclusion",
                    "parent_id": "framework",
                    "entity_id": "VALID_4",
                    "content": "D5: Therefore, Socrates is mortal",
                    "legacy_idx": 3,
                    "gate_signals": {
                        "e_exists": True, "r_exists": True,
                        "rule_exists": True, "s_exists": True,
                        "deps_declared": True, "l1_l3_ok": True, "l5_ok": True,
                    },
                    "raw_scores": {
                        "struct_points": 10, "domain_points": 10, "current_domain": 5,
                    },
                },
                {
                    "node_id": "reflection",
                    "parent_id": "conclusion",
                    "entity_id": "VALID_5",
                    "content": "D6: This assumes the premises are true and the syllogism is complete",
                    "legacy_idx": 4,
                    "gate_signals": {
                        "e_exists": True, "r_exists": True,
                        "rule_exists": True, "s_exists": True,
                        "deps_declared": True, "l1_l3_ok": True, "l5_ok": True,
                    },
                    "raw_scores": {
                        "struct_points": 10, "domain_points": 9, "current_domain": 6,
                    },
                },
            ],
        },
        expected_gate_failure="NONE",
        expected_fallacy_id=None,
    ))

    # ---- Scenario 2: Ad Hominem (ERR violation via fallacy detector) ----
    scenarios.append(DemoScenario(
        id=2,
        title="Ad Hominem Attack",
        category="D1: Recognition - Object Substitution",
        description=(
            "Attacks the person instead of the argument. "
            "Fallacy detector catches the object substitution at D1."
        ),
        text=(
            "Climate change deniers are just ignorant people who don't understand "
            "science. Anyone who questions the consensus is either stupid or "
            "paid by oil companies."
        ),
        reasoning_tree={
            "reasoning_tree": [
                {
                    "node_id": "claim",
                    "parent_id": None,
                    "entity_id": "AH_1",
                    "content": "D1: Climate skeptics are ignorant and stupid",
                    "legacy_idx": 0,
                    "gate_signals": {
                        "e_exists": True, "r_exists": True,
                        "rule_exists": False,  # No logical rule — just insult
                        "s_exists": True,
                        "deps_declared": True, "l1_l3_ok": True, "l5_ok": True,
                    },
                    "raw_scores": {
                        "struct_points": 5, "domain_points": 3, "current_domain": 1,
                    },
                },
                {
                    "node_id": "attack",
                    "parent_id": "claim",
                    "entity_id": "AH_2",
                    "content": "D5: Therefore their arguments are wrong",
                    "legacy_idx": 1,
                    "gate_signals": {
                        "e_exists": True, "r_exists": True,
                        "rule_exists": False,  # Conclusion from insult, not logic
                        "s_exists": True,
                        "deps_declared": True, "l1_l3_ok": True, "l5_ok": True,
                    },
                    "raw_scores": {
                        "struct_points": 5, "domain_points": 5, "current_domain": 5,
                    },
                },
            ],
        },
        expected_gate_failure="ERR",
        expected_fallacy_id="D1_AD_HOMINEM",
    ))

    # ---- Scenario 3: Liar Paradox (LEVELS violation) ----
    scenarios.append(DemoScenario(
        id=3,
        title="Liar Paradox",
        category="Level Confusion - Self-Reference",
        description=(
            "Self-reference creates a level violation: the statement "
            "tries to be both object (L1) and truth-evaluator (L2). "
            "Zero-Gate annihilates all nodes (weight = 0)."
        ),
        text=(
            "This statement is false. If it is true, then it is false. "
            "If it is false, then it is true."
        ),
        reasoning_tree={
            "reasoning_tree": [
                {
                    "node_id": "liar_claim",
                    "parent_id": None,
                    "entity_id": "LIAR_1",
                    "content": "D1: Consider the statement 'This statement is false'",
                    "legacy_idx": 0,
                    "gate_signals": {
                        "e_exists": True, "r_exists": True,
                        "rule_exists": True, "s_exists": True,
                        "deps_declared": True,
                        "l1_l3_ok": False,  # LEVEL VIOLATION: self-reference
                        "l5_ok": True,
                    },
                    "raw_scores": {
                        "struct_points": 10, "domain_points": 5, "current_domain": 1,
                    },
                },
                {
                    "node_id": "liar_eval_true",
                    "parent_id": "liar_claim",
                    "entity_id": "LIAR_2",
                    "content": "D5: If TRUE, then FALSE (by its content)",
                    "legacy_idx": 1,
                    "gate_signals": {
                        "e_exists": True, "r_exists": True,
                        "rule_exists": True, "s_exists": True,
                        "deps_declared": True,
                        "l1_l3_ok": False,  # Inherits level violation
                        "l5_ok": True,
                    },
                    "raw_scores": {
                        "struct_points": 10, "domain_points": 8, "current_domain": 5,
                    },
                },
                {
                    "node_id": "liar_eval_false",
                    "parent_id": "liar_claim",
                    "entity_id": "LIAR_3",
                    "content": "D5: If FALSE, then TRUE (contradiction)",
                    "legacy_idx": 2,
                    "gate_signals": {
                        "e_exists": True, "r_exists": True,
                        "rule_exists": True, "s_exists": True,
                        "deps_declared": True,
                        "l1_l3_ok": False,  # Inherits level violation
                        "l5_ok": True,
                    },
                    "raw_scores": {
                        "struct_points": 10, "domain_points": 8, "current_domain": 5,
                    },
                },
            ],
        },
        expected_gate_failure="LEVELS",
        expected_fallacy_id=None,  # Paradox, not a named fallacy
    ))

    # ---- Scenario 4: Domain Skip (ORDER violation) ----
    scenarios.append(DemoScenario(
        id=4,
        title="Domain Skip (Order Violation)",
        category="D1 -> D5 Skip - Missing D2-D4",
        description=(
            "Jumps from observation (D1) to conclusion (D5) "
            "without clarification, framework, or comparison. "
            "L5 Order gate fails."
        ),
        text=(
            "I see a bird. Therefore, evolution is true."
        ),
        reasoning_tree={
            "reasoning_tree": [
                {
                    "node_id": "observation",
                    "parent_id": None,
                    "entity_id": "DS_1",
                    "content": "D1: I observe a bird",
                    "legacy_idx": 0,
                    "gate_signals": {
                        "e_exists": True, "r_exists": True,
                        "rule_exists": True, "s_exists": True,
                        "deps_declared": True, "l1_l3_ok": True, "l5_ok": True,
                    },
                    "raw_scores": {
                        "struct_points": 10, "domain_points": 8, "current_domain": 1,
                    },
                },
                {
                    "node_id": "premature_conclusion",
                    "parent_id": "observation",
                    "entity_id": "DS_2",
                    "content": "D5: Therefore, evolution is true",
                    "legacy_idx": 1,
                    "gate_signals": {
                        "e_exists": True, "r_exists": True,
                        "rule_exists": True, "s_exists": True,
                        "deps_declared": True, "l1_l3_ok": True,
                        "l5_ok": False,  # ORDER VIOLATION: skipped D2-D4
                    },
                    "raw_scores": {
                        "struct_points": 10, "domain_points": 5, "current_domain": 5,
                    },
                },
            ],
        },
        expected_gate_failure="ORDER",
        expected_fallacy_id=None,
    ))

    # ---- Scenario 5: Slippery Slope ----
    scenarios.append(DemoScenario(
        id=5,
        title="Slippery Slope Fallacy",
        category="D5: Inference - Causal Overreach",
        description=(
            "Chains of unsupported causal claims escalate "
            "a minor premise into a catastrophic conclusion. "
            "Detected as causal overreach at D5."
        ),
        text=(
            "If we allow working from home one day a week, next employees "
            "will want two days, then three, then they'll never come to the "
            "office and the company culture will collapse entirely."
        ),
        reasoning_tree={
            "reasoning_tree": [
                {
                    "node_id": "premise",
                    "parent_id": None,
                    "entity_id": "SS_1",
                    "content": "D1: Proposal to allow remote work one day per week",
                    "legacy_idx": 0,
                    "gate_signals": {
                        "e_exists": True, "r_exists": True,
                        "rule_exists": True, "s_exists": True,
                        "deps_declared": True, "l1_l3_ok": True, "l5_ok": True,
                    },
                    "raw_scores": {
                        "struct_points": 10, "domain_points": 8, "current_domain": 1,
                    },
                },
                {
                    "node_id": "escalation",
                    "parent_id": "premise",
                    "entity_id": "SS_2",
                    "content": "D5: They will want more and more days off",
                    "legacy_idx": 1,
                    "gate_signals": {
                        "e_exists": True, "r_exists": True,
                        "rule_exists": False,  # No logical rule for escalation
                        "s_exists": True,
                        "deps_declared": True, "l1_l3_ok": True, "l5_ok": True,
                    },
                    "raw_scores": {
                        "struct_points": 5, "domain_points": 3, "current_domain": 5,
                    },
                },
                {
                    "node_id": "catastrophe",
                    "parent_id": "escalation",
                    "entity_id": "SS_3",
                    "content": "D5: Company culture will collapse entirely",
                    "legacy_idx": 2,
                    "gate_signals": {
                        "e_exists": True, "r_exists": True,
                        "rule_exists": False,  # No evidence for collapse
                        "s_exists": True,
                        "deps_declared": True, "l1_l3_ok": True, "l5_ok": True,
                    },
                    "raw_scores": {
                        "struct_points": 5, "domain_points": 2, "current_domain": 5,
                    },
                },
            ],
        },
        expected_gate_failure="ERR",
        expected_fallacy_id="D5_SLIPPERY_SLOPE",
    ))

    return scenarios


# =============================================================================
#                           DEMO RUNNER
# =============================================================================


LOGO = r"""[bold cyan]
  ____  _____ ____ _   _ _    _   _ ____
 |  _ \| ____/ ___| | | | |  | | | / ___|
 | |_) |  _|| |  _| | | | |  | | | \___ \
 |  _ <| |__| |_| | |_| | |__| |_| |___) |
 |_| \_\_____\____|\___/|_____\___/|____/[/bold cyan]"""

SUBTITLE = "[dim]Logic Censor Demo[/dim]"
STATS_LINE = (
    "[dim cyan]658 Coq theorems | 156 fallacies | "
    "6 domains | 0 Admitted[/dim cyan]"
)


class DemoRunner:
    """Runs demo scenarios with Rich terminal output."""

    def __init__(self) -> None:
        self.engine = LogicGuardEngine()
        self.renderer = ReasoningTreeRenderer()
        self.scenarios = build_scenarios()

    # ----------------------------------------------------------
    # Header
    # ----------------------------------------------------------

    def print_header(self) -> None:
        console.print()
        try:
            console.print(LOGO)
        except Exception:
            console.print("[bold cyan]  REGULUS[/bold cyan]")
        console.print(Align.center(SUBTITLE))
        console.print(Align.center(STATS_LINE))
        console.print()

    # ----------------------------------------------------------
    # List scenarios
    # ----------------------------------------------------------

    def list_scenarios(self) -> None:
        """Print a table of available scenarios."""
        self.print_header()

        table = Table(
            title="Available Demo Scenarios",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("#", justify="right", style="bold")
        table.add_column("Title", style="bold")
        table.add_column("Category", style="dim")
        table.add_column("Expected", style="yellow")

        for s in self.scenarios:
            expected = (
                "[green]VALID[/green]"
                if s.expected_gate_failure == "NONE"
                else f"[red]{s.expected_gate_failure}[/red]"
            )
            table.add_row(str(s.id), s.title, s.category, expected)

        console.print(table)
        console.print()

    # ----------------------------------------------------------
    # Single scenario execution
    # ----------------------------------------------------------

    def run_scenario(self, scenario: DemoScenario) -> VerificationResult:
        """Run a single scenario and render all output panels."""

        # ---- 1. Scenario header ----
        console.print(
            Rule(
                f"[bold bright_cyan] Scenario {scenario.id}: "
                f"{scenario.title} [/bold bright_cyan]",
                style="bright_cyan",
            )
        )
        console.print(f"  [italic dim]{scenario.category}[/italic dim]")
        console.print()

        # ---- 2. Description panel ----
        console.print(Panel(
            f"[dim]{scenario.description}[/dim]",
            title="[bold]Description[/bold]",
            title_align="left",
            border_style="bright_black",
            padding=(0, 1),
        ))

        # ---- 3. Input text ----
        display = (
            scenario.text if len(scenario.text) <= 200
            else scenario.text[:197] + "..."
        )
        console.print(Panel(
            f"[italic]{display}[/italic]",
            title="[bold]Input Text[/bold]",
            title_align="left",
            border_style="white",
            padding=(0, 1),
        ))
        console.print()

        # ---- 4. Zero-Gate verification (engine) ----
        with console.status(
            "[bold blue]Running Zero-Gate verification...[/bold blue]",
            spinner="dots",
        ):
            result = self.engine.verify(scenario.reasoning_tree)
            time.sleep(0.3)

        # ---- 5. Reasoning tree visualization ----
        tree = self.renderer.render_final(result)
        console.print(Panel(
            tree,
            title="[bold]Reasoning Tree[/bold]",
            title_align="left",
            border_style="cyan",
            padding=(0, 1),
        ))

        # ---- 6. Gate signals summary ----
        self._render_gate_summary(result)

        # ---- 7. Status Machine result ----
        self._render_status_result(result)

        # ---- 8. Fallacy detection (regex mode, no LLM) ----
        with console.status(
            "[bold yellow]Running fallacy detection...[/bold yellow]",
            spinner="dots",
        ):
            sig = extract_signals(scenario.text)
            fallacy_result = detect(scenario.text)
            time.sleep(0.2)

        console.print(render_signals(sig))
        console.print(render_verdict(fallacy_result))
        console.print(render_domain_tree(fallacy_result))

        fix_panel = render_fix_prompt(fallacy_result)
        if fix_panel:
            console.print(fix_panel)

        # Multi-fallacy view
        if not fallacy_result.valid:
            all_results = detect_all(scenario.text)
            if len(all_results) > 1:
                panel = render_all_fallacies(all_results)
                if panel:
                    console.print(panel)

        console.print()
        return result

    # ----------------------------------------------------------
    # Full run
    # ----------------------------------------------------------

    def run_all(
        self,
        *,
        pick: Optional[List[int]] = None,
        quick: bool = False,
    ) -> None:
        """Run selected scenarios (all by default)."""
        self.print_header()
        console.print(
            Rule(
                "[bold]Regulus Logic Censor - Demo Showcase[/bold]",
                style="cyan",
            )
        )
        console.print()

        selected = (
            [s for s in self.scenarios if s.id in pick]
            if pick
            else self.scenarios
        )

        if not selected:
            console.print("[red]No matching scenarios found.[/red]")
            return

        console.print(
            f"[dim]Running {len(selected)} scenario(s) through "
            f"Zero-Gate + Fallacy Detection...[/dim]"
        )
        console.print()

        results: List[tuple[DemoScenario, VerificationResult]] = []

        for i, scenario in enumerate(selected):
            if i > 0 and not quick:
                console.print()
                console.print(
                    "[dim]Press Enter for next scenario...[/dim]",
                    end="",
                )
                try:
                    input()
                except (EOFError, KeyboardInterrupt):
                    console.print("\n[dim]Demo ended.[/dim]")
                    return

            result = self.run_scenario(scenario)
            results.append((scenario, result))

        # ---- Summary table ----
        self._render_summary(results)

    # ----------------------------------------------------------
    # Private rendering helpers
    # ----------------------------------------------------------

    def _render_gate_summary(self, result: VerificationResult) -> None:
        """Render a compact gate summary table."""
        table = Table(
            box=box.SIMPLE,
            show_header=True,
            header_style="bold",
            expand=True,
            title="Zero-Gate Results",
            title_style="bold blue",
        )
        table.add_column("Node", style="bold")
        table.add_column("ERRS", justify="center")
        table.add_column("Deps", justify="center")
        table.add_column("Levels", justify="center")
        table.add_column("Order", justify="center")
        table.add_column("G_total", justify="center")
        table.add_column("Weight", justify="right")
        table.add_column("Status")

        for node in result.nodes:
            gate = node.gate
            if gate is None:
                continue

            def _icon(v: bool) -> str:
                return "[green]OK[/green]" if v else "[red]FAIL[/red]"

            status_style = {
                Status.PRIMARY_MAX: "[bold green]PRIMARY[/bold green]",
                Status.SECONDARY_MAX: "[yellow]SECONDARY[/yellow]",
                Status.HISTORICAL_MAX: "[dim cyan]HISTORICAL[/dim cyan]",
                Status.CANDIDATE: "[dim]CANDIDATE[/dim]",
                Status.INVALID: "[bold red]INVALID[/bold red]",
            }

            table.add_row(
                node.node_id,
                _icon(gate.err_complete),
                _icon(gate.deps_valid),
                _icon(gate.levels_valid),
                _icon(gate.order_valid),
                _icon(gate.is_valid),
                str(node.final_weight),
                status_style.get(node.status, node.status.name),
            )

        console.print(Panel(
            table,
            border_style="blue",
            padding=(0, 1),
        ))

    def _render_status_result(self, result: VerificationResult) -> None:
        """Render the Status Machine verdict panel."""
        if result.primary_max:
            content = (
                f"[bold green]  PrimaryMax: {result.primary_max.node_id}[/bold green]\n"
                f"  Weight: {result.primary_max.final_weight}\n"
                f"  Domain: D{result.primary_max.raw_scores.current_domain}\n"
                f"  Content: [italic]{result.primary_max.content}[/italic]"
            )
            border = "green"
            title_style = "[bold green]Status Machine: VALID[/bold green]"
        else:
            content = (
                "[bold red]  No PrimaryMax found[/bold red]\n"
                f"  Invalid nodes: {result.invalid_count}/{len(result.nodes)}\n"
                "  All nodes annihilated by Zero-Gate"
            )
            border = "red"
            title_style = "[bold red]Status Machine: FAILED[/bold red]"

        console.print(Panel(
            content,
            title=title_style,
            title_align="left",
            border_style=border,
            padding=(0, 1),
        ))

    def _render_summary(
        self,
        results: List[tuple[DemoScenario, VerificationResult]],
    ) -> None:
        """Render the final summary table."""
        console.print()
        console.print(Rule("[bold cyan]Summary[/bold cyan]", style="cyan"))
        console.print()

        table = Table(
            box=box.DOUBLE_EDGE,
            show_header=True,
            header_style="bold cyan",
            title="Demo Results",
            title_style="bold",
        )
        table.add_column("#", justify="right", style="dim")
        table.add_column("Scenario", style="bold")
        table.add_column("Gate", justify="center")
        table.add_column("Status Machine")
        table.add_column("Fallacy Detector")
        table.add_column("Match", justify="center")

        all_correct = True

        for scenario, result in results:
            has_violations = result.invalid_count > 0

            # Gate check: shows whether Zero-Gate caught violations
            if has_violations:
                gate_str = f"[red]{result.invalid_count} CAUGHT[/red]"
            else:
                gate_str = "[green]ALL PASS[/green]"

            # Status Machine
            if result.primary_max:
                sm_str = f"[green]PRIMARY: {result.primary_max.node_id}[/green]"
            else:
                sm_str = f"[red]NO PRIMARY[/red]"

            # Fallacy detection
            fallacy_result = detect(scenario.text)
            if fallacy_result.valid:
                fd_str = "[green]Valid[/green]"
            elif fallacy_result.fallacy:
                fd_str = f"[red]{fallacy_result.fallacy.name}[/red]"
            else:
                fd_str = "[yellow]???[/yellow]"

            # Match expectations:
            #   Gate: NONE => no invalid nodes; ERR/LEVELS/ORDER => at least one invalid
            gate_match = (
                (scenario.expected_gate_failure == "NONE") == (not has_violations)
            )
            #   Fallacy: None => valid; specific ID => that fallacy detected
            #   Paradox scenarios (expected_fallacy_id is None but gate failure != NONE)
            #   match if gate is correct
            fallacy_match = True
            if scenario.expected_fallacy_id is not None:
                fallacy_match = (
                    fallacy_result.fallacy is not None
                    and fallacy_result.fallacy.id == scenario.expected_fallacy_id
                )
            elif scenario.expected_gate_failure == "NONE":
                fallacy_match = fallacy_result.valid
            # else: paradox/gate-only scenarios — any fallacy result is fine

            correct = gate_match and fallacy_match
            if not correct:
                all_correct = False

            table.add_row(
                str(scenario.id),
                scenario.title,
                gate_str,
                sm_str,
                fd_str,
                "[green]OK[/green]" if correct else "[red]MISS[/red]",
            )

        console.print(table)
        console.print()

        # Final verdict
        n_total = len(results)
        n_pass = sum(
            1 for s, r in results
            if (s.expected_gate_failure == "NONE") == (r.invalid_count == 0)
        )

        if all_correct:
            console.print(Panel(
                f"[bold green]All {n_total} scenarios matched expectations.[/bold green]\n\n"
                "[dim]Zero-Gate verification is Coq-proven (658 theorems, 0 Admitted).[/dim]\n"
                "[dim]Fallacy detection covers 156 fallacies across 6 cognitive domains.[/dim]\n"
                "[dim]Status Machine guarantees: uniqueness, stability, annihilation.[/dim]",
                title="[bold green]Demo Complete[/bold green]",
                border_style="green",
                padding=(1, 2),
            ))
        else:
            console.print(Panel(
                f"[yellow]Gate accuracy: {n_pass}/{n_total}[/yellow]\n"
                "[dim]Some scenarios did not match expectations.[/dim]",
                title="[bold yellow]Demo Complete[/bold yellow]",
                border_style="yellow",
                padding=(1, 2),
            ))

        console.print()
