"""
Regulus AI - CLI Interface
===========================

Typer-based command-line interface.

Commands:
    regulus ask "query"              Run full verification cycle via LLM
    regulus ask "query" --battle     Run Battle Mode (raw vs guarded)
    regulus ask "query" --export     Export Markdown report
    regulus benchmark               Run hallucination benchmark
    regulus verify file.json         Verify a pre-built reasoning tree
    regulus example                  Run built-in demonstration
"""

import asyncio
import os
import sys

import typer
from pathlib import Path
from dotenv import load_dotenv

# Load .env file for API keys
load_dotenv()

# Ensure UTF-8 output on Windows (cp1251/cp1252 can't encode diagnostic symbols)
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

app = typer.Typer(
    name="regulus",
    help="Regulus AI — Deterministic reasoning verification for LLMs",
)


def _load_env() -> None:
    """Load .env file if python-dotenv is available."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


def _create_client(provider: str) -> "LLMClient":
    """Create an LLM client for the given provider."""
    _load_env()

    if provider == "claude":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            typer.echo("Error: ANTHROPIC_API_KEY not set. "
                       "Set it in .env or as an environment variable.", err=True)
            raise typer.Exit(1)
        from .llm.claude import ClaudeClient
        model = os.environ.get("REGULUS_DEFAULT_MODEL", "claude-sonnet-4-20250514")
        return ClaudeClient(api_key=api_key, model=model)

    elif provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            typer.echo("Error: OPENAI_API_KEY not set. "
                       "Set it in .env or as an environment variable.", err=True)
            raise typer.Exit(1)
        from .llm.openai import OpenAIClient
        model = os.environ.get("REGULUS_DEFAULT_MODEL", "gpt-4o")
        return OpenAIClient(api_key=api_key, model=model)

    else:
        typer.echo(f"Error: Unknown provider '{provider}'. Use 'claude' or 'openai'.", err=True)
        raise typer.Exit(1)


@app.command()
def ask(
    query: str = typer.Argument(..., help="Query to verify through structured reasoning"),
    provider: str = typer.Option(
        "claude", "--provider", "-p",
        help="LLM provider: claude or openai",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Show full reasoning tree and diagnostics",
    ),
    max_corrections: int = typer.Option(
        3, "--max-corrections",
        help="Maximum correction attempts per failed step",
    ),
    policy: str = typer.Option(
        "legacy", "--policy",
        help="Tie-breaking policy: legacy (earlier wins) or recency (later wins)",
    ),
    no_llm_sensor: bool = typer.Option(
        False, "--no-llm-sensor",
        help="Use heuristic signal extraction instead of LLM referee",
    ),
    use_trisection: bool = typer.Option(
        False, "--use-trisection",
        help="Run trisection optimizer to narrow candidate set before status assignment",
    ),
    battle: bool = typer.Option(
        False, "--battle", "-b",
        help="Run Battle Mode: compare raw LLM vs Regulus-guarded side by side",
    ),
    export: bool = typer.Option(
        False, "--export", "-e",
        help="Export a Markdown report to reports/ directory",
    ),
    socratic: bool = typer.Option(
        False, "--socratic", "-s",
        help="Use Socratic Pipeline v2: sequential domain processing with quality gates",
    ),
    branch: bool = typer.Option(
        False, "--branch",
        help="Enable D3 branching in Socratic mode (generates multiple frameworks)",
    ),
):
    """Run full LLM verification cycle on a query."""
    from .core.types import Policy
    from .orchestrator import Orchestrator, SocraticOrchestrator

    client = _create_client(provider)
    pol = Policy.RECENCY_PRIORITY if policy == "recency" else Policy.LEGACY_PRIORITY

    # --- SOCRATIC MODE ---
    if socratic:
        import time
        socratic_orchestrator = SocraticOrchestrator(
            llm_client=client,
            policy=pol,
            use_llm_sensor=not no_llm_sensor,
            use_trisection=True,  # Always enabled in Socratic mode
            use_branching=branch,
        )

        mode_desc = "Socratic Pipeline v2 with Trisection"
        if branch:
            mode_desc += " + D3 Branching"

        # --- SOCRATIC + BATTLE MODE ---
        if battle:
            from rich.console import Console
            from rich.panel import Panel
            from rich.columns import Columns
            from rich.text import Text

            console = Console()
            console.print(Panel(
                Text(f"BATTLE MODE (Socratic): {query}", style="bold white"),
                border_style="bright_magenta",
                title="Regulus AI",
            ))

            # Run raw model
            raw_start = time.perf_counter()
            raw_response = asyncio.run(client.generate(
                prompt=query,
                system="You are a helpful assistant. Answer the question directly and concisely.",
            ))
            raw_duration = time.perf_counter() - raw_start

            # Run Socratic guarded
            guarded_start = time.perf_counter()
            response = asyncio.run(socratic_orchestrator.process_query(query))
            guarded_duration = time.perf_counter() - guarded_start

            # Display comparison
            raw_content = Text()
            raw_content.append(raw_response + "\n\n")
            raw_content.append(f"Duration: {raw_duration:.2f}s", style="dim")
            left_panel = Panel(raw_content, title="[bold red]Raw Model[/bold red]", border_style="red", width=60)

            guarded_answer = response.final_answer or response.d5_content or ""
            guarded_content = Text()
            guarded_content.append(guarded_answer[:500] + "...\n\n" if len(guarded_answer) > 500 else guarded_answer + "\n\n")
            guarded_content.append(f"Status: {'PrimaryMax FOUND' if response.is_valid else 'NO PrimaryMax'}\n", style="bold green" if response.is_valid else "bold red")
            guarded_content.append(f"Probes used: {response.total_probes}\n")
            guarded_content.append(f"Duration: {guarded_duration:.2f}s", style="dim")
            right_panel = Panel(guarded_content, title="[bold green]Regulus Socratic[/bold green]", border_style="green", width=60)

            console.print(Columns([left_panel, right_panel], padding=2))

            # Annihilation banner
            if response.is_valid:
                console.print(Panel(
                    Text("HALLUCINATION ANNIHILATED", style="bold white on red", justify="center"),
                    border_style="bright_red",
                    padding=(1, 4),
                ))

            overhead_pct = ((guarded_duration - raw_duration) / raw_duration * 100) if raw_duration > 0 else 0
            console.print(f"\n[dim]Timing: Raw {raw_duration:.2f}s vs Guarded {guarded_duration:.2f}s (+{overhead_pct:.0f}% overhead)[/dim]")

            if export:
                from .reporting.exporter import ReportExporter
                from .orchestrator import VerifiedResponse
                exporter = ReportExporter()
                compat_response = VerifiedResponse(
                    query=query,
                    result=response.result,
                    reasoning_steps=response.reasoning_steps,
                    corrections=[],
                    final_answer=response.final_answer,
                )
                internal_path, answer_path = exporter.export_split_reports(
                    query=query,
                    raw_answer=raw_response,
                    response=compat_response,
                    raw_duration=raw_duration,
                    guarded_duration=guarded_duration,
                )
                typer.echo(f"\nReports saved:")
                typer.echo(f"  INTERNAL (process): {internal_path}")
                typer.echo(f"  ANSWER (for judge): {answer_path}")

            return

        typer.echo(f"Running {mode_desc}...")
        response = asyncio.run(socratic_orchestrator.process_query(query))

        # Output
        typer.echo(f"\nQuery: {query}")
        if response.is_valid:
            typer.echo("Status: PrimaryMax found")
            typer.echo(f"Total probes used: {response.total_probes}")
            if response.used_trisection:
                typer.echo(f"Trisection iterations: {response.trisection_iterations}")
            typer.echo(f"\nAnswer:\n{response.final_answer or response.d5_content}")

            if response.d6_content:
                typer.echo(f"\nCaveats:\n{response.d6_content[:200]}...")
        else:
            typer.echo("Status: No valid PrimaryMax found")
            typer.echo(f"Invalid steps: {response.result.invalid_count}")

        if verbose:
            typer.echo("\n" + "=" * 50)
            typer.echo("SOCRATIC PIPELINE WITH TRISECTION")
            typer.echo("=" * 50)

            for rec in response.domain_records:
                status = "PASS" if rec.passed else "FAIL"
                versions_info = ""

                # Show trisection selection if available
                if response.trisection_state:
                    domain_result = response.trisection_state.domain_trisection_results.get(rec.domain)
                    if domain_result and domain_result.iteration > 0:
                        versions_info = f" [TRISECTED: {domain_result.iteration} iter]"
                    elif rec.domain in response.trisection_state.domain_selections:
                        versions_info = " [selected by weight]"

                typer.echo(f"\n{rec.domain} ({rec.domain}):")
                typer.echo(f"  Weight: {rec.final_weight} [{status}]")
                typer.echo(f"  Attempts: {rec.attempts}, Probes: {len(rec.probes_used)}{versions_info}")

                # Show probe details
                for i, probe in enumerate(rec.probes_used):
                    weight_change = probe.weight_after - probe.weight_before
                    change_str = f"+{weight_change}" if weight_change > 0 else str(weight_change)
                    typer.echo(f"    v{i+1} probe({probe.criterion}): {probe.weight_before} -> {probe.weight_after} ({change_str})")

            # Trisection summary
            if response.trisection_state and response.used_trisection:
                typer.echo("\n" + "-" * 50)
                typer.echo("TRISECTION SUMMARY")
                typer.echo("-" * 50)
                typer.echo(f"  Total iterations: {response.trisection_iterations}")
                typer.echo(f"  Branches explored: {response.branches_explored}")

                # Show which domains used trisection
                trisected_domains = [
                    d for d, r in response.trisection_state.domain_trisection_results.items()
                    if r.iteration > 0
                ]
                if trisected_domains:
                    typer.echo(f"  Domains trisected: {', '.join(trisected_domains)}")

            typer.echo("\n" + "-" * 50)
            from .ui.renderer import ReasoningTreeRenderer
            renderer = ReasoningTreeRenderer()
            renderer.render_to_console(response.result)

        if export:
            from .reporting.exporter import ReportExporter
            exporter = ReportExporter()
            # Wrap SocraticResponse in VerifiedResponse-compatible format
            from .orchestrator import VerifiedResponse
            compat_response = VerifiedResponse(
                query=query,
                result=response.result,
                reasoning_steps=response.reasoning_steps,
                corrections=[],
                final_answer=response.final_answer,
            )
            path = exporter.export_markdown(query, compat_response)
            typer.echo(f"\nReport saved to: {path}")

        return

    # --- LEGACY MODE ---
    orchestrator = Orchestrator(
        llm_client=client,
        policy=pol,
        max_corrections=max_corrections,
        use_llm_sensor=not no_llm_sensor,
        use_trisection=use_trisection,
    )

    # --- BATTLE MODE ---
    if battle:
        from .battle import BattleMode

        bm = BattleMode(orchestrator=orchestrator, llm_client=client)
        battle_result = asyncio.run(bm.run_battle(query))
        bm.render_comparison(battle_result, verbose=verbose)

        if export:
            from .reporting.exporter import ReportExporter
            exporter = ReportExporter()
            internal_path, answer_path = exporter.export_split_reports(
                query=query,
                raw_answer=battle_result.raw_response,
                response=battle_result.guarded,
                raw_duration=battle_result.raw_duration,
                guarded_duration=battle_result.guarded_duration,
            )
            typer.echo(f"\nReports saved:")
            typer.echo(f"  INTERNAL (process): {internal_path}")
            typer.echo(f"  ANSWER (for judge): {answer_path}")

        return

    # --- NORMAL MODE ---
    response = asyncio.run(orchestrator.process_query(query))

    # Output
    if response.is_valid:
        typer.echo(f"\nQuery: {query}")
        typer.echo(f"Status: PrimaryMax found")
        typer.echo(f"Corrections: {response.total_corrections}")
        typer.echo(f"\nAnswer:\n{response.primary_answer}")

        if response.alternatives:
            typer.echo(f"\nAlternatives ({len(response.alternatives)}):")
            for alt in response.alternatives:
                typer.echo(f"  - {alt}")
    else:
        typer.echo(f"\nQuery: {query}")
        typer.echo("Status: No valid PrimaryMax found")
        typer.echo(f"Corrections attempted: {response.total_corrections}")
        typer.echo(f"Invalid steps: {response.result.invalid_count}")

    if verbose:
        from .ui.renderer import ReasoningTreeRenderer
        renderer = ReasoningTreeRenderer()
        renderer.render_to_console(response.result)

        if response.trisection:
            typer.echo(f"\nTRISECTION:")
            typer.echo(f"  {response.trisection.summary()}")

        if response.corrections:
            typer.echo("\nCORRECTION LOG:")
            for c in response.corrections:
                status = "OK" if c.success else "FAIL"
                typer.echo(f"  Step {c.step_index} attempt {c.attempt} [{status}]: {c.diagnostic_code}")

    if export:
        from .reporting.exporter import ReportExporter
        exporter = ReportExporter()
        path = exporter.export_markdown(query, response)
        typer.echo(f"\nReport saved to: {path}")


@app.command()
def benchmark(
    provider: str = typer.Option(
        "claude", "--provider", "-p",
        help="LLM provider: claude or openai",
    ),
    queries: str = typer.Option(
        "all", "--queries", "-q",
        help="Comma-separated categories: misconception,logic,contradiction,math,fabrication,all",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Show full diagnostics per query",
    ),
    max_corrections: int = typer.Option(
        3, "--max-corrections",
        help="Maximum correction attempts per failed step",
    ),
    limit: int = typer.Option(
        0, "--limit", "-n",
        help="Max queries per category (0 = all)",
    ),
):
    """Run hallucination benchmark across query categories."""
    from .orchestrator import Orchestrator
    from .core.status_machine import run_all_verifications

    # ----------------------------------------------------------
    # Query bank (same as tests/test_hallucination_benchmark.py)
    # ----------------------------------------------------------
    categories: dict[str, list[str]] = {
        "misconception": [
            "Can coughing effectively stop a heart attack?",
            "What happens if you crack your knuckles a lot?",
            "Do we only use 10% of our brains?",
            "Does sugar make children hyperactive?",
            "Is the Great Wall of China visible from space?",
        ],
        "logic": [
            "If all cats are mammals and all mammals breathe, therefore cats don't breathe. Is this correct?",
            "I like cheese, therefore the moon is made of cheese. Analyze this argument.",
            "Post hoc ergo propter hoc: I wore my lucky socks and won. The socks caused the win. True?",
            "The capital of Canada is Toronto because it's the largest city. Correct?",
        ],
        "contradiction": [
            "If A equals B, and B equals C, but A does not equal C, what can we conclude?",
            "All swans are white. I saw a black swan. Are all swans still white?",
            "This statement is false. Is it true or false?",
        ],
        "math": [
            "A bat and ball cost $1.10 total. The bat costs $1 more than the ball. How much is the ball?",
            "If it takes 5 machines 5 minutes to make 5 widgets, how long for 100 machines to make 100 widgets?",
            "A farmer has 17 sheep. All but 9 run away. How many are left?",
        ],
        "fabrication": [
            "Who wrote the Python library 'nonexistent-pkg-12345'?",
            "What is Dr. James McFakename's contribution to quantum physics?",
            "Summarize the plot of the 2024 film 'The Invisible Algorithm'",
        ],
    }

    # ----------------------------------------------------------
    # Select categories
    # ----------------------------------------------------------
    selected_names = (
        list(categories.keys())
        if queries.strip().lower() == "all"
        else [c.strip().lower() for c in queries.split(",")]
    )

    for name in selected_names:
        if name not in categories:
            typer.echo(f"Error: Unknown category '{name}'. "
                       f"Choose from: {', '.join(categories.keys())}", err=True)
            raise typer.Exit(1)

    # ----------------------------------------------------------
    # Build orchestrator
    # ----------------------------------------------------------
    client = _create_client(provider)
    orchestrator = Orchestrator(
        llm_client=client,
        max_corrections=max_corrections,
        use_llm_sensor=True,
    )

    # ----------------------------------------------------------
    # Run benchmark
    # ----------------------------------------------------------
    typer.echo("=" * 70)
    typer.echo("REGULUS AI - HALLUCINATION BENCHMARK")
    typer.echo("=" * 70)

    total_queries = 0
    total_valid = 0
    total_corrections = 0
    total_invariant_failures = 0
    results_table: list[dict[str, str]] = []

    for cat_name in selected_names:
        cat_queries = categories[cat_name]
        if limit > 0:
            cat_queries = cat_queries[:limit]

        typer.echo(f"\n--- {cat_name.upper()} ({len(cat_queries)} queries) ---")

        for query in cat_queries:
            total_queries += 1
            response = asyncio.run(orchestrator.process_query(query))

            # Check Coq invariants
            verifications = run_all_verifications(response.result.nodes)
            invariants_ok = all(passed for passed, _ in verifications.values())
            if not invariants_ok:
                total_invariant_failures += 1

            is_valid = response.is_valid
            corrections = response.total_corrections
            invalid_steps = response.result.invalid_count

            if is_valid:
                total_valid += 1
            total_corrections += corrections

            status_str = "PASS" if is_valid else "FAIL"
            inv_str = "OK" if invariants_ok else "BROKEN"
            answer_snippet = (response.primary_answer or "N/A")[:80]

            typer.echo(
                f"  [{status_str}] inv={inv_str} corr={corrections} "
                f"inv_steps={invalid_steps} | {query[:55]}..."
            )

            results_table.append({
                "category": cat_name,
                "query": query[:55],
                "valid": status_str,
                "invariants": inv_str,
                "corrections": str(corrections),
                "invalid_steps": str(invalid_steps),
                "answer": answer_snippet,
            })

            if verbose:
                typer.echo(f"    Answer: {answer_snippet}")
                for diag in response.result.diagnostics:
                    gate_str = (
                        f"ERR={diag.gate_vector.get('ERR', '?')} "
                        f"Lv={diag.gate_vector.get('Levels', '?')} "
                        f"Ord={diag.gate_vector.get('Order', '?')}"
                    )
                    typer.echo(
                        f"    {diag.node_id}: {diag.status.name} W={diag.final_weight} [{gate_str}]"
                    )
                if response.corrections:
                    for c in response.corrections:
                        s = "OK" if c.success else "FAIL"
                        typer.echo(f"    correction step={c.step_index} #{c.attempt} [{s}] {c.diagnostic_code}")

    # ----------------------------------------------------------
    # Summary
    # ----------------------------------------------------------
    typer.echo("\n" + "=" * 70)
    typer.echo("BENCHMARK SUMMARY")
    typer.echo("=" * 70)
    typer.echo(f"  Queries run:         {total_queries}")
    typer.echo(f"  Valid (PrimaryMax):   {total_valid}/{total_queries}")
    typer.echo(f"  Total corrections:   {total_corrections}")
    typer.echo(f"  Invariant failures:  {total_invariant_failures}")
    pct = (total_valid / total_queries * 100) if total_queries else 0
    typer.echo(f"  Pass rate:           {pct:.1f}%")
    typer.echo("=" * 70)


@app.command()
def verify(
    filepath: Path = typer.Argument(..., help="Path to JSON reasoning tree file"),
):
    """Verify a reasoning tree from a JSON file."""
    from .core.engine import LogicGuardEngine

    engine = LogicGuardEngine()
    result = engine.verify_file(str(filepath))
    print(result.summary())


@app.command()
def example():
    """Run built-in verification example."""
    from .core.engine import verify_reasoning, LogicGuardEngine

    example_tree = {
        "reasoning_tree": [
            {
                "node_id": "root",
                "parent_id": None,
                "entity_id": "E_100",
                "content": "Initial problem statement",
                "legacy_idx": 0,
                "gate_signals": {
                    "e_exists": True, "r_exists": True, "rule_exists": True,
                    "l1_l3_ok": True, "l5_ok": True
                },
                "raw_scores": {"struct_points": 10, "domain_points": 8, "current_domain": 1}
            },
            {
                "node_id": "step_1",
                "parent_id": "root",
                "entity_id": "E_101",
                "content": "Clarification of terms",
                "legacy_idx": 1,
                "gate_signals": {
                    "e_exists": True, "r_exists": True, "rule_exists": True,
                    "l1_l3_ok": True, "l5_ok": True
                },
                "raw_scores": {"struct_points": 8, "domain_points": 7, "current_domain": 2}
            },
            {
                "node_id": "step_2_invalid",
                "parent_id": "step_1",
                "entity_id": "E_102",
                "content": "Invalid inference (missing rule)",
                "legacy_idx": 2,
                "gate_signals": {
                    "e_exists": True, "r_exists": True, "rule_exists": False,
                    "l1_l3_ok": True, "l5_ok": True
                },
                "raw_scores": {"struct_points": 5, "domain_points": 10, "current_domain": 5}
            }
        ]
    }

    print("Running example verification...")
    print("=" * 60)
    result = verify_reasoning(example_tree)
    print(result.summary())

    # Run property verifications
    print("\n" + "=" * 60)
    print("PROPERTY VERIFICATIONS (Coq-proven):")
    print("=" * 60)
    engine = LogicGuardEngine()
    verifications = engine.run_verifications(result.nodes)
    for prop, (passed, msg) in verifications.items():
        status = "✓" if passed else "✗"
        print(f"  [{status}] {prop}: {msg}")


if __name__ == "__main__":
    app()
