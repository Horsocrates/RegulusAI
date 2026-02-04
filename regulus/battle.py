"""
Regulus AI - Battle Mode
=========================

Side-by-side comparison of raw LLM output vs Regulus-guarded verification.

Runs both paths in parallel via asyncio.gather, then renders a two-column
Rich display highlighting where the Zero-Gate caught and corrected errors.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .llm.client import LLMClient
from .orchestrator import Orchestrator, VerifiedResponse
from .ui.console import render_ascii_tree


@dataclass
class BattleResult:
    """Result of a battle between raw LLM and Regulus-guarded LLM."""
    query: str
    raw_response: str
    guarded: VerifiedResponse
    raw_duration: float
    guarded_duration: float


class BattleMode:
    """
    Run raw LLM and Regulus-guarded pipeline in parallel, then compare.

    The raw response is a single LLM generate() call with a plain system prompt.
    The guarded response goes through the full Orchestrator pipeline
    (D1-D6 reasoning, signal extraction, Zero-Gate, correction loop, status machine).
    """

    RAW_SYSTEM_PROMPT = (
        "You are a helpful assistant. Answer the question directly and concisely."
    )

    def __init__(self, orchestrator: Orchestrator, llm_client: LLMClient) -> None:
        self.orchestrator = orchestrator
        self.llm = llm_client
        self._console = Console()

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------

    async def run_battle(self, query: str) -> BattleResult:
        """Run raw LLM and Regulus pipeline in parallel."""
        (raw_text, raw_dur), (guarded_resp, guarded_dur) = await asyncio.gather(
            self._run_raw(query),
            self._run_guarded(query),
        )
        return BattleResult(
            query=query,
            raw_response=raw_text,
            guarded=guarded_resp,
            raw_duration=raw_dur,
            guarded_duration=guarded_dur,
        )

    def render_comparison(self, result: BattleResult, verbose: bool = False) -> None:
        """Render a two-column comparison to the terminal."""
        console = self._console

        # Title banner
        console.print(
            Panel(
                Text(f"BATTLE MODE: {result.query}", style="bold white"),
                border_style="bright_magenta",
                title="Regulus AI",
            )
        )

        # Left panel: Raw response
        raw_content = Text()
        raw_content.append(result.raw_response + "\n\n")
        raw_content.append(f"Duration: {result.raw_duration:.2f}s", style="dim")

        left_panel = Panel(
            raw_content,
            title="[bold red]Raw Model[/bold red]",
            border_style="red",
            width=60,
        )

        # Right panel: Guarded response
        guarded = result.guarded
        guarded_content = Text()

        # Tree visualization
        tree_str = render_ascii_tree(guarded.result)
        guarded_content.append("Reasoning Tree:\n", style="bold cyan")
        guarded_content.append(tree_str + "\n\n")

        # Status
        if guarded.is_valid:
            guarded_content.append("Status: ", style="bold")
            guarded_content.append("PrimaryMax FOUND\n", style="bold green")
            answer = guarded.primary_answer or ""
            guarded_content.append(f"Answer: {answer}\n\n")
        else:
            guarded_content.append("Status: ", style="bold")
            guarded_content.append("NO PrimaryMax\n", style="bold red")

        guarded_content.append(
            f"Corrections: {guarded.total_corrections}\n", style="yellow"
        )
        guarded_content.append(f"Invalid nodes: {guarded.result.invalid_count}\n")
        guarded_content.append(
            f"Duration: {result.guarded_duration:.2f}s", style="dim"
        )

        right_panel = Panel(
            guarded_content,
            title="[bold green]Regulus Guarded[/bold green]",
            border_style="green",
            width=60,
        )

        # Side-by-side columns
        console.print(Columns([left_panel, right_panel], padding=2))

        # Annihilation banner
        if guarded.total_corrections > 0 and guarded.is_valid:
            console.print(
                Panel(
                    Text(
                        "HALLUCINATION ANNIHILATED",
                        style="bold white on red",
                        justify="center",
                    ),
                    border_style="bright_red",
                    padding=(1, 4),
                )
            )

        # Timing comparison
        overhead_pct = (
            ((result.guarded_duration - result.raw_duration) / result.raw_duration * 100)
            if result.raw_duration > 0
            else 0
        )
        console.print(
            f"\n[dim]Timing: Raw {result.raw_duration:.2f}s vs "
            f"Guarded {result.guarded_duration:.2f}s "
            f"(+{overhead_pct:.0f}% overhead)[/dim]"
        )

        # Verbose: show diagnostics and correction log
        if verbose and guarded.result.diagnostics:
            console.print("\n[bold]DIAGNOSTICS:[/bold]")
            for diag in guarded.result.diagnostics:
                gate_str = (
                    f"ERR={diag.gate_vector.get('ERR', '?')} "
                    f"Lv={diag.gate_vector.get('Levels', '?')} "
                    f"Ord={diag.gate_vector.get('Order', '?')}"
                )
                style = "green" if diag.status.name != "INVALID" else "red"
                console.print(
                    f"  [{style}]{diag.node_id}: {diag.status.name} "
                    f"W={diag.final_weight} [{gate_str}][/{style}]"
                )

            if guarded.corrections:
                console.print("\n[bold]CORRECTION LOG:[/bold]")
                for c in guarded.corrections:
                    s = "[green]OK[/green]" if c.success else "[red]FAIL[/red]"
                    console.print(
                        f"  Step {c.step_index} attempt {c.attempt} "
                        f"{s}: {c.diagnostic_code}"
                    )

    # ----------------------------------------------------------
    # Private helpers
    # ----------------------------------------------------------

    async def _run_raw(self, query: str) -> tuple[str, float]:
        """Run raw LLM call and return (response, duration_seconds)."""
        start = time.perf_counter()
        response = await self.llm.generate(
            prompt=query,
            system=self.RAW_SYSTEM_PROMPT,
        )
        elapsed = time.perf_counter() - start
        return response, elapsed

    async def _run_guarded(self, query: str) -> tuple[VerifiedResponse, float]:
        """Run full Regulus pipeline and return (response, duration_seconds)."""
        start = time.perf_counter()
        response = await self.orchestrator.process_query(query)
        elapsed = time.perf_counter() - start
        return response, elapsed
