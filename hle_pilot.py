#!/usr/bin/env python3
"""
Regulus v3 HLE Pilot — Two-Agent Dialogue on real HLE questions
Run: python hle_pilot.py hle_seed_math_10q.json
Env vars:
  ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN — API key
  ANTHROPIC_BASE_URL — API base URL (default: Anthropic)
  REGULUS_MODEL — override model (default: see PROFILES below)
  REGULUS_PROFILE — "opus" | "glm5" | "glm5-air" (default: glm5)
"""

import anthropic
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load .env: try local first, then walk up to find project root .env
load_dotenv(override=True)
_here = Path(__file__).resolve().parent
for _ancestor in [_here] + list(_here.parents):
    _candidate = _ancestor / ".env"
    if _candidate.exists() and _candidate != _here / ".env":
        load_dotenv(_candidate, override=False)  # fill missing keys from root
        break

# Z.ai uses ZAI_API_KEY → map to ANTHROPIC_AUTH_TOKEN for SDK compatibility
if os.environ.get("ZAI_API_KEY") and not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
    os.environ["ANTHROPIC_AUTH_TOKEN"] = os.environ["ZAI_API_KEY"]

# Force unbuffered output + safe encoding for Windows cp1251
import functools
import io
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
print = functools.partial(print, flush=True)

# ─── MODEL PROFILES ──────────────────────────────────────────────────

PROFILES = {
    "opus": {
        "model": "claude-opus-4-6",
        "judge_model": "claude-sonnet-4-20250514",
        "base_url": None,  # default Anthropic
        "thinking": True,
        "thinking_budget": 64000,
        "max_output": 128000,             # must be > thinking_budget
    },
    "glm5": {
        "model": "glm-5",
        "judge_model": "glm-5",          # GLM-5 for judge Stage 3 too (cheap)
        "base_url": "https://api.z.ai/api/anthropic",
        "thinking": True,                 # GLM-5 supports thinking via Z.ai
        "thinking_budget": 64000,
        "max_output": 128000,             # must be > thinking_budget
    },
    "glm5-air": {
        "model": "glm-4.5-air",
        "judge_model": "glm-4.5-air",
        "base_url": "https://api.z.ai/api/anthropic",
        "thinking": False,
        "thinking_budget": 0,
        "max_output": 32000,
    },
}

# ─── CONFIG (resolved from profile + env overrides) ──────────────────

PROFILE_NAME = os.environ.get("REGULUS_PROFILE", "glm5")
if PROFILE_NAME not in PROFILES:
    print(f"Unknown profile '{PROFILE_NAME}'. Available: {list(PROFILES.keys())}")
    sys.exit(1)

_P = PROFILES[PROFILE_NAME]

MODEL = os.environ.get("REGULUS_MODEL", _P["model"])
JUDGE_MODEL = _P["judge_model"]
# Profile's base_url takes precedence; env var only used if profile says None
BASE_URL = _P["base_url"]
THINKING_ENABLED = _P["thinking"]
THINKING_BUDGET = _P["thinking_budget"]
MAX_OUTPUT = _P["max_output"]
SKILLS_DIR = Path("skills")
RUNS_DIR = Path("runs_hle")


# ─── AGENT CLASS ──────────────────────────────────────────────────────

class Agent:
    """Thin wrapper around Messages API with optional thinking support."""

    def __init__(self, name: str, system_prompt: str):
        self.name = name
        # Build client with optional base_url for Z.ai / OpenRouter
        client_kwargs = {}
        if BASE_URL:
            client_kwargs["base_url"] = BASE_URL
        # Z.ai uses ANTHROPIC_AUTH_TOKEN, Anthropic uses ANTHROPIC_API_KEY
        api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            client_kwargs["api_key"] = api_key
        self.client = anthropic.Anthropic(**client_kwargs)
        self.system_prompt = system_prompt
        self.messages = []
        self.total_input = 0
        self.total_output = 0
        self.call_count = 0

    def send(self, content: str, max_retries: int = 3) -> tuple[str, str]:
        self.messages.append({"role": "user", "content": content})

        last_error = None
        for attempt in range(max_retries):
            try:
                # Build request kwargs conditionally
                kwargs = {
                    "model": MODEL,
                    "max_tokens": MAX_OUTPUT,
                    "messages": self.messages,
                }

                # Thinking: only if enabled (Anthropic Opus supports it, GLM-5 may not)
                if THINKING_ENABLED:
                    kwargs["thinking"] = {
                        "type": "enabled",
                        "budget_tokens": THINKING_BUDGET
                    }

                # System prompt: use cache_control only for Anthropic native
                if BASE_URL is None:
                    kwargs["system"] = [{
                        "type": "text",
                        "text": self.system_prompt,
                        "cache_control": {"type": "ephemeral"}
                    }]
                else:
                    kwargs["system"] = self.system_prompt

                with self.client.messages.stream(**kwargs) as stream:
                    response = stream.get_final_message()
                break  # Success
            except (IndexError, anthropic.APIStatusError, anthropic.APIConnectionError) as e:
                last_error = e
                wait = 2 ** attempt * 5  # 5s, 10s, 20s
                print(f"    [retry {attempt+1}/{max_retries}] {type(e).__name__}: {e}")
                print(f"    [waiting {wait}s before retry...]")
                time.sleep(wait)
        else:
            # All retries exhausted — re-raise
            self.messages.pop()  # Remove the user message we added
            raise last_error

        text_parts = []
        thinking_parts = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif getattr(block, 'type', '') == "thinking":
                thinking_parts.append(block.thinking)

        text = "\n".join(text_parts)
        thinking = "\n---\n".join(thinking_parts) if thinking_parts else ""

        self.messages.append({"role": "assistant", "content": response.content})

        self.total_input += response.usage.input_tokens
        self.total_output += response.usage.output_tokens
        self.call_count += 1

        cache_read = getattr(response.usage, 'cache_read_input_tokens', 0) or 0
        if cache_read:
            print(f"    [cache hit: {cache_read} tokens]")

        return text, thinking

    def stats(self) -> dict:
        return {
            "calls": self.call_count,
            "input_tokens": self.total_input,
            "output_tokens": self.total_output,
        }


# ─── HELPERS ──────────────────────────────────────────────────────────

def extract(text: str, tag: str) -> str:
    """Extract content from XML tag."""
    match = re.search(f"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return match.group(1).strip() if match else ""

def load_skill(filename: str) -> str:
    """Load skill file content."""
    path = SKILLS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    print(f"  WARNING: Skill not found: {path}")
    return ""

def build_tl_prompt() -> str:
    """Build Team Lead system prompt from skills."""
    analyze = load_skill("analyze-v2.md")
    d6_ask = load_skill("d6-ask.md")
    d6_reflect = load_skill("d6-reflect.md")

    return f"""# TEAM LEAD

{analyze}

<SKILL_D6_ASK>
{d6_ask}
</SKILL_D6_ASK>

<SKILL_D6_REFLECT>
{d6_reflect}
</SKILL_D6_REFLECT>
"""

def build_worker_prompt() -> str:
    """Build Worker system prompt from skills."""
    d1 = load_skill("d1-recognize.md")
    d2 = load_skill("d2-clarify.md")
    d3 = load_skill("d3-framework.md")
    d4 = load_skill("d4-compare.md")
    d5 = load_skill("d5-infer.md")

    return f"""# WORKER — Domain Reasoning Engine

You execute one reasoning domain at a time as instructed by Team Lead.
Each domain has specific skills loaded below.
Execute the domain specified in the instruction. Be thorough and precise.
If you find contradictions with provided context, FLAG them explicitly.
Always include confidence assessment with justification.

<SKILL_D1>
{d1}
</SKILL_D1>

<SKILL_D2>
{d2}
</SKILL_D2>

<SKILL_D3>
{d3}
</SKILL_D3>

<SKILL_D4>
{d4}
</SKILL_D4>

<SKILL_D5>
{d5}
</SKILL_D5>
"""


# ─── LLM JUDGE ───────────────────────────────────────────────────────

def normalize_answer(text: str) -> str:
    """Normalize answer string for comparison.
    Strips whitespace, lowercases, removes common formatting variations.
    """
    s = text.strip().lower()
    # Remove LaTeX wrappers
    s = re.sub(r'\$+', '', s)
    s = re.sub(r'\\text\{([^}]*)\}', r'\1', s)
    s = re.sub(r'\\mathrm\{([^}]*)\}', r'\1', s)
    s = re.sub(r'\\textbf\{([^}]*)\}', r'\1', s)
    # Normalize subscripts: ₂ → 2, ₃ → 3, etc.
    sub_map = str.maketrans('₀₁₂₃₄₅₆₇₈₉', '0123456789')
    s = s.translate(sub_map)
    # Normalize superscripts: ² → 2, ³ → 3, etc.
    sup_map = str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹', '0123456789')
    s = s.translate(sup_map)
    # Remove common wrapper words
    for prefix in ['the answer is ', 'answer: ', 'final answer: ']:
        if s.startswith(prefix):
            s = s[len(prefix):]
    # Normalize whitespace around commas and colons
    s = re.sub(r'\s*,\s*', ', ', s)
    s = re.sub(r'\s*:\s*', ':', s)
    # Collapse multiple spaces
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def extract_core_answer(model_answer: str) -> str:
    """Extract the core answer from model output that may contain explanations.
    Tries XML tags first, then markdown patterns, then first substantive line.
    """
    # Try common XML tags
    for tag in ['final_answer', 'answer', 'result']:
        match = re.search(f"<{tag}>(.*?)</{tag}>", model_answer, re.DOTALL)
        if match:
            return match.group(1).strip()

    # Try markdown bold "**Answer:** VALUE" or "**Answer:** ... **VALUE**"
    # Pattern: **Answer:** followed by value on same line
    md_match = re.search(r'\*\*(?:Final\s+)?Answer[:\s]*\*\*[:\s]*(.+?)(?:\n|$)', model_answer, re.IGNORECASE)
    if md_match:
        ans_line = md_match.group(1).strip()
        # Strip trailing markdown bold markers
        ans_line = re.sub(r'\*+$', '', ans_line).strip()
        return ans_line

    # Try "answer: VALUE" at start of a line (YAML-like from structured output)
    yaml_match = re.search(r'^answer:\s*(.+?)$', model_answer, re.MULTILINE | re.IGNORECASE)
    if yaml_match:
        return yaml_match.group(1).strip()

    # If answer is short (< 200 chars), it's probably just the answer
    if len(model_answer.strip()) < 200:
        return model_answer.strip()

    # Otherwise take first non-empty line that looks like an answer
    # Strip markdown bold/italic markers before checking prefix
    for line in model_answer.strip().split('\n'):
        stripped = line.strip()
        plain = re.sub(r'^\*+|\*+$', '', stripped).strip()  # remove leading/trailing bold/italic
        if plain and not plain.startswith('#') and not plain.startswith('-'):
            return stripped

    return model_answer.strip()[:200]


def judge_answer(model_answer: str, expected_answer: str, answer_type: str) -> bool:
    """
    Compare model answer to expected.
    For multipleChoice: direct letter comparison.
    For exactMatch: string pre-check first, then LLM judge as fallback.

    P0 FIX (2026-02-17): Added string equality pre-check before LLM judge.
    Previous bug: LLM judge did semantic similarity instead of exact match,
    marking S₄≠D₂ as "correct" and "2,1,0"≠"2,1,1" as "correct".
    """
    if not model_answer:
        return False

    if answer_type == "multipleChoice":
        # Extract letter from model answer
        match = re.search(r'\b([A-E])\b', model_answer.strip())
        if match:
            return match.group(1).upper() == expected_answer.strip().upper()
        return False

    # ─── exactMatch: THREE-STAGE JUDGE ───
    # Stage 1: String equality (fast, reliable)
    # Stage 2: Numeric equivalence (for mathematical answers)
    # Stage 3: LLM judge (only for genuinely ambiguous formatting)

    core_answer = extract_core_answer(model_answer)
    norm_model = normalize_answer(core_answer)
    norm_expected = normalize_answer(expected_answer)

    print(f"    [Judge] Normalized model:    '{norm_model[:80]}'")
    print(f"    [Judge] Normalized expected: '{norm_expected[:80]}'")

    # ── STAGE 1: Exact string match after normalization ──
    if norm_model == norm_expected:
        print(f"    [Judge] Stage 1: EXACT STRING MATCH → correct")
        return True

    # Check if normalized expected is contained as a distinct answer in model output
    # (handles cases like "S₄" in "The point group is S₄")
    if len(norm_expected) >= 1 and norm_expected in norm_model:
        # Verify it's not a substring of a different answer
        # e.g., "1" should not match "21" — require word boundary
        pattern = r'(?<![a-z0-9])' + re.escape(norm_expected) + r'(?![a-z0-9])'
        if re.search(pattern, norm_model):
            print(f"    [Judge] Stage 1: Expected found as distinct token in model answer → correct")
            return True

    # ── STAGE 2: Numeric equivalence ──
    try:
        # Try parsing both as numbers (handles "0.5" vs "1/2" vs ".5")
        def parse_number(s):
            s = s.strip()
            if '/' in s:
                parts = s.split('/')
                if len(parts) == 2:
                    return float(parts[0]) / float(parts[1])
            return float(s)

        num_model = parse_number(norm_model)
        num_expected = parse_number(norm_expected)
        # Use relative tolerance for large numbers, absolute for small
        if num_expected != 0:
            rel_diff = abs(num_model - num_expected) / abs(num_expected)
            is_match = rel_diff < 1e-9
        else:
            is_match = abs(num_model) < 1e-9
        if is_match:
            print(f"    [Judge] Stage 2: NUMERIC MATCH ({num_model} ≈ {num_expected}) → correct")
            return True
        else:
            print(f"    [Judge] Stage 2: NUMERIC MISMATCH ({num_model} ≠ {num_expected}) → incorrect")
            return False
    except (ValueError, ZeroDivisionError):
        pass  # Not numeric — continue to Stage 3

    # ── STAGE 2.5: Short answer quick-reject ──
    # If both answers are short (< 30 chars) and clearly different after normalization,
    # reject without LLM. This catches S₄≠D₂, "2, 1, 1"≠"2, 1, 0", etc.
    if len(norm_model) < 30 and len(norm_expected) < 30:
        # Both are short, normalized, and don't match — they're different
        print(f"    [Judge] Stage 2.5: Short answers differ after normalization → incorrect")
        return False

    # ── STAGE 3: LLM judge (only for complex/long answers where formatting varies) ──
    print(f"    [Judge] Stage 3: LLM judge (answers too long/complex for string match)...")
    client_kwargs = {}
    if BASE_URL:
        client_kwargs["base_url"] = BASE_URL
    api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        client_kwargs["api_key"] = api_key
    client = anthropic.Anthropic(**client_kwargs)
    judge_prompt = f"""You are a STRICT equivalence judge. Your task: determine if the model's answer
is EXACTLY EQUIVALENT to the expected answer.

Expected answer: {expected_answer}
Model's answer: {core_answer}

STRICT RULES — read carefully:
1. Extract the CORE factual answer (ignore explanations, confidence, caveats)
2. The answer must be EXACTLY the same value/entity/concept
3. EQUIVALENT (return "correct"):
   - Formatting only: "FeCl₂" = "FeCl2", "H₂O" = "H2O"
   - LaTeX vs text: "$\\pi$" = "π" = "pi"
   - Units stated vs implied: "5 meters" = "5" (if units clear from context)
   - Trivial rephrasing: "sodium chloride" = "NaCl"
4. NOT EQUIVALENT (return "incorrect"):
   - Different values: "5.57" ≠ "5.58", "42" ≠ "43"
   - Different entities: "D₂" ≠ "S₄", "glucose" ≠ "fructose"
   - Different lists: "2, 1, 1" ≠ "2, 1, 0" (even one element differs = different)
   - Partial match: "A and B" ≠ "A" (incomplete answer)
   - Superset/subset: model says more than expected ≠ correct
5. When in doubt → "incorrect"

Respond with EXACTLY one word: "correct" or "incorrect"."""

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=JUDGE_MODEL,
                max_tokens=10,
                messages=[{"role": "user", "content": judge_prompt}]
            )
            judge_text = response.content[0].text.strip().lower()
            # "incorrect" contains "correct" — must check "incorrect" first
            if "incorrect" in judge_text:
                print(f"    [Judge] Stage 3: LLM says incorrect")
                return False
            if "correct" in judge_text:
                print(f"    [Judge] Stage 3: LLM says correct")
                return True
            # Unexpected response — treat as incorrect
            print(f"    [Judge] Stage 3: Unexpected LLM response: '{judge_text}' → incorrect")
            return False
        except Exception as e:
            if attempt < 2:
                print(f"    [judge retry {attempt+1}] {e}")
                time.sleep(5)
            else:
                raise


# ─── DIALOGUE RUNNER ──────────────────────────────────────────────────

def run_question(question: dict, run_dir: Path) -> dict:
    """Run two-agent dialogue on a single HLE question.

    CRITICAL: Only question["question"] is sent to agents.
    answer, rationale, and other fields are NEVER in agent prompts.
    """

    q_text = question["question"]
    q_id = question["hle_id"]

    print(f"\n{'='*60}")
    print(f"  QUESTION: {q_id}")
    print(f"  Subject: {question['raw_subject']}")
    print(f"  Type: {question['answer_type']}")
    # NOTE: expected answer is printed for operator only, NEVER sent to agents
    print(f"  Expected: {question['answer'][:80]}...")
    print(f"{'='*60}\n")

    # Initialize agents
    tl = Agent("team_lead", build_tl_prompt())
    worker = Agent("worker", build_worker_prompt())

    dialogue_log = []
    start_time = time.time()

    def log(sender, receiver, msg_type, content, thinking="", **meta):
        entry = {
            "ts": datetime.now(tz=None).isoformat(),
            "from": sender, "to": receiver,
            "type": msg_type, "content": content[:3000],
            **meta
        }
        if thinking:
            entry["thinking_excerpt"] = thinking[:2000]
        dialogue_log.append(entry)

        with open(run_dir / "dialogue.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ── PHASE 0: Team Lead decomposes question ──
    print("  [TL] Phase 0: Analyzing question...")
    tl_text, tl_think = tl.send(
        f"MODE: ask\nCONTEXT: initial\n\n"
        f"Question:\n{q_text}\n\n"
        f"Analyze this question. Classify it (including calibration_level), "
        f"generate your_components, create initial conspectus, and produce "
        f"the first worker instruction for D1.\n\n"
        f"CRITICAL: Your <worker_instruction> MUST include the FULL QUESTION TEXT verbatim. "
        f"Worker is a separate agent and does NOT have access to the question unless you include it.\n\n"
        f"Remember to output <conspectus>, <verdict>, and <worker_instruction> blocks."
    )
    log("team_lead", "worker", "init", tl_text, tl_think, domain="D1")

    instruction = extract(tl_text, "worker_instruction")
    if not instruction:
        instruction = (
            f"Execute D1 Recognition on this question.\n\n"
            f"## FULL QUESTION TEXT:\n{q_text}\n\n"
            f"Identify all elements, roles, rules, dependencies. "
            f"What makes this problem hard?"
        )

    conspectus = extract(tl_text, "conspectus") or ""

    # ── PHASE 1-5: Domain-by-domain dialogue ──
    domains = ["D1", "D2", "D3", "D4", "D5"]
    final_answer = None

    for domain in domains:
        print(f"  [Worker] Executing {domain}...")

        w_text, w_think = worker.send(instruction)
        log("worker", "team_lead", "domain_output", w_text, w_think, domain=domain)

        depth = "full"
        print(f"  [TL] Reflecting on {domain} ({depth})...")

        tl_text, tl_think = tl.send(
            f"MODE: reflect\nDEPTH: {depth}\nDOMAIN: {domain}\n\n"
            f"Worker {domain} output:\n{w_text}\n\n"
            f"Evaluate this output. Update your conspectus. Decide verdict. "
            f"If pass, produce instruction for next domain. "
            f"Output <conspectus>, <verdict>, and <worker_instruction> blocks."
        )

        verdict = extract(tl_text, "verdict").strip().lower()
        if not verdict:
            for v in ["threshold_reached", "pass", "iterate", "paradigm_shift", "plateau"]:
                if v in tl_text.lower():
                    verdict = v
                    break
            if not verdict:
                verdict = "pass"

        log("team_lead", "team_lead", "reflect", tl_text, tl_think,
            domain=domain, verdict=verdict)

        new_conspectus = extract(tl_text, "conspectus")
        if new_conspectus:
            conspectus = new_conspectus
            (run_dir / "conspectus.md").write_text(conspectus, encoding="utf-8")

        print(f"  [TL] Verdict: {verdict}")

        # Handle terminal verdicts
        if verdict in ("threshold_reached", "plateau", "fundamentally_uncertain"):
            fa_block = extract(tl_text, "final_answer")
            if fa_block:
                final_answer = fa_block.strip()

            if not final_answer:
                # Ask TL for clean answer
                print("  [TL] Extracting clean answer...")
                tl_extract, _ = tl.send(
                    "Output ONLY the final answer. No explanation. No analysis.\n"
                    "Format: <final_answer>YOUR ANSWER HERE</final_answer>\n\n"
                    "CRITICAL — EXACT FORM PRESERVATION:\n"
                    "- Output the EXACT expression from your derivation, not a simplification\n"
                    "- Do NOT drop terms, round, or approximate\n"
                    "- Every dropped term = wrong answer for exact match grading\n"
                )
                fa_block = extract(tl_extract, "final_answer")
                final_answer = fa_block if fa_block else tl_extract.strip()

            print(f"  [Extract] Raw answer: {repr(final_answer[:100])}")
            break

        # Handle iteration
        if verdict == "iterate":
            print(f"  [TL] Iterating on {domain}...")
            iter_instruction = extract(tl_text, "worker_instruction")
            if iter_instruction:
                w_redo, w_think = worker.send(iter_instruction)
                log("worker", "team_lead", "domain_output", w_redo, w_think,
                    domain=f"{domain}_redo")

                tl_redo, tl_think = tl.send(
                    f"MODE: reflect\nDEPTH: {depth}\nDOMAIN: {domain}_redo\n\n"
                    f"Worker {domain} revised output:\n{w_redo}\n\n"
                    f"Output <conspectus>, <verdict>, and <worker_instruction> blocks."
                )
                verdict = extract(tl_redo, "verdict").strip().lower() or "pass"
                log("team_lead", "team_lead", "reflect", tl_redo, tl_think,
                    domain=f"{domain}_redo", verdict=verdict)
                tl_text = tl_redo

        # Get next instruction
        instruction = extract(tl_text, "worker_instruction")
        if not instruction and domain != "D5":
            next_d = domains[domains.index(domain) + 1] if domain != "D5" else None
            if next_d:
                instruction = (
                    f"Execute {next_d}.\n\n"
                    f"## FULL QUESTION TEXT:\n{q_text}\n\n"
                    f"Context from previous domains (conspectus excerpt):\n{conspectus[:1500]}"
                )

    # ── PHASE 6: Extract final answer ──
    if not final_answer:
        print("  [TL] Extracting clean answer...")
        tl_text, tl_think = tl.send(
            "Output ONLY the final answer. No explanation. No analysis. No bullet points.\n\n"
            "Format: <final_answer>YOUR ANSWER HERE</final_answer>\n\n"
            "CRITICAL — EXACT FORM PRESERVATION:\n"
            "- Output the EXACT mathematical expression from your derivation\n"
            "- Do NOT simplify, approximate, or drop 'negligible' terms\n"
            "- Do NOT round numbers or convert fractions to decimals\n"
            "- If D4/D5 derived (10^5010000 - 10^10000)/2, output EXACTLY that\n"
            "- NOT 5×10^5009999 (drops a term), NOT ≈0.5×10^5010000 (approximation)\n"
            "- For HLE exact match, every dropped term = wrong answer\n"
            "- Prefer the form closest to how the answer was derived\n"
        )
        fa_block = extract(tl_text, "final_answer")
        if fa_block:
            final_answer = fa_block.strip()
        else:
            # Last resort: take first non-empty line
            for line in tl_text.strip().split('\n'):
                line = line.strip()
                if line and not line.startswith('<') and not line.startswith('#'):
                    final_answer = line
                    break
            if not final_answer:
                final_answer = tl_text.strip()[:200]
        log("team_lead", "orchestrator", "final", tl_text, tl_think, verdict="extracted")

    elapsed = time.time() - start_time

    # ── JUDGE ──
    expected = question["answer"]
    answer_type = question["answer_type"]

    print(f"\n  [Judge] Comparing answers...")
    print(f"    Model:    {final_answer[:100]}")
    print(f"    Expected: {expected[:100]}")

    try:
        is_correct = judge_answer(final_answer, expected, answer_type)
    except Exception as e:
        print(f"    Judge error: {e}")
        is_correct = False

    # ── BUILD RESULT ──
    result = {
        "question_id": q_id,
        "question": q_text[:200] + "..." if len(q_text) > 200 else q_text,
        "raw_subject": question["raw_subject"],
        "answer_type": answer_type,
        "expected": expected,
        "answer_raw": final_answer,
        "judge_correct": is_correct,
        "elapsed_seconds": round(elapsed, 1),
        "team_lead_stats": tl.stats(),
        "worker_stats": worker.stats(),
        "total_calls": tl.call_count + worker.call_count,
        "total_tokens": tl.total_input + tl.total_output + worker.total_input + worker.total_output,
    }

    (run_dir / "result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (run_dir / "conspectus.md").write_text(conspectus, encoding="utf-8")

    # Passport (without answer/rationale to keep clean)
    passport = {
        "version": "1.0",
        "run_id": run_dir.name,
        "question_id": q_id,
        "raw_subject": question["raw_subject"],
        "answer_type": answer_type,
        "result": result,
        "dialogue": dialogue_log,
        "conspectus_final": conspectus,
    }
    (run_dir / "passport.json").write_text(
        json.dumps(passport, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\n  {'─'*50}")
    print(f"  Answer:     {final_answer[:80]}")
    print(f"  Expected:   {expected[:80]}")
    print(f"  Judge:      {'CORRECT' if is_correct else 'INCORRECT'}")
    print(f"  Time:       {elapsed:.1f}s")
    print(f"  Calls:      TL={tl.call_count}, W={worker.call_count}")
    print(f"  Tokens:     {result['total_tokens']:,}")
    print(f"  {'─'*50}")

    return result


# ─── MAIN ─────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python hle_pilot.py <seed_file.json> [max_questions]")
        print("Example: python hle_pilot.py hle_seed_chemistry_10q_42.json 3")
        sys.exit(1)

    seed_file = Path(sys.argv[1])
    max_q = int(sys.argv[2]) if len(sys.argv) > 2 else None

    with open(seed_file, encoding="utf-8") as f:
        seed_set = json.load(f)

    questions = seed_set["questions"]
    if max_q:
        questions = questions[:max_q]

    print("\n" + "="*60)
    print("  REGULUS v3 HLE PILOT — Real HLE Questions")
    print(f"  Profile: {PROFILE_NAME} | Model: {MODEL}")
    print(f"  Base URL: {BASE_URL or 'Anthropic (default)'}")
    print(f"  Thinking: {'ON' if THINKING_ENABLED else 'OFF'}")
    print(f"  Domain: {seed_set['domain']}")
    print(f"  Questions: {len(questions)} (of {seed_set['n_questions']} in seed set)")
    print(f"  Seed file: {seed_file}")
    print("="*60)

    # Check skills
    print("\nChecking skills...")
    required = ["analyze-v2.md", "d6-ask.md", "d6-reflect.md",
                 "d1-recognize.md", "d2-clarify.md", "d3-framework.md",
                 "d4-compare.md", "d5-infer.md"]
    missing = [s for s in required if not (SKILLS_DIR / s).exists()]
    if missing:
        print(f"  WARNING: Missing skills: {missing}")
        print(f"  Copy them to ./{SKILLS_DIR}/ before running.")
        return
    print("  All skills found")

    RUNS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    results = []

    for i, q in enumerate(questions):
        print(f"\n  [{i+1}/{len(questions)}]")

        run_dir = RUNS_DIR / f"{timestamp}_{q['hle_id'][:16]}"
        run_dir.mkdir(parents=True, exist_ok=True)

        try:
            result = run_question(q, run_dir)
            results.append(result)
        except Exception as e:
            print(f"\n  ERROR on {q['hle_id']}: {e}")
            import traceback
            traceback.print_exc()
            results.append({"question_id": q["hle_id"], "error": str(e)})

    # ── SUMMARY ──
    print("\n" + "="*60)
    print("  HLE TEST SUMMARY")
    print("="*60)

    correct = 0
    total = 0
    total_tokens = 0
    total_time = 0

    for r in results:
        if "error" in r:
            print(f"  {r['question_id'][:16]}: ERROR - {r['error'][:60]}")
            continue

        total += 1
        is_correct = r.get("judge_correct", False)
        if is_correct:
            correct += 1
        total_tokens += r.get("total_tokens", 0)
        total_time += r.get("elapsed_seconds", 0)

        status = "CORRECT" if is_correct else "INCORRECT"
        print(f"  {r['question_id'][:16]}: {status}")
        print(f"    Subject:  {r.get('raw_subject', 'N/A')}")
        print(f"    Got:      {r.get('answer_raw', 'N/A')[:60]}")
        print(f"    Expected: {r.get('expected', 'N/A')[:60]}")
        print(f"    Time:     {r.get('elapsed_seconds', 0):.1f}s | Tokens: {r.get('total_tokens', 0):,}")

    pct = 100 * correct / total if total else 0
    print(f"\n  Accuracy: {correct}/{total} ({pct:.0f}%)")
    print(f"  Total tokens: {total_tokens:,}")
    print(f"  Total time: {total_time:.0f}s")
    print(f"  Results saved to: {RUNS_DIR}/")

    # Save aggregate report
    report = {
        "timestamp": timestamp,
        "seed_file": str(seed_file),
        "domain": seed_set["domain"],
        "profile": PROFILE_NAME,
        "model": MODEL,
        "thinking_enabled": THINKING_ENABLED,
        "n_questions": len(questions),
        "accuracy": correct / total if total else 0,
        "correct": correct,
        "total": total,
        "errors": len(results) - total,
        "total_tokens": total_tokens,
        "total_time_seconds": round(total_time, 1),
        "results": results,
    }

    report_file = RUNS_DIR / f"{timestamp}_report.json"
    report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Report: {report_file}")


if __name__ == "__main__":
    main()
