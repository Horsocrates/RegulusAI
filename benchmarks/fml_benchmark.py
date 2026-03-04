#!/usr/bin/env python3
"""
Benchmark: Follow My Lead / FALLACIES (232-class fallacy classification).

Based on: "Follow My Lead: Knowledge-Augmented LLMs for Logical Fallacy Classification"
(Oct 2025, arxiv 2510.09970) + FALLACIES dataset (Raising-hrx, NAACL 2024).

Baselines (232-way accuracy):
  - ChatGPT-4o: 44.0%
  - Claude-Sonnet-4: 42.2%
  - Gemini-2.5-Flash: 43.5%
  - ChatGPT-4o + AID-LF + Prolog: 47.8%
  - Claude-Sonnet-4 + AID-LF + Prolog: 62.9%

Usage:
    uv run python benchmarks/fml_benchmark.py --limit 50 --provider gpt4o
    uv run python benchmarks/fml_benchmark.py --limit 232 --provider gpt4o --tl
"""

from __future__ import annotations

import sys
import os
import asyncio
import json
import time
from collections import Counter, defaultdict
from typing import Dict, List, Optional

# Force UTF-8
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from logic_benchmark import _create_client

# =============================================================================
#  REGULUS → FALLACIES MAPPING (156 → 232)
# =============================================================================
# Maps each Regulus ID to its closest FALLACIES class name.
# Coverage: not all 156 have equivalents in the 232 taxonomy.
# Many of our IDs are finer-grained variants not in FALLACIES.

REGULUS_TO_FML: Dict[str, str] = {
    # ---- D1: Recognition (Object substitution) ----
    "D1_AD_HOMINEM": "Ad Hominem Abusive",
    "D1_TU_QUOQUE": "Ad Hominem Tu quoque",
    "D1_GUILT_BY_ASSOCIATION": "Ad Hominem Guilt by Association",
    "D1_NAME_CALLING": "Prejudicial Language",
    "D1_TONE_POLICING": "Style Over Substance",
    "D1_ARGUMENT_FROM_MOTIVES": "Bulverism",
    "D1_MIND_READING": "Psychogenetic Fallacy",
    "D1_OTHERING": "Stereotyping the fallacy",
    "D1_REDUCTIO_AD_HITLERUM": "Reductio ad Hitlerum",
    "D1_IDENTITY_FALLACY": "Identity Fallacy",
    "D1_BLOOD_IS_THICKER": "Genetic Fallacy",
    "D1_OLFACTORY_RHETORIC": "Prejudicial Language",
    "D1_PATERNALISM": "Ad Fidentia",
    "D1_RED_HERRING": "Red Herring",
    "D1_STRAW_MAN": "Strawman Fallacy",
    "D1_HALF_TRUTH": "Cherry Picking",
    "D1_LYING_WITH_STATISTICS": "Lying with Statistics",
    "D1_AVAILABILITY_BIAS": "Misleading Vividness",
    "D1_POLLYANNA": "Wishful Thinking",
    "D1_STAR_POWER": "Appeal to Celebrity",
    "D1_TRANSFER": "Appeal to False Authority",
    "D1_JUST_PLAIN_FOLKS": "Appeal to Common Folk",
    "D1_ROMANTIC_REBEL": "Galileo Fallacy",
    "D1_NIMBY": "Avoiding the Issue",
    "D1_DISCIPLINARY_BLINDERS": "Limited Scope",
    "D1_BRAINWASHING": "Hypnotic Bait and Switch",

    # ---- D2: Clarification (Meaning errors) ----
    "D2_EQUIVOCATION": "Equivocation",
    "D2_ETYMOLOGICAL": "Etymological Fallacy",
    "D2_REIFICATION": "Reification",
    "D2_POLITICAL_CORRECTNESS": "Political Correctness Fallacy",
    "D2_HEROES_ALL": "Distinction Without a Difference",
    "D2_EITHER_OR": "False Dilemma",
    "D2_PLAIN_TRUTH": "Alleged Certainty",
    "D2_PASSIVE_VOICE": "Hedging",
    "D2_SNOW_JOB": "Argument by Gibberish",
    "D2_REDUCTIONISM": "Causal Reductionism",
    "D2_OVEREXPLANATION": "Failure to Elucidate",
    "D2_ACTIONS_CONSEQUENCES": "Appeal to Consequences",
    "D2_DIMINISHED_RESPONSIBILITY": "Special Pleading",

    # ---- D3: Framework Selection (Irrelevant criterion) ----
    "D3_BANDWAGON": "Appeal to Popularity",
    "D3_APPEAL_TO_TRADITION": "Appeal to Tradition",
    "D3_APPEAL_TO_NATURE": "Appeal to Nature",
    "D3_MORAL_SUPERIORITY": "Self Righteousness Fallacy",
    "D3_SOLDIERS_HONOR": "Appeal to Accomplishment",
    "D3_MORTIFICATION": "Appeal to Pity",
    "D3_E_FOR_EFFORT": "Notable Effort",
    "D3_ESCHATOLOGICAL": "Appeal to Fear",
    "D3_AFFECTIVE": "Appeal to Emotion",
    "D3_BIG_BUT": "Red Herring",
    "D3_MORAL_LICENSING": "Having Your Cake",
    "D3_COST_BIAS": "Sunk Cost Fallacy",
    "D3_MEASURABILITY": "Fake Precision",
    "D3_PROCRUSTEAN": "Shoehorning",
    "D3_ABLEISM": "Ad Hominem Circumstantial",
    "D3_MOVING_GOALPOSTS": "Moving the Goalposts",
    "D3_CATEGORY_MISMATCH": "Fallacy of Composition",  # Note: not a real ID but kept for robustness

    # ---- D4: Comparison (Comparison errors) ----
    "D4_FALSE_ANALOGY": "Weak Analogy",
    "D4_DOUBLE_STANDARD": "Double Standard",
    "D4_TWO_SIDES": "False Equivalence",
    "D4_HERO_BUSTING": "Nirvana Fallacy",
    "D4_SIMPLETONS": "Faulty Comparison",
    "D4_WORST_NEGATES_BAD": "Relative Privation",
    "D4_SCORING_FALLACY": "Fake Precision",
    "D4_FUNDAMENTAL_ATTRIBUTION": "Psychogenetic Fallacy",

    # ---- D5: Inference (Causal/logical errors) ----
    "D5_NON_SEQUITUR": "Non Sequitur",
    "D5_POST_HOC": "Questionable Cause",
    "D5_OVERGENERALIZATION": "Hasty Generalization",
    "D5_SLIPPERY_SLOPE": "Slippery Slope",
    "D5_EXCLUDED_MIDDLE": "False Dilemma",
    "D5_ARGUMENT_FROM_IGNORANCE": "Argument from Ignorance",
    "D5_ARGUMENT_FROM_CONSEQUENCES": "Appeal to Consequences",
    "D5_ARGUMENT_FROM_SILENCE": "Argument from Silence",
    "D5_HOYLES_FALLACY": "Gamblers Fallacy",
    "D5_PERSONALIZATION": "Spotlight Fallacy",
    "D5_POSITIVE_THINKING": "Wishful Thinking",
    "D5_TRUST_YOUR_GUT": "Appeal to Intuition",
    "D5_MAGICAL_THINKING": "Magical Thinking",
    "D5_SCAPEGOATING": "Scapegoating",
    "D5_WHERES_SMOKE": "Questionable Cause",
    "D5_WORST_CASE": "Slippery Slope",
    "D5_DRAW_OWN_CONCLUSION": "Jumping to Conclusions",
    "D5_SILENT_MAJORITY": "Appeal to Common Belief",
    "D5_WISDOM_OF_CROWD": "Appeal to Common Belief",

    # ---- D6: Reflection (Reflection errors) ----
    "D6_APPEAL_TO_CLOSURE": "Appeal to Closure",
    "D6_ARGUMENT_FROM_INCREDULITY": "Argument from Incredulity",
    "D6_SUNK_COST": "Sunk Cost Fallacy",
    "D6_ARGUMENT_FROM_INERTIA": "Appeal to Tradition",
    "D6_DEFAULT_BIAS": "Appeal to Normality",
    "D6_CALLING_CARDS": "Appeal to Accomplishment",
    "D6_THIRD_PERSON_EFFECT": "Blind Authority Fallacy",
    "D6_DUNNING_KRUGER": "Blind Authority Fallacy",
    "D6_ALL_CROOKS": "Hasty Generalization",
    "D6_ESSENTIALIZING": "Stereotyping the fallacy",
    "D6_NOTHING_NEW": "Argument from Age",
    "D6_PARALYSIS_OF_ANALYSIS": "Inconsistency",
    "D6_FREE_SPEECH": "Red Herring",
    "D6_MAGIC_WAND": "Nirvana Fallacy",
    "D6_MYOB": "Avoiding the Issue",
    "D6_UNINTENDED_CONSEQUENCES": "Appeal to Consequences",
    "D6_WRONG_MESSAGE": "Red Herring",
    "D6_FINISH_THE_JOB": "Sunk Cost Fallacy",
    "D6_VENTING": "Appeal to Emotion",
    "D6_NON_RECOGNITION": "Willed Ignorance",
    "D6_DEFENSIVENESS": "Ad Hominem Circumstantial",
    "D6_DELIBERATE_IGNORANCE": "Willed Ignorance",

    # ---- T1A: Type 1 condition violations (structure) ----
    "T1A_COMPLEX_QUESTION": "Complex Question Fallacy",
    "T1A_TABOO": "Appeal to Force",
    "T1A_VENUE_FALLACY": "Avoiding the Issue",

    # ---- T1B: Type 1 condition violations (manipulation) ----
    "T1B_SCARE_TACTICS": "Appeal to Fear",
    "T1B_APPEAL_TO_PITY": "Appeal to Pity",
    "T1B_PLAYING_ON_EMOTION": "Appeal to Emotion",
    "T1B_SAVE_THE_CHILDREN": "Appeal to Pity",
    "T1B_THE_POUT": "Appeal to Spite",
    "T1B_F_BOMB": "Prejudicial Language",
    "T1B_SHOPPING_HUNGRY": "Appeal to Desperation",
    "T1B_WE_HAVE_TO_DO_SOMETHING": "Appeal to Desperation",
    "T1B_AD_BACULUM": "Appeal to Force",
    "T1B_BRIBERY": "Argument to the Purse",
    "T1B_PROSOPOLOGY": "Anthropomorphism",
    "T1B_APPEASEMENT": "Argument to Moderation",
    "T1B_APPEAL_TO_HEAVEN": "Appeal to Heaven",
    "T1B_ALPHABET_SOUP": "Alphabet Soup",
    "T1B_AD_MYSTERIAM": "Appeal to Complexity",
    "T1B_PSEUDO_ESOTERIC": "Appeal to Complexity",
    "T1B_BLIND_LOYALTY": "Blind Authority Fallacy",
    "T1B_STANDARD_VERSION": "Proof by Intimidation",
    "T1B_BIG_BRAIN_LITTLE_BRAIN": "Appeal to Stupidity",
    "T1B_BIG_LIE": "Spin Doctoring",
    "T1B_GASLIGHTING": "Spin Doctoring",
    "T1B_ALTERNATIVE_TRUTH": "Spin Doctoring",
    "T1B_PLAUSIBLE_DENIABILITY": "Hedging",
    "T1B_MALA_FIDES": "Spin Doctoring",
    "T1B_DOG_WHISTLE": "Prejudicial Language",
    "T1B_SCRIPTED_MESSAGE": "Spin Doctoring",
    "T1B_OCTOBER_SURPRISE": "Spin Doctoring",
    "T1B_NARRATIVE_FALLACY": "Spin Doctoring",
    "T1B_INFOTAINMENT": "Hypnotic Bait and Switch",
    "T1B_THOUSAND_FLOWERS": "Argument by Gibberish",
    "T1B_TINA": "False Dilemma",
    "T1B_NO_DISCUSSION": "Appeal to Force",
    "T1B_JUST_DO_IT": "Appeal to Force",

    # ---- T3: Type 3 sequence violations ----
    "T3_CIRCULAR_REASONING": "Circular Reasoning",
    "T3_RATIONALIZATION": "Rationalization",
    "T3_BURDEN_SHIFTING": "Shifting of the Burden of Proof",

    # ---- T4: Type 4 syndromes ----
    "T4_CONFIRMATION_BIAS": "Biased Sample Fallacy",
    "T4_ECHO_CHAMBER": "Gadarene Swine Fallacy",
    "T4_GROUPTHINK": "Gadarene Swine Fallacy",
    "T4_COGNITIVE_CLOSURE": "Jumping to Conclusions",
    "T4_COMPARTMENTALIZATION": "Kettle Logic",
    "T4_MOTIVATED_REASONING": "Rationalization",

    # ---- T5: Type 5 context-dependent ----
    "T5_AFFECTIVE_REASONING": "Appeal to Emotion",
    "T5_APPEAL_NATURE_CONTEXT": "Appeal to Nature",
    "T5_APPEAL_TRADITION_CONTEXT": "Appeal to Tradition",
    "T5_ARGUMENT_CONSEQUENCES_CONTEXT": "Appeal to Consequences",
    "T5_ARGUMENT_SILENCE_CONTEXT": "Argument from Silence",
    "T5_TRUST_GUT_CONTEXT": "Appeal to Intuition",
}

# Reverse: FALLACIES name → set of Regulus IDs
FML_TO_REGULUS: Dict[str, set] = {}
for rid, fname in REGULUS_TO_FML.items():
    FML_TO_REGULUS.setdefault(fname, set()).add(rid)

# How many of the 232 FALLACIES classes we cover
_COVERED_FML = set(REGULUS_TO_FML.values())


def load_fml_data(data_path: str, limit: int = 232, first_per_type: bool = True) -> List[Dict]:
    """Load FALLACIES test data.

    Args:
        data_path: Path to step_fallacy.test.jsonl
        limit: Max number of examples
        first_per_type: If True, take first example per fallacy type (like Follow My Lead)
    """
    examples = []
    with open(data_path, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["label"] == 1:  # only fallacious examples
                examples.append(d)

    if first_per_type:
        # Take first example per fallacy type
        seen = set()
        filtered = []
        for ex in examples:
            if ex["fallacy"] not in seen:
                seen.add(ex["fallacy"])
                filtered.append(ex)
        examples = filtered

    return examples[:limit]


async def run_fml_benchmark(
    examples: List[Dict], provider: str, concurrency: int, mode: str = "multigate"
) -> tuple:
    """Run classification on FML examples. Returns (results, tl_log)."""
    from regulus.fallacies.llm_extractor import LLMFallacyExtractor

    client = _create_client(provider)
    extractor = LLMFallacyExtractor(client, mode=mode)

    sem = asyncio.Semaphore(concurrency)

    async def classify_one(idx: int, ex: Dict) -> Dict:
        text = ex["step"]
        gold_fallacy = ex["fallacy"]

        async with sem:
            try:
                start = time.time()
                result = await extractor.extract(text)
                elapsed = time.time() - start

                return {
                    "idx": idx,
                    "gold_fallacy": gold_fallacy,
                    "text_preview": text[:120],
                    "predicted_id": result.primary_fallacy_id,
                    "predicted_fml": REGULUS_TO_FML.get(result.primary_fallacy_id, "UNMAPPED"),
                    "confidence": result.confidence,
                    "reasoning": result.reasoning,
                    "elapsed": elapsed,
                }
            except Exception as e:
                return {
                    "idx": idx,
                    "gold_fallacy": gold_fallacy,
                    "text_preview": text[:120],
                    "predicted_id": "ERROR",
                    "predicted_fml": "ERROR",
                    "confidence": 0,
                    "reasoning": str(e),
                    "elapsed": 0,
                }

    tasks = [classify_one(i, ex) for i, ex in enumerate(examples)]
    print(f"  Processing {len(examples)} examples (concurrency={concurrency})...", flush=True)
    start = time.time()
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start
    print(f"  Done in {elapsed:.1f}s ({elapsed/len(examples):.1f}s/ex avg)", flush=True)

    tl_log = list(extractor.tl_log) if hasattr(extractor, 'tl_log') else []
    extractor.clear_cache()
    return list(results), tl_log


def analyze_fml_results(results: List[Dict], tl_log: list = None):
    """Analyze FML benchmark results."""
    from rich.console import Console
    from rich.table import Table
    from rich import box

    console = Console(force_terminal=True)
    total = len(results)

    # Metrics
    exact_match = 0  # predicted_fml == gold_fallacy (case-insensitive)
    covered = 0  # gold_fallacy is in our mapping coverage
    covered_match = 0  # among covered, how many match

    per_fallacy = defaultdict(lambda: {"total": 0, "match": 0, "predictions": []})

    for r in results:
        gold = r["gold_fallacy"]
        pred_fml = r["predicted_fml"]

        is_match = pred_fml.lower().strip() == gold.lower().strip()
        is_covered = gold in _COVERED_FML

        if is_match:
            exact_match += 1
        if is_covered:
            covered += 1
            if is_match:
                covered_match += 1

        per_fallacy[gold]["total"] += 1
        per_fallacy[gold]["match"] += int(is_match)
        per_fallacy[gold]["predictions"].append((r["predicted_id"], pred_fml))

    # ---- Overall ----
    console.print()
    console.print("[bold cyan]=== Follow My Lead (FALLACIES) Benchmark ===[/bold cyan]")
    console.print()

    summary = Table(title="Overall Results", box=box.ROUNDED)
    summary.add_column("Metric", style="bold")
    summary.add_column("Value", justify="right")
    summary.add_column("Notes")
    summary.add_row("Total examples", str(total), "")
    summary.add_row(
        "[bold yellow]Exact match accuracy[/bold yellow]",
        f"[bold yellow]{exact_match} ({exact_match/total:.1%})[/bold yellow]",
        "predicted FML name == gold (232-way)",
    )
    summary.add_row(
        "Coverage",
        f"{covered} ({covered/total:.1%})",
        f"gold fallacy has a Regulus mapping ({len(_COVERED_FML)}/{232} classes covered)",
    )
    if covered > 0:
        summary.add_row(
            "Accuracy on covered",
            f"{covered_match} ({covered_match/covered:.1%})",
            "among gold fallacies we can map to",
        )
    console.print(summary)

    # Baselines comparison
    console.print()
    console.print("[bold]Comparison with Follow My Lead baselines (232-way):[/bold]")
    console.print(f"  ChatGPT-4o baseline: 44.0%")
    console.print(f"  Claude-Sonnet-4:     42.2%")
    console.print(f"  [bold]Ours:                {exact_match/total:.1%}[/bold]")

    # ---- Per-fallacy misses ----
    misses = [(g, s) for g, s in per_fallacy.items() if s["match"] == 0]
    hits = [(g, s) for g, s in per_fallacy.items() if s["match"] > 0]

    if hits:
        console.print()
        console.print(f"[green]Correct ({len(hits)} types):[/green]")
        for g, s in sorted(hits):
            preds = s["predictions"]
            console.print(f"  [green]✓[/green] {g:45s} ← {preds[0][0]} → {preds[0][1]}")

    if misses and len(misses) <= 60:
        console.print()
        console.print(f"[red]Missed ({len(misses)} types):[/red]")
        for g, s in sorted(misses)[:40]:
            pred_id, pred_fml = s["predictions"][0]
            console.print(
                f"  [red]✗[/red] {g:45s} ← {pred_id} → {pred_fml}"
            )

    # ---- TL log ----
    if tl_log:
        overrides = [e for e in tl_log if e.get("tl_override")]
        console.print()
        console.print(f"[bold magenta]TL: {len(tl_log)} total, {len(overrides)} overrides[/bold magenta]")


def main():
    limit = 50
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        if idx + 1 < len(sys.argv):
            limit = int(sys.argv[idx + 1])

    provider = "gpt4o"
    if "--provider" in sys.argv:
        idx = sys.argv.index("--provider")
        if idx + 1 < len(sys.argv):
            provider = sys.argv[idx + 1]

    concurrency = 5
    if "--concurrency" in sys.argv:
        idx = sys.argv.index("--concurrency")
        if idx + 1 < len(sys.argv):
            concurrency = int(sys.argv[idx + 1])

    use_tl = "--tl" in sys.argv
    mode = "multigate_tl" if use_tl else "multigate"

    data_path = os.path.join(os.path.dirname(__file__), "..", "_data", "FALLACIES", "step_fallacy.test.jsonl")
    if not os.path.exists(data_path):
        print(f"ERROR: {data_path} not found. Run: git clone https://github.com/Raising-hrx/FALLACIES.git _data/FALLACIES")
        sys.exit(1)

    print(f"Loading FALLACIES dataset...", flush=True)
    examples = load_fml_data(data_path, limit=limit)
    print(f"Using {len(examples)} examples (1 per fallacy type), provider={provider}, mode={mode}", flush=True)
    print(f"Our mapping covers {len(_COVERED_FML)}/232 FALLACIES classes", flush=True)

    print(f"\nRunning {mode} classification...", flush=True)
    results, tl_log = asyncio.run(run_fml_benchmark(examples, provider, concurrency, mode=mode))

    analyze_fml_results(results, tl_log=tl_log)


if __name__ == "__main__":
    main()
