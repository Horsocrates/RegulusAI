#!/usr/bin/env python3
"""
Regulus v5 HLE Pilot — Framework-First Two-Agent Dialogue

Pipeline v5 architecture:
  D1 → D2 (+Assumption Register) → D3 (Enumerate→Analyze→Select)
  → D4 (multi-framework) → D5 (+cross-verify +assumption audit)
  → D6 (extract) → Gap-triggered return logic

Run: python hle_pilot.py hle_seed_math_10q.json
Env vars:
  ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN — API key
  ANTHROPIC_BASE_URL — API base URL (default: Anthropic)
  REGULUS_MODEL — override model (default: see PROFILES below)
  REGULUS_PROFILE — "opus" | "glm5" | "glm5-air" (default: glm5)
"""

import anthropic
import httpx
import json
import os
import re
import subprocess
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
        "tools": False,
    },
    "glm5": {
        "model": "glm-5",
        "judge_model": "glm-5",          # GLM-5 for judge Stage 3 too (cheap)
        "base_url": "https://api.z.ai/api/anthropic",
        "thinking": True,                 # GLM-5 supports thinking via Z.ai
        "thinking_budget": 64000,
        "max_output": 128000,             # must be > thinking_budget
        "tools": True,                    # GLM-5 HLE: 30.5% → 50.4% with tools
    },
    "glm5-air": {
        "model": "glm-4.5-air",
        "judge_model": "glm-4.5-air",
        "base_url": "https://api.z.ai/api/anthropic",
        "thinking": False,
        "thinking_budget": 0,
        "max_output": 32000,
        "tools": False,
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
TOOLS_ENABLED = _P.get("tools", False)
# REGULUS_STOP_AFTER: D1, D2, D3, D4, D5 — stops pipeline after that domain
# Legacy REGULUS_STOP_AFTER_D3=1 still supported
_stop_after_raw = os.environ.get("REGULUS_STOP_AFTER", "").upper().strip()
if not _stop_after_raw and os.environ.get("REGULUS_STOP_AFTER_D3", "").lower() in ("1", "true", "yes"):
    _stop_after_raw = "D3"
STOP_AFTER = _stop_after_raw if _stop_after_raw in ("D1", "D2", "D3", "D4", "D5") else None
STOP_AFTER_D3 = STOP_AFTER == "D3"  # backward compat
SKILLS_DIR = Path("skills")
RUNS_DIR = Path("runs_hle")


# ─── PYTHON EXECUTION TOOL ───────────────────────────────────────────

PYTHON_EXEC_TOOL = {
    "name": "python_exec",
    "description": (
        "Execute Python code and return stdout/stderr. "
        "Use for: numerical computations, symbolic math (sympy), "
        "Monte Carlo simulations, equation solving, verification of analytical results. "
        "Libraries available: math, sympy, numpy, scipy, itertools, fractions, "
        "decimal, statistics, random, collections, functools. "
        "Always print() results to stdout."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute. Must print() results to stdout."
            }
        },
        "required": ["code"]
    }
}

MAX_TOOL_ROUNDS = 5   # max tool calls per single send()
TOOL_TIMEOUT = 120    # seconds per python execution (30s was too short for optimization problems)


def execute_python(code: str, timeout: int = TOOL_TIMEOUT) -> str:
    """Execute Python code in subprocess, return stdout+stderr."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path.home()),  # neutral dir, not project dir
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += ("\n[stderr]\n" + result.stderr) if output else result.stderr
        if not output.strip():
            output = "[no output — did you forget to print()?]"
        # Truncate to prevent token explosion
        if len(output) > 10000:
            output = output[:10000] + f"\n... [truncated, total {len(output)} chars]"
        return output
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT after {timeout}s — simplify your computation]"
    except Exception as e:
        return f"[EXECUTION ERROR: {type(e).__name__}: {e}]"


# ─── CONFIDENCE EXTRACTION HELPER ─────────────────────────────────────

def _extract_confidence(text: str) -> int | None:
    """Extract domain_confidence from TL reflect output.

    Handles multiple formats:
      - "domain_confidence: 85%"   → 85
      - "domain_confidence: 85"    → 85
      - "Confidence: 85%"          → 85
      - "confidence_history: [92, 88, 65]" → 65  (last value)
      - "confidence_history: [92]" → 92

    Filters out:
      - "skill_confidence" (different metric)

    Returns int in [10..100] or None if nothing found.
    """
    cleaned = text.replace('**', '')

    # ── 1. Try standard patterns (most specific first) ──
    for pat in [
        r'domain[_\s]confidence[:\s]+(\d+)\s*%',
        r'domain[_\s]confidence[:\s]+(\d+)',
    ]:
        for m in re.finditer(pat, cleaned, re.IGNORECASE):
            val = int(m.group(1))
            if 10 <= val <= 100:
                return val

    # ── 2. Try confidence_history list format: extract LAST value ──
    hist_match = re.search(
        r'confidence_history[:\s]+\[([0-9,\s]+)\]', cleaned, re.IGNORECASE
    )
    if hist_match:
        nums = [int(x.strip()) for x in hist_match.group(1).split(',') if x.strip().isdigit()]
        if nums:
            val = nums[-1]  # last value = most recent
            if 10 <= val <= 100:
                return val

    # ── 3. Generic "Confidence: XX%" — but skip skill_confidence ──
    for pat in [
        r'[Cc]onfidence[:\s]+(\d+)\s*%',
        r'[Cc]onfidence[:\s]+(\d+)',
    ]:
        for m in re.finditer(pat, cleaned, re.IGNORECASE):
            val = int(m.group(1))
            # Check 20-char context before match for "skill_" or "confidence_history"
            ctx_start = max(0, m.start() - 25)
            ctx = cleaned[ctx_start:m.start()].lower()
            if 'skill_' in ctx or 'history' in ctx:
                continue
            if 10 <= val <= 100:
                return val

    return None


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

        for tool_round in range(MAX_TOOL_ROUNDS + 1):
            # ── API call with retries ──
            last_error = None
            for attempt in range(max_retries):
                try:
                    # Build request kwargs conditionally
                    kwargs = {
                        "model": MODEL,
                        "max_tokens": MAX_OUTPUT,
                        "messages": self.messages,
                    }

                    # Thinking: only if enabled
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

                    # Tools: add if enabled
                    if TOOLS_ENABLED:
                        kwargs["tools"] = [PYTHON_EXEC_TOOL]

                    with self.client.messages.stream(**kwargs) as stream:
                        response = stream.get_final_message()
                    break  # Success
                except (IndexError, anthropic.APIStatusError, anthropic.APIConnectionError,
                        httpx.RemoteProtocolError, httpx.ReadTimeout) as e:
                    last_error = e
                    wait = 2 ** attempt * 5  # 5s, 10s, 20s
                    print(f"    [retry {attempt+1}/{max_retries}] {type(e).__name__}: {e}")
                    print(f"    [waiting {wait}s before retry...]")
                    time.sleep(wait)
            else:
                # All retries exhausted — re-raise
                if tool_round == 0:
                    self.messages.pop()  # Remove the user message we added
                raise last_error

            # ── Track token usage for EVERY API call (including tool rounds) ──
            self.total_input += response.usage.input_tokens
            self.total_output += response.usage.output_tokens
            self.call_count += 1

            cache_read = getattr(response.usage, 'cache_read_input_tokens', 0) or 0
            if cache_read:
                print(f"    [cache hit: {cache_read} tokens]")

            # ── Check for tool_use blocks ──
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            if tool_use_blocks and tool_round < MAX_TOOL_ROUNDS:
                # Store assistant response (contains tool_use + possibly thinking)
                self.messages.append({"role": "assistant", "content": response.content})

                # Execute each tool and build tool_result content
                tool_results = []
                for tb in tool_use_blocks:
                    if tb.name == "python_exec":
                        code = tb.input.get("code", "")
                        print(f"    [{self.name}] tool: python_exec ({len(code)} chars)")
                        output = execute_python(code)
                        lines = output.count('\n') + 1
                        print(f"    [{self.name}] result: {len(output)} chars, {lines} lines")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tb.id,
                            "content": output
                        })
                    else:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tb.id,
                            "content": f"[unknown tool: {tb.name}]",
                            "is_error": True
                        })

                # Append tool results as user message and loop back
                self.messages.append({"role": "user", "content": tool_results})
                continue  # → next tool_round iteration

            # ── No tool_use (or max rounds hit) — extract text and finish ──
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
            return text, thinking

        # Fallback: max tool rounds exhausted
        print(f"    [{self.name}] WARNING: max tool rounds ({MAX_TOOL_ROUNDS}) exhausted")
        return "[max tool rounds exhausted]", ""

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
    # Chemistry normalization (P7 fix)
    # Strip state annotations: (s), (aq), (l), (g)
    s = re.sub(r'\((?:s|aq|l|g)\)', '', s)
    # Normalize reaction arrows → = (all variants)
    s = re.sub(r'\\(?:rightarrow|longrightarrow|to)\b', '=', s)
    s = re.sub(r'[→⟶⟹]', '=', s)
    # Remove LaTeX spacing commands
    s = re.sub(r'\\[;:!,]', '', s)
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

    # Try markdown bold "**Answer:** VALUE" or "**Final Answer:** VALUE"
    md_match = re.search(r'\*\*(?:Final\s+)?Answer[:\s]*\*\*[:\s]*(.+?)(?:\n|$)', model_answer, re.IGNORECASE)
    if md_match:
        ans_line = md_match.group(1).strip()
        ans_line = re.sub(r'\*+$', '', ans_line).strip()
        # P7 fix: If answer contains a LaTeX equation ($$...$$), extract just the equation
        chem_eq = re.search(r'\$\$(.*?)\$\$', ans_line, re.DOTALL)
        if chem_eq:
            ans_line = chem_eq.group(1).strip()
        else:
            # Check for "The reaction/equation is: X" pattern
            reaction_match = re.search(
                r'(?:reaction|equation)\s+is[:\s]+(.+)',
                ans_line, re.IGNORECASE
            )
            if reaction_match:
                ans_line = reaction_match.group(1).strip()
        return ans_line

    # Try "answer: VALUE" at start of a line (YAML-like from structured output)
    yaml_match = re.search(r'^answer:\s*(.+?)$', model_answer, re.MULTILINE | re.IGNORECASE)
    if yaml_match:
        return yaml_match.group(1).strip()

    # If answer is short (< 200 chars), it's probably just the answer
    if len(model_answer.strip()) < 200:
        return model_answer.strip()

    # Otherwise take first non-empty line that looks like an answer
    for line in model_answer.strip().split('\n'):
        stripped = line.strip()
        plain = re.sub(r'^\*+|\*+$', '', stripped).strip()
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
        # Extended boundary: also exclude Unicode math chars (ℵ, ₀, ^, etc.)
        # so "0" doesn't match inside "ℵ0" or "2^ℵ₀"
        pattern = r'(?<![a-zA-Z0-9ℵ₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹\^])' + re.escape(norm_expected) + r'(?![a-zA-Z0-9ℵ₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹\^])'
        if re.search(pattern, norm_model):
            print(f"    [Judge] Stage 1: Expected found as distinct token in model answer → correct")
            return True

    # ── STAGE 2: Numeric equivalence ──
    try:
        def parse_number(s):
            s = s.strip()
            if '/' in s:
                parts = s.split('/')
                if len(parts) == 2:
                    return float(parts[0]) / float(parts[1])
            return float(s)

        num_model = parse_number(norm_model)
        num_expected = parse_number(norm_expected)
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

    # ── STAGE 2.5a: Simple expected vs complex model mismatch ──
    # If expected answer is simple (short number/symbol) and model answer is
    # long/complex and doesn't contain expected as its core, reject immediately.
    # Catches: expected="0" vs model="c (continuum cardinality, 2^ℵ₀)"
    if len(norm_expected) <= 5:
        # Expected is very simple (e.g., "0", "1", "c", "42", "3/10")
        # Extract the core of model answer (first token before any parentheses/explanation)
        core_model = re.split(r'[\s(,;:]', norm_model)[0].strip()
        if core_model != norm_expected:
            # Check if expected appears as a standalone token in model core
            # "0" should not match "2^ℵ₀" or "10" or "continuum"
            expected_pattern = rf'\b{re.escape(norm_expected)}\b'
            if not re.search(expected_pattern, core_model):
                print(f"    [Judge] Stage 2.5a: Simple expected '{norm_expected}' ≠ core model '{core_model}' → incorrect")
                return False

    # ── STAGE 2.5: Short answer quick-reject ──
    if len(norm_model) < 30 and len(norm_expected) < 30:
        # Check if they might be mathematical expressions first
        math_chars = set("+-*/^χKCgcSκ²³_(){}.")
        if any(c in math_chars for c in norm_model) and any(c in math_chars for c in norm_expected):
            # Might be math expressions — skip to Stage 2.5b
            print(f"    [Judge] Stage 2.5: Short but math-like — trying numeric substitution")
        else:
            # Both are short, normalized, and don't match — they're different
            print(f"    [Judge] Stage 2.5: Short answers differ after normalization → incorrect")
            return False

    # ── STAGE 2.5b: Numeric substitution for mathematical formulas ──
    # If answers contain variables (χ, K, C, g, etc.), substitute concrete values
    # and check if expressions evaluate to the same number.
    # This catches equivalences via adjunction, Noether, etc.
    math_indicators = ["χ", "K_S", "K²", "C²", "C·K", "\\chi", "\\kappa",
                       "c_2", "c₂", "12χ", "12\\chi", "genus", " g "]
    if any(ind in model_answer or ind in expected_answer
           for ind in math_indicators):
        print(f"    [Judge] Stage 2.5b: Detected math formula — numeric substitution check")
        try:
            import sympy as sp
        except ImportError:
            sp = None

        if sp is not None:
            # Try multiple test cases with different parameter values
            test_cases = [
                {"chi": 2, "K2": 0, "C2": 0, "g": 1, "CK": 0},   # K3 elliptic
                {"chi": 1, "K2": 8, "C2": 12, "g": 2, "CK": -10}, # P1xP1, C=(2,3)
                {"chi": 3, "K2": 1, "C2": 5, "g": 4, "CK": 1},    # generic surface
                {"chi": 1, "K2": 0, "C2": 4, "g": 3, "CK": 0},    # another test
            ]

            def parse_formula(text):
                """Attempt to parse a mathematical formula into a sympy expression."""
                s = text.strip()
                # Normalize common patterns
                replacements = [
                    ("12χ", "12*chi"), ("12\\chi", "12*chi"),
                    ("χ", "chi"), ("\\chi", "chi"),
                    ("K_S²", "K2"), ("K_S^2", "K2"), ("K²", "K2"),
                    ("C²", "C2"), ("C^2", "C2"),
                    ("C·K_S", "CK"), ("C·K", "CK"), ("C*K", "CK"),
                    ("c₂(S)", "c2S"), ("c_2(S)", "c2S"), ("c₂", "c2S"),
                    ("−", "-"), ("–", "-"), ("—", "-"),
                    (" ", ""),
                ]
                for old, new in replacements:
                    s = s.replace(old, new)
                # Try sympy parsing
                try:
                    chi, K2, C2, g, CK, c2S = sp.symbols("chi K2 C2 g CK c2S")
                    expr = sp.sympify(s, locals={
                        "chi": chi, "K2": K2, "C2": C2, "g": g,
                        "CK": CK, "c2S": c2S
                    })
                    return expr
                except:
                    return None

            expr_model = parse_formula(model_answer)
            expr_expected = parse_formula(expected_answer)

            if expr_model is not None and expr_expected is not None:
                chi, K2, C2, g, CK, c2S = sp.symbols("chi K2 C2 g CK c2S")
                all_match = True
                any_computed = False

                for tc in test_cases:
                    try:
                        subs = {
                            chi: tc["chi"], K2: tc["K2"], C2: tc["C2"],
                            g: tc["g"], CK: tc["CK"],
                            c2S: 12 * tc["chi"] - tc["K2"],  # Noether formula
                        }
                        val_model = float(expr_model.subs(subs))
                        val_expected = float(expr_expected.subs(subs))
                        any_computed = True
                        print(f"      Test {tc}: model={val_model}, expected={val_expected}")
                        if abs(val_model - val_expected) > 0.01:
                            all_match = False
                    except:
                        continue

                if any_computed and all_match:
                    print(f"    [Judge] Stage 2.5b: Formulas agree on all test cases → correct")
                    return True
                elif any_computed and not all_match:
                    print(f"    [Judge] Stage 2.5b: Formulas DISAGREE on test cases → proceeding to Stage 3")
                    # Don't return False yet — let LLM judge decide (maybe we parsed wrong)
            else:
                print(f"    [Judge] Stage 2.5b: Could not parse formulas — proceeding to Stage 3")

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
   - MATHEMATICAL EQUIVALENCE: formulas that simplify to the same expression
     via standard identities (adjunction, Noether, Euler characteristic, etc.)
     Example: "12χ − K² + 2g − 2" = "12χ + C² − K² − 4 + 4g" if 2g−2 = C² + C·K
4. NOT EQUIVALENT (return "incorrect"):
   - Different values: "5.57" ≠ "5.58", "42" ≠ "43"
   - Different entities: "D₂" ≠ "S₄", "glucose" ≠ "fructose"
   - Different lists: "2, 1, 1" ≠ "2, 1, 0" (even one element differs = different)
   - Partial match: "A and B" ≠ "A" (incomplete answer)
   - Superset/subset: model says more than expected ≠ correct
5. For mathematical formulas: check if they give the same numerical result
   when you substitute specific values for all variables.
6. When in doubt → "incorrect"

Respond with EXACTLY one word: "correct" or "incorrect"."""

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=JUDGE_MODEL,
                max_tokens=10,
                messages=[{"role": "user", "content": judge_prompt}]
            )
            judge_text = response.content[0].text.strip().lower()
            if "incorrect" in judge_text:
                print(f"    [Judge] Stage 3: LLM says incorrect")
                return False
            if "correct" in judge_text:
                print(f"    [Judge] Stage 3: LLM says correct")
                return True
            print(f"    [Judge] Stage 3: Unexpected LLM response: '{judge_text}' → incorrect")
            return False
        except Exception as e:
            if attempt < 2:
                print(f"    [judge retry {attempt+1}] {e}")
                time.sleep(5)
            else:
                raise


# ─── DIALOGUE RUNNER (v5 — Framework-First) ─────────────────────────

def run_question(question: dict, run_dir: Path) -> dict:
    """Run two-agent dialogue on a single HLE question.

    Pipeline v5 flow:
      D1 → D2 (+Assumption Register) → D3 (Enumerate→Analyze→Select)
      → D4 (multi-framework, ×N) → D5 (+cross-verify +assumption audit)
      → Extract → Gap-triggered return logic

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
            "type": msg_type, "content": content[:12000],
            **meta
        }
        if thinking:
            entry["thinking_excerpt"] = thinking[:4000]
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

    # ── PHASE 1-5: Framework-First Pipeline (v5) ──
    #
    # Flow: D1 → D2 → D3(enumerate→analyze→select) → D4(×N) → D5 → Extract
    # Gap > 20pp → diagnostic questions → iterate
    # Gap > 35pp → return to D3, try next framework

    final_answer = None
    c_computation = None  # Worker's confidence in computation
    c_approach = None     # TL's confidence in approach (scorecard)

    # ── Helper: run Worker + TL reflect cycle ──
    DOMAIN_CONF_GATE = 60  # Minimum domain_confidence to proceed (Sufficient Reason)
    MIN_IMPROVEMENT = 10   # Minimum confidence improvement per iteration (pp)
    SOFT_CAP = 6           # Soft cap on iterations — warn but don't stop

    def _run_domain_once(domain_name, worker_instruction, tl_reflect_extra="", label=None):
        """Run one Worker execution + TL reflection.
        Returns (w_text, tl_text, verdict, domain_conf)."""
        nonlocal conspectus
        lbl = label or domain_name

        print(f"  [Worker] Executing {lbl}...")
        w_text, w_think = worker.send(worker_instruction)
        log("worker", "team_lead", "domain_output", w_text, w_think, domain=lbl)

        # ── P14: Empty output recovery — ask Worker to summarize tool results ──
        if not w_text.strip():
            print(f"  [P14] Worker text empty after tool calls — requesting summary")
            summary_prompt = (
                "Your previous response used Python tools but produced no text output. "
                "Please provide your COMPLETE analysis as text now:\n"
                "1. State what you computed and the key results\n"
                "2. List all findings, intermediate values, and conclusions\n"
                "3. Answer the domain question based on your computations\n\n"
                "Do NOT re-run Python — just summarize the results you already obtained."
            )
            w_text, w_think = worker.send(summary_prompt)
            log("worker", "team_lead", "domain_output", w_text, w_think,
                domain=f"{lbl}_summary")

        # ── Empty output gate: auto-iterate without TL (only if still empty) ──
        if not w_text.strip():
            print(f"  [GATE] Worker returned EMPTY output for {lbl} — auto-iterate")
            log("team_lead", "team_lead", "reflect", f"[AUTO-GATE] Empty worker output for {lbl}",
                "", domain=lbl, verdict="iterate")
            return w_text, f"[Empty output — auto-iterate]", "iterate", 0

        depth = "full"
        print(f"  [TL] Reflecting on {lbl} ({depth})...")
        tl_text, tl_think = tl.send(
            f"MODE: reflect\nDEPTH: {depth}\nDOMAIN: {lbl}\n\n"
            f"Worker {lbl} output:\n{w_text}\n\n"
            f"Evaluate this output. Update your conspectus. Decide verdict. "
            f"If pass, produce instruction for next domain.\n\n"
            f"MANDATORY: State domain_confidence: XX% for this domain's output quality. "
            f"This is your confidence that {lbl} is COMPLETE and CORRECT enough to build on. "
            f"If domain_confidence < {DOMAIN_CONF_GATE}%, verdict MUST be iterate.\n\n"
            f"Output <conspectus>, <verdict>, and <worker_instruction> blocks."
            f"{tl_reflect_extra}"
        )

        verdict = extract(tl_text, "verdict").strip().lower()
        if not verdict:
            for v in ["threshold_reached", "pass", "iterate", "paradigm_shift"]:
                if v in tl_text.lower():
                    verdict = v
                    break
            if not verdict:
                verdict = "pass"

        # ── Extract domain_confidence ──
        domain_conf = _extract_confidence(tl_text)

        if domain_conf is not None:
            print(f"  [GATE] {lbl} domain_confidence={domain_conf}%")
            if domain_conf < DOMAIN_CONF_GATE and verdict == "pass":
                print(f"  [GATE] domain_confidence={domain_conf}% < {DOMAIN_CONF_GATE}% — "
                      f"overriding verdict pass→iterate")
                verdict = "iterate"
        else:
            domain_conf = 50  # Default if TL didn't report
            print(f"  [GATE] {lbl} domain_confidence not reported — defaulting to {domain_conf}%")

        log("team_lead", "team_lead", "reflect", tl_text, tl_think,
            domain=lbl, verdict=verdict)

        new_conspectus = extract(tl_text, "conspectus")
        if new_conspectus:
            conspectus = new_conspectus
            (run_dir / "conspectus.md").write_text(conspectus, encoding="utf-8")

        print(f"  [TL] Verdict: {verdict} (domain_conf={domain_conf}%)")
        return w_text, tl_text, verdict, domain_conf

    def run_domain(domain_name, worker_instruction, tl_reflect_extra="", label=None):
        """Backward-compatible wrapper. Returns (w_text, tl_text, verdict)."""
        w, t, v, _dc = _run_domain_once(domain_name, worker_instruction, tl_reflect_extra, label)
        return w, t, v

    def iterate_domain(domain_name, initial_instruction, tl_reflect_extra="",
                       empty_retry_msg=None):
        """Adaptive iteration loop for a domain.

        Rules:
        - Iterate while domain_confidence < GATE (60%)
        - Each iteration must improve confidence by ≥ MIN_IMPROVEMENT (10pp)
        - If stagnation (< +10pp): one feedback round with specific diagnostic
        - If still stagnant after feedback: paradigm_shift or accept+report
        - Soft cap at SOFT_CAP (6) iterations: warn but continue if still improving

        Returns: (w_text, tl_text, verdict, domain_conf, conf_history)
        """
        conf_history = []
        feedback_given = False
        paradigm_attempted = False

        # First run
        w_text, tl_text, verdict, domain_conf = _run_domain_once(
            domain_name, initial_instruction, tl_reflect_extra)
        conf_history.append(domain_conf)

        iteration = 0
        while verdict == "iterate" or domain_conf < DOMAIN_CONF_GATE:
            iteration += 1

            # ── Check improvement ──
            if len(conf_history) >= 2:
                improvement = conf_history[-1] - conf_history[-2]
                print(f"  [ITER] {domain_name} iter={iteration} conf={domain_conf}% "
                      f"Δ={improvement:+d}pp history={conf_history}")

                if improvement < MIN_IMPROVEMENT:
                    # Stagnation detected
                    if not feedback_given:
                        # ── Feedback round: specific diagnostic ──
                        print(f"  [ITER] Stagnation (Δ={improvement:+d}pp < +{MIN_IMPROVEMENT}pp) "
                              f"— sending targeted feedback")
                        feedback_given = True
                        feedback_inst = (
                            f"## TARGETED FEEDBACK — STAGNATION DETECTED\n\n"
                            f"domain_confidence has been: {conf_history}\n"
                            f"Improvement was only {improvement:+d}pp (need ≥+{MIN_IMPROVEMENT}pp).\n\n"
                            f"Your current approach may be hitting a ceiling. Specifically:\n"
                            f"1. What is the SINGLE BIGGEST uncertainty remaining in this domain?\n"
                            f"2. What NEW information or technique would resolve it?\n"
                            f"3. Are there any assumptions you haven't questioned?\n"
                            f"4. Can you verify your result using a completely different method?\n\n"
                            f"Focus on the ONE thing that would most increase confidence.\n\n"
                            f"## FULL QUESTION:\n{q_text}\n\nContext:\n{conspectus[:2000]}"
                        )
                        w_text, tl_text, verdict, domain_conf = _run_domain_once(
                            domain_name, feedback_inst, tl_reflect_extra,
                            label=f"{domain_name}_feedback{iteration}")
                        conf_history.append(domain_conf)
                        continue

                    elif not paradigm_attempted:
                        # ── Paradigm shift: use METHOD_MENU fallback if available ──
                        print(f"  [ITER] Still stagnant after feedback — attempting PARADIGM SHIFT")
                        paradigm_attempted = True

                        # Extract METHOD_MENU from conspectus to guide the shift
                        method_menu_match = re.search(
                            r'METHOD_MENU:?\s*\n((?:\s+M\d:.+\n)+)',
                            conspectus, re.MULTILINE
                        )
                        if method_menu_match:
                            menu_text = method_menu_match.group(1).strip()
                            # Parse method entries
                            methods = re.findall(r'M(\d+):\s*(.+?)(?:\n|$)', menu_text)
                            fallback_text = ""
                            if len(methods) > 1:
                                fallback_text = (
                                    f"\n\nMETHOD_MENU from D3 (use NEXT method in fallback order):\n"
                                    f"{menu_text}\n\n"
                                    f"Your current method (M1: {methods[0][1].strip()}) has stagnated.\n"
                                    f"Switch to the NEXT method: M2: {methods[1][1].strip()}\n"
                                    f"DO NOT reuse intermediate results from the previous method.\n"
                                )
                            print(f"  [ITER] METHOD_MENU found with {len(methods)} methods — "
                                  f"shifting to M{methods[1][0] if len(methods) > 1 else '?'}")
                        else:
                            fallback_text = ""
                            print(f"  [ITER] No METHOD_MENU found — generic paradigm shift")

                        paradigm_inst = (
                            f"## PARADIGM SHIFT — ABANDON CURRENT APPROACH\n\n"
                            f"Confidence history: {conf_history} — no progress despite feedback.\n\n"
                            f"COMPLETELY ABANDON your current method. Requirements:\n"
                            f"1. State what assumption or technique you are DROPPING\n"
                            f"2. Choose a FUNDAMENTALLY DIFFERENT approach "
                            f"(not a variation of the same method)\n"
                            f"3. Solve from scratch using only the new approach\n"
                            f"4. Compare: does the new approach give a different answer?\n\n"
                            f"This is not 'try harder' — this is 'try DIFFERENTLY'.\n"
                            f"{fallback_text}\n"
                            f"## FULL QUESTION:\n{q_text}\n\nContext:\n{conspectus[:2000]}"
                        )
                        w_text, tl_text, verdict, domain_conf = _run_domain_once(
                            domain_name, paradigm_inst, tl_reflect_extra,
                            label=f"{domain_name}_paradigm{iteration}")
                        conf_history.append(domain_conf)
                        continue

                    else:
                        # ── Exhausted all strategies: only accept if above gate ──
                        if domain_conf >= DOMAIN_CONF_GATE:
                            print(f"  [ITER] Stagnant after paradigm shift — accepting at {domain_conf}% (≥ gate)")
                        else:
                            print(f"  [ITER] Stagnant after paradigm shift — accepting with LOW_CONFIDENCE "
                                  f"({domain_conf}% < {DOMAIN_CONF_GATE}% gate)")
                            verdict = "low_confidence"
                        print(f"  [ITER] Final conf_history: {conf_history}")
                        break
            else:
                print(f"  [ITER] {domain_name} iter={iteration} conf={domain_conf}% "
                      f"history={conf_history}")

            # ── Soft cap warning ──
            if iteration >= SOFT_CAP:
                if len(conf_history) >= 2 and conf_history[-1] - conf_history[-2] >= MIN_IMPROVEMENT:
                    print(f"  [ITER] Soft cap ({SOFT_CAP}) reached but still improving — continuing")
                else:
                    print(f"  [ITER] Soft cap ({SOFT_CAP}) reached and not improving — stopping")
                    break

            # ── Confidence is acceptable ──
            if domain_conf >= DOMAIN_CONF_GATE and verdict != "iterate":
                break

            # ── Build iterate instruction ──
            if not w_text.strip():
                # Empty output — give specific retry instruction
                iter_inst = empty_retry_msg or (
                    f"{domain_name} RETRY: Previous output was empty.\n"
                    f"SIMPLIFY your approach. Print intermediate results.\n\n"
                    f"## FULL QUESTION:\n{q_text}\n\nContext:\n{conspectus[:2000]}")
            else:
                iter_inst = extract(tl_text, "worker_instruction")
                if not iter_inst:
                    print(f"  [ITER] No worker_instruction from TL — stopping iteration")
                    break
                iter_inst += f"\n\n## FULL QUESTION:\n{q_text}\n\nContext:\n{conspectus[:2000]}"

            w_text, tl_text, verdict, domain_conf = _run_domain_once(
                domain_name, iter_inst, tl_reflect_extra,
                label=f"{domain_name}_iter{iteration}")
            conf_history.append(domain_conf)

        print(f"  [ITER] {domain_name} DONE: conf={domain_conf}% "
              f"history={conf_history} iterations={iteration}")
        return w_text, tl_text, verdict, domain_conf, conf_history

    # ── Helper: get next instruction from TL output ──
    def get_instruction(tl_text, fallback_domain=None):
        inst = extract(tl_text, "worker_instruction")
        if not inst and fallback_domain:
            inst = (
                f"Execute {fallback_domain}.\n\n"
                f"## FULL QUESTION TEXT:\n{q_text}\n\n"
                f"Context from previous domains (conspectus excerpt):\n{conspectus[:1500]}"
            )
        return inst

    # ═══════════════════════════════════════════
    # D1 — Recognition
    # ═══════════════════════════════════════════
    w_text, tl_text, verdict, d1_conf, d1_history = iterate_domain(
        "D1", instruction,
        empty_retry_msg=f"D1 RETRY: Previous output was empty. Re-execute D1 Recognition.\n\n## FULL QUESTION:\n{q_text}"
    )

    # ── STOP_AFTER D1 (debug mode) ──
    if STOP_AFTER == "D1":
        print("\n  ╔══════════════════════════════════════════╗")
        print("  ║  STOP_AFTER=D1 — skipping D2-D5          ║")
        print("  ╚══════════════════════════════════════════╝")
        elapsed = time.time() - start_time
        result = {
            "question_id": q_id, "question": q_text,
            "raw_subject": question.get("subject", ""),
            "answer_type": question.get("answer_type", ""),
            "expected": question.get("answer", ""),
            "mode": f"debug_stop_{STOP_AFTER}",
            "d1_confidence": d1_conf,
            "d1_conf_history": d1_history,
            "conspectus_final": conspectus[:6000],
            "d1_worker_output": w_text[:6000],
            "d1_tl_reflect": tl_text[:6000],
            "elapsed_seconds": round(elapsed, 1),
            "total_calls": (tl.call_count if hasattr(tl, 'call_count') else 0) +
                           (worker.call_count if hasattr(worker, 'call_count') else 0),
        }
        (run_dir / "result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n  D1-only result saved: {run_dir / 'result.json'}")
        return result

    instruction = get_instruction(tl_text, "D2")

    # ═══════════════════════════════════════════
    # D2 — Clarification + Assumption Register
    # ═══════════════════════════════════════════
    d2_extra = """

## MANDATORY: ASSUMPTION REGISTER

List ALL assumptions entering your reasoning. For each, classify:

| ID | Assumption | Source | Origin | Justified? |
|----|-----------|--------|--------|:----------:|
| A1 | ... | PROVEN / IMPORTED / ASSUMED | where from | yes/no |

Source types:
- **PROVEN**: Derived within this problem (stated in question, or derived in D1)
- **IMPORTED**: Taken from another theorem/problem. You MUST justify why it applies HERE.
  If you cannot justify → mark as UNVERIFIED_IMPORT
- **ASSUMED**: Taken as given without proof (honest uncertainty)

For IMPORTED: state "impact_if_wrong: [what changes if this is false]"

CRITICAL: Properties from similar-but-different problems are IMPORTED, not PROVEN.
Example: "120° angles are optimal" from Steiner trees does NOT prove they are
optimal for area maximization. Different objective = different problem = must re-prove.

## MANDATORY: HYPOTHESIS COMPLETENESS CHECK

Before closing D2, verify that your hypothesis set covers ALL structurally distinct cases:

- **Chemistry**: If the problem involves two species (e.g., metal A and metal M), you MUST consider
  that they could be the SAME element in different oxidation states (comproportionation/disproportionation).
  Add this as an explicit hypothesis if not already covered.
- **Mathematics**: Consider degenerate/edge cases (empty set, zero, infinity, equality).
- **Any domain**: For each assumption "X ≠ Y" or "X is of type T", add a hypothesis where that assumption fails.

List your hypotheses and state what structural category each covers.
"""
    instruction = (instruction or "") + d2_extra

    d2_tl_extra = """

CHECK D2 OUTPUT — THREE MANDATORY CHECKS:

**CHECK 1: ASSUMPTION REGISTER**
Does Worker output include an ASSUMPTION REGISTER?
If NO → iterate, ask Worker to list all assumptions with PROVEN/IMPORTED/ASSUMED.
If YES → verify: any UNVERIFIED_IMPORT? Note in conspectus for D5 scoring.

**CHECK 2: PROOF CHAIN AUDIT**
For every derivation/proof in D2 output:
a) Is it structured as a proof chain (numbered steps with explicit assumptions)?
   If NO → iterate with: "Restructure your proof of [claim] as a numbered proof chain. Each step must list its assumptions and their status (PROVEN/IMPORTED/ASSUMED)."
b) For each step: is the assumption PROVEN from the question text, or ASSUMED/IMPORTED?
   If ANY step is ASSUMED/IMPORTED → conclusion_strength is CONDITIONAL, not PROVEN.
   Record in conspectus: "PROOF: [claim] — conclusion_strength: CONDITIONAL (step N assumes [what])"
c) Does any step contain a HIDDEN PREMISE — something the proof needs but doesn't state?
   Common hidden premises to check:
   - "Reaction type is X" (but could it be a different type? comproportionation? disproportionation?)
   - "The set/space has property P" (but is P proven for THIS specific object? connectedness? compactness?)
   - "Stoichiometry is 1:1" (but could it be 1:2 or 2:3?)
   - "This set is connected/closed/compact" (proven HERE or just assumed?)
   - "The objects are distinct" (but could A and M be the same entity?)
   - "Symmetry holds" (but is the distribution actually symmetric?)

   If hidden premise found → add to assumption register as UNVERIFIED_IMPORT, set proof conclusion to CONDITIONAL.

**CHECK 3: D1 FLAG RESOLUTION AUDIT**
For each D1 flag that D2 claims to have resolved:
a) Was it resolved by a PROVEN conclusion (all steps from question text) or a CONDITIONAL one?
b) If CONDITIONAL → flag MUST remain OPEN, NOT resolved. Record: "D1 FLAG [id]: OPEN (closed by CONDITIONAL proof — re-opened)"
c) OPEN flags MUST be forwarded to D3-D5 as active constraints
d) Record in conspectus: "D1 FLAGS: [id]=resolved(PROVEN) | [id]=OPEN(conditional) | ..."

**CHECK 4: HYPOTHESIS SPACE COMPLETENESS**
Does the Worker's hypothesis set cover ALL structurally distinct possibilities?

Common blind spots to check:
- **Chemistry:** Did Worker consider that the two species could be the SAME element in different oxidation states? (e.g., comproportionation: Fe⁰ + Fe³⁺ → Fe²⁺). If the problem says "metal A" and "unknown chloride of metal M", Worker often assumes A ≠ M. But A = M with different oxidation states is a valid and common reaction type.
- **Mathematics:** Did Worker consider degenerate cases? (empty set, zero, infinity, trivial solution)
- **Physics:** Did Worker consider extreme regimes? (relativistic, quantum, classical limits)
- **Logic:** Did Worker consider the negation of the main assumption?

If the hypothesis space is incomplete (missing a structurally distinct category of solutions):
→ verdict = iterate
→ State: "Your hypotheses only cover [X]. You must also consider [Y] as a separate hypothesis. Add it to open_hypotheses."

**CHECK 5: CLAIM SOURCE AUDIT (Sufficient Reason for PROVEN)**
For EVERY claim, rule, or definition in Worker's D2 output, verify its status matches its SOURCE:

| Source type | Max allowed status | Example |
|---|---|---|
| Quoted from question text | PROVEN | "Metal A is divalent" — stated in problem |
| Derived step-by-step from PROVEN premises only | PROVEN | "Therefore n=2" — if ALL steps trace to question text |
| Domain knowledge / textbook fact | IMPORTED | "120° is optimal" — from Steiner theorem |
| Worker-invented rule or convention | ASSUMED | "Purpose should match what control tests" |
| Analogy or pattern | HEURISTIC | "Large enough to ignore" |

CRITICAL TEST — scan for these red flags:
- Worker writes "RULE:" or "RULE[N]:" WITHOUT citing a specific theorem/textbook/standard → status MUST be ASSUMED
- Worker writes "The [more precise/accurate] description is..." → this is SEMANTIC JUDGMENT → ASSUMED
- Worker writes "Convention:" or "Standard practice:" without citation → IMPORTED at best
- Worker defines a NEW term or category not in the question → ASSUMED
- Worker writes "clearly" / "obviously" on a non-trivial claim → ASSUMED

If ANY claim has status PROVEN but its source is domain_knowledge or worker_invented:
→ DOWNGRADE to IMPORTED or ASSUMED
→ Add mandatory if_wrong: "If this claim is false, the answer changes to [X]"
→ verdict = iterate
→ State: "Claim '[claim]' was marked PROVEN but source is [type]. Downgraded to [new_status]. Worker must add if_wrong field."

**VERDICT RULE:**
If any D1 flag was closed by a CONDITIONAL proof → verdict = iterate.
If hypothesis space is incomplete → verdict = iterate.
If any claim has inflated status (PROVEN when should be IMPORTED/ASSUMED) → verdict = iterate.
State in worker_instruction: "FLAG [id] was closed by a CONDITIONAL proof (step N assumes [what]). Re-open the flag. Consider BOTH branches: what if the proof holds, and what if it fails. Output open_hypotheses for both cases."
"""
    w_text, tl_text, verdict, d2_conf, d2_history = iterate_domain(
        "D2", instruction, tl_reflect_extra=d2_tl_extra,
        empty_retry_msg=f"D2 RETRY: Previous output was empty. Re-execute D2 Clarification.\n\n## FULL QUESTION:\n{q_text}\n\n{d2_extra}"
    )

    # ── STOP_AFTER D2 (debug mode) ──
    if STOP_AFTER == "D2":
        print("\n  ╔══════════════════════════════════════════╗")
        print("  ║  STOP_AFTER=D2 — skipping D3-D5          ║")
        print("  ╚══════════════════════════════════════════╝")
        elapsed = time.time() - start_time
        result = {
            "question_id": q_id, "question": q_text,
            "raw_subject": question.get("subject", ""),
            "answer_type": question.get("answer_type", ""),
            "expected": question.get("answer", ""),
            "mode": f"debug_stop_{STOP_AFTER}",
            "d2_confidence": d2_conf, "d2_conf_history": d2_history,
            "conspectus_final": conspectus[:6000],
            "elapsed_seconds": round(elapsed, 1),
            "total_calls": (tl.call_count if hasattr(tl, 'call_count') else 0) +
                           (worker.call_count if hasattr(worker, 'call_count') else 0),
        }
        (run_dir / "result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n  D2-only result saved: {run_dir / 'result.json'}")
        return result

    instruction = get_instruction(tl_text, "D3")

    # ═══════════════════════════════════════════
    # D3 — Framework Selection (MULTI-STEP with adaptive iteration)
    # ═══════════════════════════════════════════

    def run_d3_cycle(base_instruction, iteration_num=0):
        """Run one full D3 cycle: enumerate → analyze → theory → TL select.
        Returns (tl_d3, verdict, d3_conf, w_d3_enum, w_d3_rank, w_d3_theory)."""
        nonlocal conspectus
        suffix = f"_iter{iteration_num}" if iteration_num > 0 else ""

        # D3.1 — Enumerate
        d3_enumerate = (base_instruction or "") + """

## D3 STEP 1: METHOD MENU + FRAMEWORK ENUMERATION

### Part A: METHOD MENU (do this FIRST)
BEFORE listing individual frameworks, classify the available SOLUTION METHODS.
These are broad categories — paradigm shift will move between methods, not just between frameworks.

Output a METHOD_MENU:
```
METHOD_MENU:
  M1: [Method name] — [1-sentence description] — [why first choice]
  M2: [Method name] — [1-sentence description] — [fallback if M1 stagnates]
  M3: [Method name] — [1-sentence description] — [fallback if M2 stagnates]

  Selected: M[X]
  Fallback order on paradigm_shift: M[Y] → M[Z]
```

Common method categories (include ALL that could apply):
- **Analytical/Symbolic**: exact derivation, closed-form solution, algebraic manipulation
- **Numerical/Computational**: optimization, simulation, numerical search, iterative methods
- **Structural/Combinatorial**: enumeration, graph theory, counting arguments, pigeonhole
- **Reduction**: reduce to a known solved problem, isomorphism, bijection
- **Probabilistic**: Monte Carlo, random sampling, expected value arguments
- **Experimental/Empirical**: direct measurement, hypothesis testing (for science questions)

### Part B: FRAMEWORK ENUMERATION (within the selected method)
Do NOT select a framework yet. List ALL plausible approaches WITHIN the selected method:

For each framework:
- Name and brief description (1-2 sentences)
- Why it MIGHT apply (what features of the problem match)
- Why it MIGHT NOT apply (risks, assumptions needed)
- Key assumptions required (mark PROVEN/IMPORTED/ASSUMED)

Be EXHAUSTIVE. Include:
- Standard textbook approaches for this problem type
- Computational/numerical approaches
- Elementary approaches (small cases, direct counting, brute force)
- Approaches from adjacent mathematical fields

Do NOT rank yet. Do NOT filter. Cast a wide net.
"""
        print(f"  ── D3.1{suffix}: Framework Enumeration ──")
        w_d3_enum, w_think = worker.send(d3_enumerate)
        log("worker", "team_lead", "domain_output", w_d3_enum, w_think,
            domain=f"D3.1_enumerate{suffix}")

        # D3.2 — Analyze & Distribute
        d3_analyze = """
## D3 STEP 2: ANALYZE & DISTRIBUTE WEIGHTS

For each framework from Step 1:
1. Score fit to problem (0-100)
2. Count assumptions: how many PROVEN vs IMPORTED vs ASSUMED?
3. Estimate tractability (can we compute with this? easy/medium/hard)
4. Assign probability weight (= "likelihood this is the RIGHT approach")

RULES:
- Weights MUST sum to 100%
- No single framework > 70% (unless all others explicitly refuted with proof)
- 'Other/Unknown' category ALWAYS gets ≥ 5%
- Frameworks with 2+ UNVERIFIED_IMPORTS get max 30% weight

Output a ranked table:
| Rank | Framework | Fit | Assumptions (P/I/A) | Tractability | Weight |
|------|-----------|:---:|:-------------------:|:------------:|:------:|
"""
        print(f"  ── D3.2{suffix}: Framework Analysis ──")
        w_d3_rank, w_think = worker.send(d3_analyze)
        log("worker", "team_lead", "domain_output", w_d3_rank, w_think,
            domain=f"D3.2_analyze{suffix}")

        # D3.3 — Theory Derivation (new step: derive theoretical backbone for D4)
        d3_theory = """
## D3 STEP 3: THEORY CHAIN — DERIVE THE THEORETICAL PATH TO THE ANSWER

Break this into discrete steps. For EACH step, report it IMMEDIATELY before moving to the next.
Do NOT try to write the entire chain at once — go step by step.

FORMAT for each step (keep each step SHORT — 3-5 lines max):

### STEP N: [title]
- **Statement**: What is established?
- **Basis**: Law/principle/theorem (1 line)
- **Assumes**: [PROVEN/IMPORTED/ASSUMED] — list each assumption
- **Status**: PROVEN | BRANCHED | CONDITIONAL

RULES:
1. Number every step sequentially (STEP 1, STEP 2, ...)
2. If D2 has OPEN hypotheses → the chain MUST BRANCH. Show BOTH paths.
3. Mark BRANCHED steps clearly: "BRANCH A: [hypothesis]" / "BRANCH B: [hypothesis]"
4. After ALL steps, write a CONCLUSION block:

### CONCLUSION
- **theoretical_prediction**: What does the theory predict?
- **d4_instructions**: EXPLICIT computation instructions for D4 (what to calculate, input values, expected output format)
- **verification_criterion**: How D4 confirms/refutes the theory

Keep the TOTAL output CONCISE. Aim for 5-10 steps. If a step needs computation, state WHAT to compute — don't compute it here. D4 will execute.
"""
        print(f"  ── D3.3{suffix}: Theory Derivation ──")
        w_d3_theory, w_think = worker.send(d3_theory)
        log("worker", "team_lead", "domain_output", w_d3_theory, w_think,
            domain=f"D3.3_theory{suffix}")

        # D3.4 — TL reviews everything: enumeration, ranking, AND theory
        d3_tl_select = f"""MODE: reflect
DEPTH: full
DOMAIN: D3{suffix}

Worker enumerated, ranked, and derived theory for frameworks:

=== ENUMERATION ===
{w_d3_enum[:1500]}

=== RANKING ===
{w_d3_rank[:1500]}

=== THEORY CHAIN ===
{w_d3_theory[:4000]}

YOUR TASK:
1. Review the framework list. Are important approaches MISSING?
   - Standard textbook approach for this problem type?
   - Elementary/computational approach?
   - Approach from adjacent mathematical field?

2. Record FRAMEWORK DISTRIBUTION in conspectus (weights sum to 100%).

3. **THEORY AUDIT** — For each step in the theory chain:
   a) Is the theoretical_basis correct? (Does the cited law/theorem actually apply here?)
   b) Are all assumptions classified correctly? (Is something marked PROVEN that should be ASSUMED?)
   c) Are there HIDDEN STEPS — jumps where the theory skips over a non-obvious claim?
   d) If D2 had OPEN flags or CONDITIONAL proofs — does the theory BRANCH for both possibilities?
   e) Are d4_instructions complete? Does D4 know exactly WHAT to compute?

   If theory has problems → verdict = iterate, ask Worker to fix specific steps.

3. SELECT which frameworks to compute in D4:
   | Top framework weight | Compute |
   |---------------------|---------|
   | ≥ 70% | Top-1 only |
   | 50-69% | Top-2 |
   | < 50% | Top-3 |
   | All < 30% | RED FLAG — return to D2 |

4. If you identify a MISSING framework → add it, re-distribute weights.

MANDATORY: State domain_confidence: XX% for D3 output quality.
This is your confidence that the framework selection is CORRECT and COMPLETE.

Output <conspectus>, <verdict>, and <worker_instruction>.
In worker_instruction, specify which framework(s) to use in D4.
"""
        print(f"  ── D3.4{suffix}: TL Framework + Theory Selection ──")
        tl_d3, tl_think = tl.send(d3_tl_select)

        verdict = extract(tl_d3, "verdict").strip().lower() or "pass"

        # Extract domain_confidence using shared helper
        d3_conf = _extract_confidence(tl_d3)
        if d3_conf is None:
            d3_conf = 50
        print(f"  [GATE] D3{suffix} domain_confidence={d3_conf}%")

        if d3_conf < DOMAIN_CONF_GATE and verdict == "pass":
            print(f"  [GATE] D3 domain_confidence={d3_conf}% < {DOMAIN_CONF_GATE}% — overriding to iterate")
            verdict = "iterate"

        log("team_lead", "team_lead", "reflect", tl_d3, tl_think,
            domain=f"D3_select{suffix}", verdict=verdict)

        new_conspectus = extract(tl_d3, "conspectus")
        if new_conspectus:
            conspectus = new_conspectus
            (run_dir / "conspectus.md").write_text(conspectus, encoding="utf-8")

        print(f"  [TL] D3{suffix} verdict: {verdict}")
        return tl_d3, verdict, d3_conf, w_d3_enum, w_d3_rank, w_d3_theory

    # ── D3 adaptive iteration loop ──
    d3_conf_history = []
    d3_feedback_given = False
    d3_paradigm_attempted = False

    tl_d3, verdict, d3_conf, w_d3_enum, w_d3_rank, w_d3_theory = run_d3_cycle(instruction)
    d3_conf_history.append(d3_conf)

    d3_iteration = 0
    while verdict == "iterate" or d3_conf < DOMAIN_CONF_GATE:
        d3_iteration += 1

        # Check improvement
        if len(d3_conf_history) >= 2:
            improvement = d3_conf_history[-1] - d3_conf_history[-2]
            print(f"  [ITER] D3 iter={d3_iteration} conf={d3_conf}% Δ={improvement:+d}pp "
                  f"history={d3_conf_history}")

            if improvement < MIN_IMPROVEMENT:
                if not d3_feedback_given:
                    print(f"  [ITER] D3 stagnation — targeted feedback round")
                    d3_feedback_given = True
                    feedback_inst = (
                        f"D3 confidence stagnant at {d3_conf_history}.\n"
                        f"RE-EXAMINE: Is there a framework you haven't considered?\n"
                        f"Are you biased toward a familiar approach?\n"
                        f"What would someone from a DIFFERENT field try?\n\n"
                        f"## FULL QUESTION:\n{q_text}\n\nContext:\n{conspectus[:2000]}")
                    tl_d3, verdict, d3_conf, _, _, _ = run_d3_cycle(feedback_inst, d3_iteration)
                    d3_conf_history.append(d3_conf)
                    continue
                elif not d3_paradigm_attempted:
                    print(f"  [ITER] D3 still stagnant — PARADIGM SHIFT")
                    d3_paradigm_attempted = True
                    paradigm_inst = (
                        f"## D3 PARADIGM SHIFT\n\n"
                        f"Confidence history: {d3_conf_history} — no progress.\n"
                        f"COMPLETELY ABANDON current framework candidates.\n"
                        f"Think from FIRST PRINCIPLES: what is the problem REALLY asking?\n"
                        f"Consider approaches from: combinatorics, algebra, analysis, "
                        f"geometry, probability, information theory, physics analogies.\n\n"
                        f"## FULL QUESTION:\n{q_text}\n\nContext:\n{conspectus[:2000]}")
                    tl_d3, verdict, d3_conf, _, _, _ = run_d3_cycle(paradigm_inst, d3_iteration)
                    d3_conf_history.append(d3_conf)
                    continue
                else:
                    if d3_conf >= DOMAIN_CONF_GATE:
                        print(f"  [ITER] D3 stagnant after paradigm shift — accepting at {d3_conf}% (≥ gate)")
                    else:
                        print(f"  [ITER] D3 stagnant after paradigm shift — accepting with LOW_CONFIDENCE "
                              f"({d3_conf}% < {DOMAIN_CONF_GATE}% gate)")
                        verdict = "low_confidence"
                    break
        else:
            print(f"  [ITER] D3 iter={d3_iteration} conf={d3_conf}% history={d3_conf_history}")

        if d3_iteration >= SOFT_CAP:
            print(f"  [ITER] D3 soft cap ({SOFT_CAP}) — stopping")
            break

        if d3_conf >= DOMAIN_CONF_GATE and verdict != "iterate":
            break

        # Regular iterate — use TL's instruction for re-enumeration
        d3_redo_inst = extract(tl_d3, "worker_instruction")
        if not d3_redo_inst:
            print(f"  [ITER] D3 no worker_instruction — stopping")
            break

        tl_d3, verdict, d3_conf, w_d3_enum, w_d3_rank, w_d3_theory = run_d3_cycle(d3_redo_inst, d3_iteration)
        d3_conf_history.append(d3_conf)

    print(f"  [ITER] D3 DONE: conf={d3_conf}% history={d3_conf_history} "
          f"iterations={d3_iteration}")

    # ═══════════════════════════════════════════
    # STOP AFTER D3 (theory validation mode)
    # ═══════════════════════════════════════════
    if STOP_AFTER in ("D3",):
        print("\n  ╔══════════════════════════════════════════╗")
        print("  ║  STOP_AFTER_D3 mode — skipping D4/D5     ║")
        print("  ╚══════════════════════════════════════════╝")

        # Assemble theory-only result
        elapsed = time.time() - start_time
        theory_result = {
            "question_id": q_id,
            "question": q_text,
            "raw_subject": question.get("subject", ""),
            "answer_type": question.get("answer_type", ""),
            "expected": question.get("answer", ""),
            "mode": "theory_only_d3",
            "theory_chain": w_d3_theory[:4000] if w_d3_theory else "[empty]",
            "conspectus_final": conspectus[:4000],
            "d3_confidence": d3_conf,
            "d3_conf_history": d3_conf_history,
            "elapsed_seconds": round(elapsed, 1),
            "team_lead_stats": {
                "calls": tl.call_count if hasattr(tl, 'call_count') else None,
                "input_tokens": tl.total_input if hasattr(tl, 'total_input') else None,
                "output_tokens": tl.total_output if hasattr(tl, 'total_output') else None,
            },
            "worker_stats": {
                "calls": worker.call_count if hasattr(worker, 'call_count') else None,
                "input_tokens": worker.total_input if hasattr(worker, 'total_input') else None,
                "output_tokens": worker.total_output if hasattr(worker, 'total_output') else None,
            },
        }
        tl_calls = tl.call_count if hasattr(tl, 'call_count') else 0
        w_calls = worker.call_count if hasattr(worker, 'call_count') else 0
        tl_tok = (tl.total_input or 0) + (tl.total_output or 0) if hasattr(tl, 'total_input') else 0
        w_tok = (worker.total_input or 0) + (worker.total_output or 0) if hasattr(worker, 'total_input') else 0
        theory_result["total_calls"] = tl_calls + w_calls
        theory_result["total_tokens"] = tl_tok + w_tok

        # Save result
        (run_dir / "result.json").write_text(
            json.dumps(theory_result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n  Theory-only result saved: {run_dir / 'result.json'}")
        return theory_result

    # ═══════════════════════════════════════════
    # D4 — Computation (may be multi-framework)
    # ═══════════════════════════════════════════
    d4_instruction = get_instruction(tl_d3, "D4")
    d4_instruction = (d4_instruction or "") + f"""

## FULL QUESTION TEXT:
{q_text}

For each framework assigned by the Team Lead, compute the answer:
- Show ALL computation steps
- Verify edge cases
- Report your answer AND confidence for EACH framework separately
- If computing multiple frameworks: compare results at the end

Context (conspectus excerpt):
{conspectus[:2000]}
"""
    d4_empty_retry = (
        f"## D4 RETRY — PREVIOUS OUTPUT WAS EMPTY\n\n"
        f"Your previous computation returned no output (likely timeout or error).\n"
        f"SIMPLIFY your approach:\n"
        f"- Break computation into small steps, print intermediate results\n"
        f"- If enumerating: reduce search space, use pruning, check fewer cases\n"
        f"- If code times out: use analytical bounds to eliminate cases first\n"
        f"- Prefer analytical solutions over brute-force enumeration\n"
        f"- If using python_exec: keep each code block under 10 seconds\n\n"
        f"## FULL QUESTION TEXT:\n{q_text}\n\nContext:\n{conspectus[:2000]}"
    )

    d4_tl_extra = """

**NUMERICAL MISMATCH GATE (Patch 11):**
After evaluating D4 computation, check for numerical discrepancies with problem constraints:

1. Does the computed answer satisfy ALL constraints from the question EXACTLY?
   - Mass balance: closes to 0.000% error?
   - Integer constraints: result is exact integer?
   - Probability: exactly in [0,1]?
   - Stoichiometry: coefficients are exact integers?

2. If ANY discrepancy exists, compute: EXACT_ERROR = |computed - constraint|

3. Classification:
   - EXACT-ANSWER tasks (stoichiometry, combinatorics, integer sequences, formal proofs):
     ANY nonzero error = NUMERICAL MISMATCH (RED FLAG)
   - APPROXIMATE tasks (physics, engineering): error must be within stated precision

4. If RED FLAG detected:
   - State: "NUMERICAL MISMATCH: [value] ≠ [expected], error = [X]%"
   - DO NOT rationalize ("acceptable rounding", "close enough", "negligible")
   - A nonzero error in an exact task means THE MODEL IS WRONG, not imprecise arithmetic
   - Record in conspectus: "D4 MISMATCH DETECTED: [details]"
   - Recommend: investigate whether D2 assumptions need revision

CRITICAL: 3.68% error in exact stoichiometry = WRONG MODEL. 0.002% error in integer count = WRONG MODEL.
Only 0.000% is acceptable for exact-answer tasks.

**CLAIM STATUS INHERITANCE CHECK (Sufficient Reason):**
D4 builds on claims from D2/D3 with statuses (PROVEN/IMPORTED/ASSUMED/CONDITIONAL).
Before accepting ANY claim used in D4's computation:

1. Check: does the claim trace back to the question text (PROVEN), or was it a D2 convention/rule?
   - If D4 uses a claim marked PROVEN but it was actually a D2-invented rule (no question-text citation),
     that claim is ASSUMED at best — D4's computation inherits the weakness.
   - Record: "D4 FRAGILE DEPENDENCY: computation uses [claim] which is [actual_status], not PROVEN"

2. If D4's answer would CHANGE when an IMPORTED/ASSUMED claim is negated:
   - Record in conspectus: "FRAGILE: Answer depends on [claim]. If false → answer becomes [X]"
   - domain_confidence penalty: -20pp (because answer is not robust)

3. For MC questions: if D4 eliminates an answer option based on an IMPORTED/ASSUMED claim,
   that elimination is CONDITIONAL — the eliminated option must remain as a candidate.

**CONSTRUCTIVE SANITY CHECK (Anti-Tautological Verification — P7):**
After D4 computation, verify the result is PHYSICALLY/GEOMETRICALLY/LOGICALLY PLAUSIBLE:

1. SCALE CHECK: Are computed quantities the right order of magnitude?
   - A "small sphere inside object X" must have radius << size of X
   - A probability must be in [0,1]
   - A count must be a non-negative integer
   - If computed value is ABSURDLY large/small vs problem scale → RED FLAG
   - Example: r_small = 21 inside cone of height 3 → ABSURD → formula is WRONG

2. CONSTRUCTIVE EXAMPLE CHECK (mandatory when answer involves derived formulas):
   - Pick ONE concrete set of input values (from the problem or simple integers)
   - Compute the answer using your formula
   - Then INDEPENDENTLY verify from FIRST PRINCIPLES (NOT from the same formula chain):
     * Go back to ORIGINAL definitions (geometric distances, physical constraints)
     * Check: does the computed object actually satisfy ALL stated conditions?
     * Example: formula gives r₂=21 → can a sphere of radius 21 fit inside a cone of height 3?
       Obviously NO → formula is WRONG, regardless of algebra
   - If constructive check FAILS → formula is WRONG → domain_confidence ≤ 25%
   - Record: "CONSTRUCTIVE CHECK: [PASS/FAIL] — [details]"

3. TAUTOLOGICAL VERIFICATION TRAP (detect and reject):
   - If D4's "verification" consists of:
     a) Computing value X from formula F
     b) Checking that X satisfies relation R that is ALGEBRAICALLY EQUIVALENT to F
   - Then verification proves NOTHING — it is circular
   - REAL verification must use an INDEPENDENT constraint NOT derivable from F
   - TAUTOLOGICAL example: derive r₂ from formula, check r₂/d = cot(α/2) — this IS the formula
   - REAL example: derive r₂ from formula, verify sphere of radius r₂ fits inside cone at position d

4. IMPOSSIBILITY CLAIMS require EXTRA scrutiny:
   - If D4 concludes "impossible / no solution / does not exist":
     * EXTRAORDINARY claim needs extraordinary evidence
     * Could the formula itself be WRONG? What if derivation had an error?
     * Try to CONSTRUCT a counterexample with concrete numbers
     * If you can build one → "impossibility" is WRONG → iterate with revised formula
     * Require 2+ INDEPENDENT derivation paths both showing impossible
   - Record: "IMPOSSIBILITY AUDIT: [confirmed by N methods / REFUTED by example]"
"""

    w_text, tl_text, verdict, d4_conf, d4_history = iterate_domain(
        "D4", d4_instruction, tl_reflect_extra=d4_tl_extra, empty_retry_msg=d4_empty_retry)

    instruction = get_instruction(tl_text, "D5")

    # ═══════════════════════════════════════════
    # D5 — Inference + Cross-Verification
    # ═══════════════════════════════════════════
    d5_extra = """

## MANDATORY: CROSS-VERIFICATION (do this AFTER your main conclusion)

1. **SANITY CHECKS** (mandatory):
   - Range: Is answer in valid domain? (probability ∈ [0,1], count ∈ ℤ≥0, etc.)
   - Magnitude: Is the order of magnitude reasonable?
   - Symmetry: If answer has suspicious symmetry (≈1/2, ≈0, ≈1), explain WHY
   - **EXTREME VALUE FLAG**: If P=0.000 or P=1.000 for a probability question,
     this requires RIGOROUS PROOF of impossibility/certainty. "It seems like
     it always happens" is NOT a proof. Ask: "Is there ANY configuration where
     the outcome differs?" If you cannot PROVE none exists → the answer is NOT 0 or 1.
   - **Probability < 0.001 or > 0.999**: Almost certainly wrong for HLE problems.
     These problems are designed to have non-trivial answers. Flag immediately.
   - Small case: Verify formula on a SMALL CONCRETE EXAMPLE (n=2 or n=3)

2. **ALTERNATIVE METHOD** (attempt if feasible):
   - Solve using a fundamentally DIFFERENT approach (not redo same calculation)
   - CRITICAL: alternative must NOT share assumptions with primary method
   - If two independent methods disagree → report BOTH, cap confidence at 50%

3. **ASSUMPTION AUDIT + ERR INTEGRATION**:
   Review your assumption register from D2 AND add any NEW assumptions introduced
   in D3-D5. Every claim in your derivation has an ERR status:

   | ERR Status | Meaning | Sufficient Reason? |
   |-----------|---------|:------------------:|
   | PROVEN | Derived step-by-step within THIS problem | ✅ YES |
   | IMPORTED | Taken from external theorem/result | ❌ NO — must PROVE it applies HERE |
   | ASSUMED | Taken without proof | ❌ NO — must prove or flag |
   | APPROXIMATION | Uses ≈ instead of = | ❌ NO — must give error bound |
   | HEURISTIC | "large enough", "intuitively", "it seems" | ❌ NEVER sufficient |

   PROCEDURE — for EACH key claim in your final answer chain:
   1. State the claim explicitly
   2. Assign ERR status (PROVEN / IMPORTED / ASSUMED / APPROXIMATION / HEURISTIC)
   3. If NOT PROVEN:
      - For IMPORTED: cite the exact theorem, verify ALL its conditions hold for
        THIS specific problem. "Standard result in field X" is NOT sufficient —
        state the theorem, list its hypotheses, check each one.
      - For ASSUMED: attempt to prove it. If you cannot → flag it.
      - For APPROXIMATION: compute error bound |exact − approx| < ε
      - For HEURISTIC: replace with proof or computation. Never acceptable.

   CRITICAL — COMMON ERR TRAPS:
   - "By [named property]" (e.g., "by symmetry", "by duality", "by invariance"):
     This is IMPORTED until you PROVE the named property holds for THIS problem.
     A property holding in similar problems does NOT make it PROVEN here.
   - "Result is independent of parameter X": IMPORTED. Prove the invariance.
   - "Distribution has property P": IMPORTED. Prove P from the distribution's definition.
   - Citing a theorem without verifying hypotheses: IMPORTED with UNVERIFIED conditions.

   OUTPUT: Sufficient Reason Table (mandatory):
   | # | Claim | ERR Status | Theorem/Source | Conditions verified? | Sufficient? |
   |---|-------|-----------|---------------|:-------------------:|:-----------:|
   | 1 | ... | PROVEN/IMPORTED/... | ... | yes/no/N/A | ✅/❌ |

   If ANY claim in the answer chain has Sufficient=❌ → max confidence 60%
   If 2+ claims have Sufficient=❌ → max confidence 40%

4. **PROOF STEP AUDIT** (for proofs/derivations):
   - For EACH step "X implies Y": is there ANY case where X true but Y false?
   - For "clearly X" or "obviously X": PROVE X, don't just assert it
   - For "for all X, P(X)": did you check EVERY X, or just typical ones?
   - For limit arguments: limits describe behavior at ∞, not at finite points.
     "f(n) → L" does NOT prove f(n₀) = L. Compute f(n₀) directly or bound the error.
   - For "this is a standard result": state the result precisely, verify hypotheses

5. **CONFIDENCE RULES**:
   - ALL claims PROVEN with sufficient reason → uncapped
   - Any claim IMPORTED without full hypothesis verification → max 60%
   - Any claim uses APPROXIMATION without error bound → max 50%
   - Any HEURISTIC claim ("large enough", "intuitively") → max 40%
   - Sanity check fails → max 60%
   - Only one method, no cross-check → max 75%
   - Two INDEPENDENT methods agree (no shared IMPORTED assumptions) → uncapped
   - Two DEPENDENT methods agree (shared IMPORTED) → max 70%

6. **REPORT**: `worker_confidence: N%` and the Sufficient Reason Table above
"""
    instruction = (instruction or "") + d5_extra

    # TL D5 scorecard
    d5_tl_extra = """

CRITICAL — TWO-LEVEL CONFIDENCE SCORECARD:

## Level 1: C_computation (from Worker)
Extract Worker's reported confidence. This measures computation correctness.

## Level 2: C_approach (YOUR scorecard — measures framework correctness)
Fill EVERY checkpoint:

| Checkpoint | Weight | Score | Note |
|------------|:------:|:-----:|------|
| A. Recognition completeness | 0.10 | ?/1.0 | |
| B. Definition depth | 0.08 | ?/1.0 | |
| C. Framework selection (multiple considered? top weight?) | 0.12 | ?/1.0 | |
| D. Computation completeness (all criteria, edge cases) | 0.12 | ?/1.0 | |
| E. Cross-verification (sanity + alt method + INDEPENDENCE) | 0.18 | ?/1.0 | |
| F. Proof integrity (no hasty gen, boundary conditions) | 0.12 | ?/1.0 | |
| G. Answer format & magnitude | 0.13 | ?/1.0 | |
| H. Assumption independence (unverified imports?) | 0.15 | ?/1.0 | |

CHECKPOINT E — before scoring, verify METHOD INDEPENDENCE:
- Independent methods agree → E up to 1.0
- Methods share assumptions → E max 0.5
- Only one method → E max 0.3

CHECKPOINT F — PROOF INTEGRITY + SUFFICIENT REASON AUDIT:
You MUST verify the Worker's Sufficient Reason Table. For EACH claim:
1. Does Worker provide a Sufficient Reason Table? If NO → F ≤ 0.3
2. For each claim marked PROVEN: verify the proof is actually complete
   - "Step says X implies Y. Is there a case where X is true but Y is false?"
   - "Step says 'clearly X' — is it actually clear? Prove it, don't assert it."
3. For each claim marked IMPORTED: did Worker verify ALL hypotheses of the theorem?
   - Did Worker STATE the theorem precisely (not just name it)?
   - Did Worker LIST the hypotheses?
   - Did Worker CHECK each hypothesis against THIS specific problem?
   - If ANY hypothesis unchecked → reclassify as UNVERIFIED IMPORT → F ≤ 0.4
4. For claims marked APPROXIMATION: is error bound given? If NO → F ≤ 0.3
5. Any HEURISTIC claims remaining? → F ≤ 0.2

RED FLAGS (score F low):
- "clearly"/"obviously"/"it follows" without proof → F ≤ 0.5
- "By [property]" without proving property holds HERE → F ≤ 0.4
- Theorem cited without hypothesis verification → F ≤ 0.4
- "Standard result" without precise statement → F ≤ 0.3
- "For all X, P(X)" proven only for generic X → F ≤ 0.3
- Limit/asymptotic used as exact value at finite point → F ≤ 0.3

CHECKPOINT F — ADDITIONAL: CLAIM GENEALOGY AUDIT (Sufficient Reason)
For the final answer's inference chain, trace EACH claim back to its ORIGIN DOMAIN:
- If origin = question text → OK (PROVEN)
- If origin = D2 derivation with ALL PROVEN steps → OK (PROVEN)
- If origin = D2 rule/convention WITHOUT question-text citation → NOT PROVEN (max IMPORTED)
- If origin = Worker-invented rule ("RULE:", "Convention:", "Standard practice:") → ASSUMED

Specific patterns to search for in the inference chain:
- "RULE[N]:" or "RULE:" without citing a specific theorem/textbook → ASSUMED (not PROVEN)
- "The [more precise/accurate] description is..." → SEMANTIC JUDGMENT → ASSUMED
- "Off-target effects is vague" vs "altered surface expression is precise" → JUDGMENT, not FACT
- "Purpose should be described by what the control tests" → INVENTED CONVENTION → ASSUMED
- Any claim where Worker CHOSE between two valid interpretations → JUDGMENT → ASSUMED

If ANY link in the final answer chain has INFLATED status (marked PROVEN but actually IMPORTED/ASSUMED):
→ F ≤ 0.3 (the proof is built on sand)
→ Hard cap: SUFFICIENT REASON VIOLATION → max 50%
→ verdict = iterate

CHECKPOINT H — ASSUMPTION INDEPENDENCE (ERR-based):
Review Worker's Sufficient Reason Table:
- Count claims with ERR status ≠ PROVEN
- If answer chain depends on 1 IMPORTED claim → H ≤ 0.6
- If answer chain depends on 2+ IMPORTED claims → H ≤ 0.4
- If IMPORTED claim is "distribution has property P" → verify P independently
- If primary and alternative methods share the SAME imported assumption → H ≤ 0.3

HARD CAPS:
- No cross-verification → max 50%
- Only 1 framework → max 65%
- Sanity check failed → max 45%
- Two methods disagree → max 40%
- iff with only one direction → max 35%
- Magnitude wrong → max 25%
- Methods share assumptions → max 55%
- Proof contains "clearly"/"obviously" on a NON-TRIVIAL claim → max 65%
- **SUFFICIENT REASON VIOLATION** (any claim in answer chain not PROVEN) → max 50%
- Answer chain has IMPORTED claim with unchecked hypotheses → max 45%
- Answer depends on APPROXIMATION without error bound → max 45%
- Answer depends on HEURISTIC ("large enough", "intuitively") → max 35%

C_approach = min(all_caps, round(weighted_sum × 100))

## GAP ANALYSIS
Gap = |C_computation - C_approach|
Final confidence = min(C_computation, C_approach)

Write in conspectus:
  ## CONFIDENCE TRACKER
  C_computation (Worker): X%
  C_approach (TL scorecard): Y%
  Gap: Zpp
  Final confidence: min(X,Y) = W%

## WEAKEST CHECKPOINTS (identify top 3 lowest scores):
  1. Checkpoint [X] = [score] → target domain: [D?]
  2. Checkpoint [Y] = [score] → target domain: [D?]
  3. Checkpoint [Z] = [score] → target domain: [D?]

Checkpoint-to-domain routing:
  A (Recognition) → D1 | B (Definition) → D2 | C (Framework) → D3
  D (Computation) → D4 | E (Cross-verify) → D5 | F (Proof) → D5
  G (Format) → D5 | H (Assumptions) → D2

## DIAGNOSTIC QUESTIONS (if C_approach < 65% or gap ≥ 20pp):
For each weak checkpoint, write ONE specific question that,
if answered satisfactorily, would raise that checkpoint by 0.2-0.3:
  - "To raise C from 0.4 to 0.7: [specific question about framework choice]"
  - "To raise E from 0.3 to 0.6: [specific question about cross-verification]"

## ITERATION DECISION (MANDATORY — follow exactly):
- C_approach ≥ 65% AND gap < 20pp → PROCEED (verdict: pass/threshold_reached)
- C_approach < 65% → verdict MUST be "iterate" (NEVER threshold_reached when C < 65%)
- Gap ≥ 20pp → verdict MUST be "iterate" (diagnostic questions needed)
- Gap ≥ 35pp → verdict MUST be "iterate" + route to D3 (framework switch)

CRITICAL: "threshold_reached" is ONLY valid when C_approach ≥ 65% AND gap < 20pp.
If you feel the answer is correct but C_approach < 65%, that means your PROOF
is insufficient, not that the answer is wrong. Iterate to PROVE it.

ADDITIONAL AUTO-FLAGS (trigger diagnostic regardless of gap):
- Answer is P=0.000 or P=1.000 → "Prove determinism rigorously"
- Answer is P < 0.001 or P > 0.999 → "Extreme probability — verify"
- Answer magnitude differs > 3 orders from 'typical' → "Magnitude check"
"""

    w_text, tl_text, verdict, d5_conf, d5_history = iterate_domain(
        "D5", instruction, tl_reflect_extra=d5_tl_extra)

    # ── SUSPICIOUSLY CLEAN DETECTOR (MC questions only) ──
    # Q2 failure: 92→95→97→98→100 with zero iterations on a 5-option MC question.
    # For MC questions where top-2 answers differ by one phrase, this is a red flag.
    # Force a devil's advocate D4 pass to stress-test the answer.
    is_mc = question.get("answer_type") == "multipleChoice"
    all_histories = [d1_history, d2_history, d4_history, d5_history]
    all_passed_first_try = all(
        len(h) <= 1 for h in all_histories if h
    )
    min_domain_conf = min(
        d1_conf or 0, d2_conf or 0, d4_conf or 0, d5_conf or 0
    )

    if is_mc and all_passed_first_try and min_domain_conf >= 82:
        print(f"  [CLEAN-FLAG] MC question: ALL domains passed first try, min_conf={min_domain_conf}%")
        print(f"  [CLEAN-FLAG] Forcing devil's advocate D4 re-evaluation")

        devil_instruction = f"""
## DEVIL'S ADVOCATE PASS — MANDATORY FOR MC QUESTIONS WITH ZERO ITERATIONS

Your previous pipeline produced answer with very high confidence on first try.
For MC questions this is a RED FLAG — you may have confirmation-biased all verification.

YOU MUST perform the following adversarial analysis:

### Step 1: Identify top-2 candidates
- Your chosen answer: [extract from conspectus]
- Closest runner-up: [the answer choice that ALMOST passed your criteria]

### Step 2: Build STRONGEST argument for the runner-up
- What reasoning chain leads to the runner-up being correct?
- What assumption in YOUR chain, if wrong, makes the runner-up correct?
- Is there a domain-knowledge convention that favors the runner-up's phrasing?

### Step 3: Claim source audit
For each claim that distinguishes your answer from the runner-up:
- Is it PROVEN (from question text) or ASSUMED (your judgment/convention)?
- If the distinguishing claim is ASSUMED → you cannot be >70% confident

### Step 4: Verdict
- If runner-up has fewer ASSUMED claims → SWITCH your answer
- If equal → lower confidence to max 70%, flag as "MC_ADVERSARIAL_UNCERTAIN"
- If your answer clearly has stronger PROVEN chain → confirm, but confidence max 90%

## FULL QUESTION TEXT:
{q_text}

## Current conspectus:
{conspectus[:3000]}
"""

        w_devil, tl_devil, v_devil, d4_devil_conf = _run_domain_once(
            "D4", devil_instruction, tl_reflect_extra=d4_tl_extra,
            label="D4_devil_advocate")

        # If devil's advocate lowered confidence or changed answer, update D4
        if d4_devil_conf is not None and d4_devil_conf < d4_conf:
            print(f"  [CLEAN-FLAG] Devil's advocate lowered D4 conf: {d4_conf}% → {d4_devil_conf}%")
            d4_conf = d4_devil_conf
            d4_history.append(d4_devil_conf)

            # Re-run D5 with updated context
            print(f"  [CLEAN-FLAG] Re-running D5 after devil's advocate")
            d5_instruction = get_instruction(tl_devil, "D5") or instruction
            w_text, tl_text, verdict, d5_conf, d5_history = iterate_domain(
                "D5", d5_instruction, tl_reflect_extra=d5_tl_extra)
        else:
            print(f"  [CLEAN-FLAG] Devil's advocate confirmed answer (conf={d4_devil_conf}%)")

    # ── Extract confidence values ──
    # Search BOTH conspectus AND tl_text (D5 reflect output) because
    # TL may write confidence in its reflect output before conspectus is updated.
    def extract_confidence(text, label):
        # Strip Markdown bold markers — TL often writes "**C_computation (Worker):** 100%"
        # which puts ** between : and digits, breaking the regex.
        cleaned = text.replace('**', '')
        patterns = [
            rf'{label}[^:\d]*[:\s]+(\d+)\s*%',    # "C_computation (Worker): 95%"
            rf'{label}[^:\d]*[:\s]+(\d+)(?!\d)',    # "C_computation: 95"
            rf'{label}[^:\d]*=\s*(\d+)\s*%',       # "C_approach = 93%"
            rf'{label}[^:\d]*=\s*(\d+)(?!\d)',      # "C_approach = 93"
        ]
        for p in patterns:
            m = re.search(p, cleaned, re.IGNORECASE)
            if m:
                val = int(m.group(1))
                if 0 <= val <= 100:
                    return val
        return None

    # BUG FIX: Try tl_text FIRST (latest values), fall back to conspectus (may be stale).
    # Previous code used combined_text with re.search which returned FIRST match (from
    # conspectus), missing updated values from TL's D5 reflect.
    c_computation = (extract_confidence(tl_text, "C_computation")
                     or extract_confidence(tl_text, "worker.confidence")
                     or extract_confidence(tl_text, "Worker confidence")
                     or extract_confidence(conspectus, "C_computation")
                     or extract_confidence(conspectus, "worker.confidence")
                     or extract_confidence(conspectus, "Worker confidence"))
    c_approach = (extract_confidence(tl_text, "C_approach")
                  or extract_confidence(tl_text, "TL confidence")
                  or extract_confidence(tl_text, "tl_confidence")
                  or extract_confidence(conspectus, "C_approach")
                  or extract_confidence(conspectus, "TL confidence")
                  or extract_confidence(conspectus, "tl_confidence"))

    # Fallback chain: if confidence labels not found, try domain_confidence parser,
    # then flat defaults. Prevents Q3-style bug where bold formatting broke label parsing
    # but domain_confidence was available.
    if c_computation is None:
        # Try extracting from Worker's text using domain_confidence parser
        c_computation = _extract_confidence(w_text)
        if c_computation:
            print(f"  [Confidence] c_computation fallback from worker domain_confidence: {c_computation}%")
        else:
            c_computation = 20 if not w_text.strip() else 50
            print(f"  [Confidence] c_computation not found — defaulting to {c_computation}%")
    if c_approach is None:
        # Try extracting from TL's D5 reflect domain_confidence
        c_approach = _extract_confidence(tl_text)
        if c_approach:
            print(f"  [Confidence] c_approach fallback from TL domain_confidence: {c_approach}%")
        else:
            c_approach = 20 if not tl_text.strip() else 40
            print(f"  [Confidence] c_approach not found — defaulting to {c_approach}%")

    # ── CONFIDENCE-DRIVEN ITERATION ──
    #
    # Two triggers:
    # 1. C_approach < CONFIDENCE_THRESHOLD → absolute threshold
    # 2. Gap ≥ 20pp → relative threshold (computation ok, approach suspect)
    # 3. Extreme probability auto-flag
    #
    # Routing: lowest checkpoint → target domain for diagnostic questions
    #
    CONFIDENCE_THRESHOLD = 65  # Below this, always iterate
    MAX_CONFIDENCE_ITERATIONS = 2  # Prevent infinite loops

    # Extreme probability check
    extreme_prob_flag = False
    if final_answer:
        try:
            ans_val = float(final_answer.strip())
            if ans_val == 0.0 or ans_val == 1.0:
                extreme_prob_flag = True
                print(f"  [AUTO-FLAG] P={ans_val} — extreme probability, forcing diagnostic")
            elif ans_val < 0.001 or ans_val > 0.999:
                extreme_prob_flag = True
                print(f"  [AUTO-FLAG] P={ans_val} — near-extreme, forcing diagnostic")
        except (ValueError, TypeError):
            pass

    # ── Checkpoint extraction from conspectus ──
    def extract_checkpoints(text):
        """Extract checkpoint scores from TL's scorecard in conspectus."""
        checkpoints = {}
        # Map checkpoint letters to domains for routing
        checkpoint_domains = {
            "A": "D1",  # Recognition
            "B": "D2",  # Definition
            "C": "D3",  # Framework
            "D": "D4",  # Computation
            "E": "D5",  # Cross-verification
            "F": "D5",  # Proof integrity (re-derive)
            "G": "D5",  # Format (re-state)
            "H": "D2",  # Assumptions (re-audit)
        }
        checkpoint_questions = {
            "A": "Are all elements from the question identified? Is anything missing from D1?",
            "B": "Are all key terms defined at sufficient depth? Any hidden ambiguity in definitions?",
            "C": ("Was the RIGHT mathematical framework chosen? What alternative frameworks exist? "
                  "Enumerate at least 2 alternatives and explain why they were rejected."),
            "D": ("Is the computation complete? Check edge cases. Verify on small concrete example. "
                  "Show the computation for n=1 and n=2 explicitly."),
            "E": ("Solve using a FUNDAMENTALLY DIFFERENT method (not same framework). "
                  "The alternative must NOT share assumptions with the primary method. "
                  "Compare results. If they differ, explain why."),
            "F": ("Audit each step of the proof: for every claim 'X is P', ask 'when is X NOT P?' "
                  "Is that case excluded? Check boundary conditions. "
                  "If you cited a theorem, verify it applies to THIS exact situation."),
            "G": ("Verify the answer is in the correct format. Check magnitude against intuition. "
                  "For a probability, is it between 0 and 1? For a count, is it a positive integer?"),
            "H": ("List every assumption. For each IMPORTED assumption, PROVE it applies here. "
                  "If you cannot prove it, try solving WITHOUT that assumption. "
                  "What changes if the assumption is false?"),
        }
        # Parse scores from conspectus (patterns like "A. Recognition... | 0.7" or "A: 0.7")
        for letter in "ABCDEFGH":
            patterns = [
                rf'{letter}[\.\s].*?(\d+\.?\d*)\s*/\s*1\.0',  # "A. ... 0.7/1.0"
                rf'{letter}[\.\s].*?\|\s*(\d+\.?\d*)\s*\|',    # "| A. ... | 0.7 |"
                rf'checkpoint.*?{letter}.*?(\d+\.?\d*)',         # loose match
            ]
            for p in patterns:
                m = re.search(p, text, re.IGNORECASE)
                if m:
                    try:
                        score = float(m.group(1))
                        if 0 <= score <= 1.0:
                            checkpoints[letter] = {
                                "score": score,
                                "domain": checkpoint_domains[letter],
                                "question": checkpoint_questions[letter],
                            }
                            break
                    except ValueError:
                        continue
        return checkpoints

    # ── Iteration loop ──
    prev_c_approach = None  # P7: track for stagnation detection
    TOKEN_BUDGET = 600_000  # P7: max tokens per question before aborting iteration
    for iteration in range(MAX_CONFIDENCE_ITERATIONS):
        if c_computation is None or c_approach is None:
            print(f"  [Confidence] Could not extract — skipping iteration")
            break

        # P7: Token budget guard
        current_tokens = ((tl.total_input or 0) + (tl.total_output or 0) +
                          (worker.total_input or 0) + (worker.total_output or 0))
        if current_tokens > TOKEN_BUDGET:
            print(f"  [Confidence] TOKEN BUDGET exceeded ({current_tokens:,} > {TOKEN_BUDGET:,}) — "
                  f"accepting current confidence")
            break

        # P7: Stagnation detection (skip on first iteration)
        if prev_c_approach is not None:
            improvement = (c_approach or 0) - (prev_c_approach or 0)
            if improvement < 5:
                print(f"  [Confidence] STAGNATION: c_approach improved only {improvement:+d}pp "
                      f"({prev_c_approach}% -> {c_approach}%) — stopping iterations")
                break
        prev_c_approach = c_approach

        gap = abs(c_computation - c_approach)
        final_conf = min(c_computation, c_approach)
        print(f"  [Confidence] Iter {iteration}: C_comp={c_computation}% C_approach={c_approach}% "
              f"Gap={gap}pp Final={final_conf}%")

        # ── Detect D4 numerical mismatch in conspectus/TL output ──
        d4_mismatch = bool(re.search(
            r'NUMERICAL MISMATCH|D4 MISMATCH DETECTED|model.*is.*wrong|'
            r'error.*≠.*0|RED FLAG.*exact|mismatch.*stoichiom|mismatch.*integer',
            tl_text + conspectus, re.IGNORECASE
        ))
        if d4_mismatch:
            print(f"  [Confidence] D4 NUMERICAL MISMATCH detected in conspectus/TL output")

        # ── Decide whether to iterate ──
        needs_iteration = False
        reason = ""

        if d4_mismatch and iteration == 0:
            needs_iteration = True
            reason = "D4 numerical mismatch — structural model (D2) may be wrong"
        elif extreme_prob_flag and iteration == 0:
            needs_iteration = True
            reason = f"extreme probability P={final_answer}"
        elif c_approach < CONFIDENCE_THRESHOLD:
            needs_iteration = True
            reason = f"C_approach={c_approach}% < threshold {CONFIDENCE_THRESHOLD}%"
        elif gap >= 35:
            needs_iteration = True
            reason = f"gap={gap}pp ≥ 35 — framework likely wrong"
        elif gap >= 20:
            needs_iteration = True
            reason = f"gap={gap}pp ≥ 20 — structural concern"

        if not needs_iteration:
            print(f"  [Confidence] No iteration needed — proceeding")
            break

        # Terminal verdicts can skip iteration ONLY if confidence is adequate.
        # If gap ≥ 35 or C_approach < threshold, iteration is MANDATORY regardless of verdict.
        if verdict in ("threshold_reached",):
            if gap is not None and gap >= 35:
                print(f"  [Confidence] verdict=threshold_reached BUT gap={gap}pp ≥ 35 — OVERRIDING, iteration mandatory")
            elif c_approach is not None and c_approach < CONFIDENCE_THRESHOLD:
                print(f"  [Confidence] verdict=threshold_reached BUT C_approach={c_approach}% < {CONFIDENCE_THRESHOLD}% — OVERRIDING, iteration mandatory")
            else:
                print(f"  [Confidence] Would iterate but verdict is terminal and confidence adequate — skipping")
                break

        print(f"  [Confidence] ITERATING — reason: {reason}")

        # ── Extract checkpoints and find weakest ──
        # BUG FIX: Parse BOTH conspectus AND tl_text — TL's D5 reflect contains
        # updated checkpoint scores that may not be in conspectus yet.
        checkpoints = extract_checkpoints(conspectus + "\n" + tl_text)

        if checkpoints:
            # Sort by score ascending — weakest first
            sorted_cp = sorted(checkpoints.items(), key=lambda x: x[1]["score"])
            weakest = sorted_cp[:3]  # Top 3 weakest checkpoints

            print(f"  [Confidence] Weakest checkpoints: "
                  + ", ".join(f"{k}={v['score']:.1f}→{v['domain']}" for k, v in weakest))

            # ── Route to EARLIEST weak domain ──
            # Principle: if D2 is broken (assumptions invalid), everything after D2
            # is built on sand. Must fix foundation first, then re-derive.
            DOMAIN_ORDER = {"D1": 1, "D2": 2, "D3": 3, "D4": 4, "D5": 5}
            WEAK_THRESHOLD = 0.6  # Below this = "broken" checkpoint

            # Collect all broken checkpoints and their domains
            broken_domains = set()
            for letter, info in checkpoints.items():
                if info["score"] < WEAK_THRESHOLD:
                    broken_domains.add(info["domain"])

            if broken_domains:
                # Route to EARLIEST broken domain
                target_domain = min(broken_domains, key=lambda d: DOMAIN_ORDER.get(d, 99))
                print(f"  [Confidence] Broken domains (score<{WEAK_THRESHOLD}): "
                      + ", ".join(sorted(broken_domains, key=lambda d: DOMAIN_ORDER.get(d, 99)))
                      + f" → routing to earliest: {target_domain}")
            else:
                # All checkpoints ≥ WEAK_THRESHOLD — route to weakest by score
                target_domain = weakest[0][1]["domain"]

            # gap ≥ 35 can push EARLIER but never later than current target
            if gap >= 35 and DOMAIN_ORDER.get("D3", 3) < DOMAIN_ORDER.get(target_domain, 5):
                target_domain = "D3"
                print(f"  [Confidence] gap={gap}pp ≥ 35 — overriding to D3 (earlier than {target_domain})")

            # D4 mismatch ALWAYS routes to D2 — the structural model is wrong,
            # not the computation. Checkpoints may not catch this because D4 score
            # can be high (correct computation on wrong model).
            if d4_mismatch and DOMAIN_ORDER.get(target_domain, 99) > DOMAIN_ORDER.get("D2", 2):
                print(f"  [Confidence] D4 MISMATCH override: {target_domain} → D2 "
                      f"(numerical discrepancy indicates wrong structural model)")
                target_domain = "D2"

            # Build diagnostic instruction with targeted questions
            diag_questions = []
            for i, (letter, info) in enumerate(weakest, 1):
                diag_questions.append(f"{i}. [Checkpoint {letter}, score={info['score']:.1f}] {info['question']}")

            # Add extreme probability questions if flagged
            if extreme_prob_flag:
                diag_questions.append(
                    f"{len(diag_questions)+1}. CRITICAL: Answer P={final_answer} is extreme. "
                    f"PROVE determinism rigorously. Find ANY counterexample configuration."
                )

            # Add D4 mismatch questions if flagged
            if d4_mismatch:
                diag_questions.append(
                    f"{len(diag_questions)+1}. CRITICAL — NUMERICAL MISMATCH: D4 computation "
                    f"does not exactly satisfy the problem constraints. This means the structural "
                    f"model from D2 is likely WRONG. Re-examine ALL D2 proof chains:\n"
                    f"   a) Which assumptions were ASSUMED (not PROVEN)?\n"
                    f"   b) What ALTERNATIVE models exist? (e.g., different reaction type, "
                    f"different stoichiometry, different structural property)\n"
                    f"   c) Try the alternative model — does it give 0.000% error?\n"
                    f"   d) If the alternative works perfectly, SWITCH to it."
                )

            diag_text = "\n".join(diag_questions)

            diag_inst = (
                f"## CONFIDENCE ITERATION {iteration+1}\n\n"
                f"C_approach is {c_approach}% (target: ≥{CONFIDENCE_THRESHOLD}%). "
                f"Reason for iteration: {reason}\n\n"
                f"To raise confidence, address EACH of these questions:\n\n"
                f"{diag_text}\n\n"
                f"For each question:\n"
                f"- Answer explicitly (not 'I already addressed this')\n"
                f"- State what NEW information this provides\n"
                f"- State how it changes your confidence\n\n"
                f"After addressing all questions, re-state your final answer "
                f"and updated worker_confidence.\n\n"
                f"## FULL QUESTION TEXT:\n{q_text}\n\n"
                f"Context:\n{conspectus[:2000]}"
            )

            # ── Execute iteration at target domain ──
            label = f"{target_domain}_confidence_iter{iteration+1}"
            print(f"  [Confidence] Routing to {target_domain} ({label})")

            if target_domain == "D3":
                # Framework switch — need D4 + D5 after
                w_iter, tl_iter, v_iter = run_domain("D3", diag_inst, label=label)
                d4_re_inst = get_instruction(tl_iter, "D4") or diag_inst
                d4_re_inst += f"\n\n## FULL QUESTION:\n{q_text}\n\nContext:\n{conspectus[:2000]}"
                w_d4r, tl_d4r, v_d4r = run_domain("D4", d4_re_inst, label=f"D4_recompute_iter{iteration+1}")
                d5_re_inst = get_instruction(tl_d4r, "D5") or ""
                d5_re_inst += d5_extra
                w_d5r, tl_d5r, v_d5r = run_domain("D5", d5_re_inst, d5_tl_extra, f"D5_recompute_iter{iteration+1}")
                tl_text = tl_d5r
                verdict = v_d5r

            elif target_domain in ("D1", "D2"):
                # Early domain issue — re-run from target through ALL subsequent domains.
                # If D2 (assumptions) is broken, D3 framework may be wrong too → full cascade.
                w_iter, tl_iter, v_iter = run_domain(target_domain, diag_inst, label=label)

                # D2 → D3 → D4 → D5 (or D1 → D3 → D4 → D5)
                d3_re_inst = get_instruction(tl_iter, "D3") or ""
                d3_re_inst += (f"\n\nRe-examine framework with updated {target_domain} output. "
                               f"Assumptions may have changed — verify framework still applies."
                               f"\n## FULL QUESTION:\n{q_text}\n\nContext:\n{conspectus[:2000]}")
                w_d3r, tl_d3r, v_d3r = run_domain("D3", d3_re_inst, label=f"D3_reframework_iter{iteration+1}")

                d4_re_inst = get_instruction(tl_d3r, "D4") or ""
                d4_re_inst += f"\n\nRe-compute with updated framework.\n## FULL QUESTION:\n{q_text}\n\nContext:\n{conspectus[:2000]}"
                w_d4r, tl_d4r, v_d4r = run_domain("D4", d4_re_inst, label=f"D4_recompute_iter{iteration+1}")

                d5_re_inst = get_instruction(tl_d4r, "D5") or ""
                d5_re_inst += d5_extra
                w_d5r, tl_d5r, v_d5r = run_domain("D5", d5_re_inst, d5_tl_extra, f"D5_recompute_iter{iteration+1}")
                tl_text = tl_d5r
                verdict = v_d5r

            else:
                # D4 or D5 issue — iterate at that domain only
                w_iter, tl_iter, v_iter = run_domain(target_domain, diag_inst, d5_tl_extra if target_domain == "D5" else "", label)
                tl_text = tl_iter
                verdict = v_iter

        else:
            # Could not parse checkpoints — use gap-based routing
            # BUG FIX: Previously always routed to D5 even when gap≥35 should → D3.
            # This caused Q3's Worker to get impossible D5 task instead of framework switch.
            if d4_mismatch:
                # D4 mismatch without checkpoints — route to D2 (model is wrong)
                print(f"  [Confidence] No checkpoints + D4 MISMATCH — routing to D2 (structural model revision)")
                diag_inst = (
                    f"## CONFIDENCE ITERATION {iteration+1} — D2 MODEL REVISION\n\n"
                    f"D4 computation found a NUMERICAL MISMATCH with problem constraints.\n"
                    f"This means the structural model from D2 is WRONG.\n\n"
                    f"Re-examine your D2 derivations:\n"
                    f"1. Which proof chains have CONDITIONAL conclusions? Those are suspect.\n"
                    f"2. For each ASSUMED step: what if it's false? What alternative model results?\n"
                    f"3. Are there D1 flags that were closed by CONDITIONAL proofs? Re-open them.\n"
                    f"4. Try the alternative model(s) — does any give EXACT match (0% error)?\n\n"
                    f"## FULL QUESTION:\n{q_text}\n\nContext:\n{conspectus[:2000]}"
                )
                # Run D2 → D3 → D4 → D5 cascade
                w_d2r, tl_d2r, v_d2r = run_domain("D2", diag_inst, label=f"D2_mismatch_iter{iteration+1}")
                d3_re_inst = get_instruction(tl_d2r, "D3") or ""
                d3_re_inst += (f"\n\nRe-examine framework after D2 model revision."
                               f"\n## FULL QUESTION:\n{q_text}\n\nContext:\n{conspectus[:2000]}")
                w_d3r, tl_d3r, v_d3r = run_domain("D3", d3_re_inst, label=f"D3_reframework_iter{iteration+1}")
                d4_re_inst = get_instruction(tl_d3r, "D4") or ""
                d4_re_inst += f"\n\nRe-compute with revised model.\n## FULL QUESTION:\n{q_text}\n\nContext:\n{conspectus[:2000]}"
                w_d4r, tl_d4r, v_d4r = run_domain("D4", d4_re_inst, label=f"D4_recompute_iter{iteration+1}")
                d5_re_inst = get_instruction(tl_d4r, "D5") or ""
                d5_re_inst += d5_extra
                w_d5r, tl_d5r, v_d5r = run_domain("D5", d5_re_inst, d5_tl_extra, f"D5_recompute_iter{iteration+1}")
                tl_text = tl_d5r
                verdict = v_d5r

            elif gap >= 35:
                fallback_domain = "D3"
                print(f"  [Confidence] No checkpoints but gap={gap}pp ≥ 35 — routing to D3 (framework switch)")
                diag_inst = (
                    f"## CONFIDENCE ITERATION {iteration+1} — FRAMEWORK RE-EVALUATION\n\n"
                    f"C_approach is only {c_approach}%. Gap={gap}pp. Reason: {reason}\n\n"
                    f"The current framework may be WRONG. Address:\n"
                    f"1. What alternative mathematical frameworks could solve this problem?\n"
                    f"2. Enumerate at least 3 fundamentally different approaches\n"
                    f"3. For each alternative, compute the answer (at least partially)\n"
                    f"4. If any alternative gives a DIFFERENT answer, explain the discrepancy\n"
                    f"5. List every IMPORTED assumption and check if removing it changes the answer\n"
                )
                if extreme_prob_flag:
                    diag_inst += f"6. PROVE P={final_answer} rigorously. Find ANY counterexample.\n"
                diag_inst += f"\n## FULL QUESTION:\n{q_text}\n\nContext:\n{conspectus[:2000]}"

                # Run D3 → D4 → D5 chain (same as checkpoint-based D3 routing)
                w_d3, tl_d3, v_d3 = run_domain("D3", diag_inst, label=f"D3_framework_iter{iteration+1}")
                d4_re_inst = get_instruction(tl_d3, "D4") or diag_inst
                d4_re_inst += f"\n\n## FULL QUESTION:\n{q_text}\n\nContext:\n{conspectus[:2000]}"
                w_d4r, tl_d4r, v_d4r = run_domain("D4", d4_re_inst, label=f"D4_recompute_iter{iteration+1}")
                d5_re_inst = get_instruction(tl_d4r, "D5") or ""
                d5_re_inst += d5_extra
                w_d5r, tl_d5r, v_d5r = run_domain("D5", d5_re_inst, d5_tl_extra, f"D5_recompute_iter{iteration+1}")
                tl_text = tl_d5r
                verdict = v_d5r

            elif gap >= 20:
                fallback_domain = "D4"
                print(f"  [Confidence] No checkpoints but gap={gap}pp ≥ 20 — routing to D4 (computation)")
                diag_inst = (
                    f"## CONFIDENCE ITERATION {iteration+1} — COMPUTATION RE-CHECK\n\n"
                    f"C_approach is only {c_approach}%. Gap={gap}pp. Reason: {reason}\n\n"
                    f"The computation may have errors. Address:\n"
                    f"1. Verify formula on small concrete example (n=1 or n=2)\n"
                    f"2. Check each computation step independently\n"
                    f"3. Solve using a completely different method and compare\n"
                    f"4. List and verify all IMPORTED assumptions\n"
                )
                if extreme_prob_flag:
                    diag_inst += f"5. PROVE P={final_answer} rigorously. Find ANY counterexample.\n"
                diag_inst += f"\n## FULL QUESTION:\n{q_text}\n\nContext:\n{conspectus[:2000]}"

                # Run D4 → D5 chain
                w_d4, tl_d4, v_d4 = run_domain("D4", diag_inst, label=f"D4_compute_iter{iteration+1}")
                d5_re_inst = get_instruction(tl_d4, "D5") or ""
                d5_re_inst += d5_extra
                w_d5r, tl_d5r, v_d5r = run_domain("D5", d5_re_inst, d5_tl_extra, f"D5_recompute_iter{iteration+1}")
                tl_text = tl_d5r
                verdict = v_d5r

            else:
                fallback_domain = "D5"
                print(f"  [Confidence] No checkpoints, gap={gap}pp < 20 — generic D5 diagnostic")
                diag_inst = (
                    f"C_approach is only {c_approach}%. Reason: {reason}\n"
                    f"Address:\n"
                    f"1. Verify formula on small concrete example (n=1 or n=2)\n"
                    f"2. Solve using a completely different mathematical framework\n"
                    f"3. List and verify all IMPORTED assumptions\n"
                    f"4. Check answer in known databases (OEIS, etc.)\n"
                )
                if extreme_prob_flag:
                    diag_inst += f"5. PROVE P={final_answer} rigorously. Find ANY counterexample.\n"
                diag_inst += f"\n## FULL QUESTION:\n{q_text}\n\nContext:\n{conspectus[:2000]}"

                w_redo, tl_redo, v_redo = run_domain("D5", diag_inst, d5_tl_extra, f"D5_generic_iter{iteration+1}")
                tl_text = tl_redo
                verdict = v_redo

        # ── Re-extract confidence after iteration ──
        # Prefer tl_text (latest) over conspectus (stale)
        c_computation = (extract_confidence(tl_text, "C_computation")
                         or extract_confidence(tl_text, "Worker confidence")
                         or extract_confidence(conspectus, "C_computation")
                         or extract_confidence(conspectus, "Worker confidence")
                         or c_computation)
        c_approach = (extract_confidence(tl_text, "C_approach")
                      or extract_confidence(tl_text, "TL confidence")
                      or extract_confidence(conspectus, "C_approach")
                      or extract_confidence(conspectus, "TL confidence")
                      or c_approach)
        extreme_prob_flag = False  # Don't re-trigger on same answer

    # Final confidence values
    if c_computation is not None and c_approach is not None:
        gap = abs(c_computation - c_approach)
        final_conf = min(c_computation, c_approach)
    else:
        gap = None
        final_conf = c_approach or c_computation

    print(f"  [Confidence] FINAL: C_comp={c_computation}% C_approach={c_approach}% Final={final_conf}%")

    # ── Handle terminal verdicts ──
    if verdict in ("threshold_reached", "plateau", "fundamentally_uncertain"):
        fa_block = extract(tl_text, "final_answer")
        if fa_block:
            final_answer = fa_block.strip()

    if not final_answer:
        # Check if TL already produced answer in D5 reflection
        fa_block = extract(tl_text, "final_answer")
        if fa_block:
            final_answer = fa_block.strip()

    # Get next instruction for potential continuation
    instruction = get_instruction(tl_text)

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
    # Extract dual confidence values from conspectus
    def extract_confidence_final(text, label):
        """Try to find 'label: N%' or 'label N%' or 'label (TL scorecard): N%' in text."""
        patterns = [
            rf'{label}[^:\d]*[:\s]+(\d+)%',
            rf'{label}[^:\d]*[:\s]+(\d+)',
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return int(m.group(1))
        return None

    # Try multiple label variants for robustness
    worker_conf = (
        c_computation  # from pipeline if already extracted
        or extract_confidence_final(conspectus, "C_computation")
        or extract_confidence_final(conspectus, "worker confidence")
        or extract_confidence_final(conspectus, "Worker confidence")
    )
    tl_conf = (
        c_approach  # from pipeline if already extracted
        or extract_confidence_final(conspectus, "C_approach")
        or extract_confidence_final(conspectus, "tl confidence")
        or extract_confidence_final(conspectus, "TL confidence")
    )
    conf_gap = abs(worker_conf - tl_conf) if (worker_conf is not None and tl_conf is not None) else None
    final_conf = min(worker_conf, tl_conf) if (worker_conf is not None and tl_conf is not None) else (tl_conf or worker_conf)

    result = {
        "question_id": q_id,
        "question": q_text[:200] + "..." if len(q_text) > 200 else q_text,
        "raw_subject": question["raw_subject"],
        "answer_type": answer_type,
        "expected": expected,
        "answer_raw": final_answer,
        "judge_correct": is_correct,
        "confidence": {
            "c_computation": worker_conf,     # Worker: "Is my computation correct?"
            "c_approach": tl_conf,            # TL: "Is the approach correct?"
            "gap": conf_gap,                  # |c_computation - c_approach|
            "final": final_conf,              # min(c_computation, c_approach)
            "method": "scorecard_v2_dual",
        },
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
    print(f"  Confidence: C_comp={worker_conf}% C_approach={tl_conf}% Gap={conf_gap}pp Final={final_conf}%")
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
    print("  REGULUS v5 HLE PILOT — Framework-First Architecture")
    print(f"  Profile: {PROFILE_NAME} | Model: {MODEL}")
    print(f"  Base URL: {BASE_URL or 'Anthropic (default)'}")
    print(f"  Thinking: {'ON' if THINKING_ENABLED else 'OFF'}")
    if STOP_AFTER:
        print(f"  Mode: DEBUG STOP AFTER {STOP_AFTER}")
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
