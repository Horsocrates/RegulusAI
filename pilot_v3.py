#!/usr/bin/env python3
"""
Regulus v3 Pilot — Two-Agent Dialogue Test
Run: python pilot_v3.py
Requires: ANTHROPIC_API_KEY env variable
"""

import anthropic
import json
import re
import time
from pathlib import Path
from datetime import datetime

# ─── CONFIG ───────────────────────────────────────────────────────────

MODEL = "claude-opus-4-6"          # Both agents use Opus 4.6
THINKING_BUDGET = 10000             # Thinking tokens per call
MAX_OUTPUT = 64000                  # Max output tokens (must be > THINKING_BUDGET)
SKILLS_DIR = Path("skills")         # Skills directory
RUNS_DIR = Path("runs")             # Output directory

# ─── TEST QUESTIONS (HLE failures we should fix) ─────────────────────

QUESTIONS = [
    {
        "id": "MSV-CHEM-007",
        "domain": "chemistry",
        "question": """Consider the following statements about copper (Cu):

I. It has two common oxidation states: +1 and +2
II. Copper(II) sulfate pentahydrate is blue in color
III. Copper is more reactive than zinc in the activity series
IV. It is used in electrical wiring due to its high conductivity
V. Copper reacts readily with dilute hydrochloric acid to produce hydrogen gas
VI. The green patina on copper roofs is primarily copper(II) carbonate

Which of the above statements are correct?""",
        "expected": "I, II, IV, VI",
        "why_chosen": "EXTRACTION VERIFICATION — Round 2 reasoning was correct (conspectus had I,II,IV,VI) but extraction bug returned I-VI. Verifies fix.",
    },
    {
        "id": "MSV-CHEM-001",
        "domain": "chemistry",
        "question": """Consider the following statements about sulfuric acid (H₂SO₄):

I. It is a diprotic acid
II. It has a boiling point above 300°C
III. It is a strong oxidizing agent when concentrated
IV. Its first dissociation is weak in aqueous solution
V. It can dehydrate sugars to produce carbon
VI. It is produced industrially via the Haber process

Which of the above statements are correct?""",
        "expected": "I, II, III, V",
        "why_chosen": "Haber/Contact process trap (VI), Ka₁ trap (IV). Tests calibration on fresh question.",
    },
    {
        "id": "MSV-BIO-002",
        "domain": "biology",
        "question": """Consider the following statements about the human immune system:

I. B cells produce antibodies as part of the adaptive immune response
II. Natural killer (NK) cells are part of the adaptive immune system
III. The complement system can be activated by antibodies bound to pathogens
IV. T helper cells directly kill virus-infected cells
V. Macrophages can act as antigen-presenting cells
VI. Memory B cells are responsible for the faster secondary immune response

Which of the above statements are correct?""",
        "expected": "I, III, V, VI",
        "why_chosen": "NK innate/adaptive trap (II), T helper/cytotoxic trap (IV). Tests biology generalization.",
    },
]


# ─── AGENT CLASS ──────────────────────────────────────────────────────

class Agent:
    """Thin wrapper around Messages API with thinking support."""
    
    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.client = anthropic.Anthropic()
        self.system_prompt = system_prompt
        self.messages = []
        self.total_input = 0
        self.total_output = 0
        self.total_thinking = 0
        self.call_count = 0
    
    def send(self, content: str) -> str:
        self.messages.append({"role": "user", "content": content})

        # Use streaming to avoid SDK timeout for large max_tokens
        with self.client.messages.stream(
            model=MODEL,
            max_tokens=MAX_OUTPUT,
            thinking={
                "type": "enabled",
                "budget_tokens": THINKING_BUDGET
            },
            system=[{
                "type": "text",
                "text": self.system_prompt,
                "cache_control": {"type": "ephemeral"}
            }],
            messages=self.messages
        ) as stream:
            response = stream.get_final_message()

        # Extract text (skip thinking blocks for conversation, but log them)
        text_parts = []
        thinking_parts = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "thinking":
                thinking_parts.append(block.thinking)

        text = "\n".join(text_parts)
        thinking = "\n---\n".join(thinking_parts) if thinking_parts else ""

        self.messages.append({"role": "assistant", "content": response.content})

        self.total_input += response.usage.input_tokens
        self.total_output += response.usage.output_tokens
        self.call_count += 1

        # Log cache stats
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
    print(f"  ⚠ Skill not found: {path}")
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


# ─── DIALOGUE RUNNER ──────────────────────────────────────────────────

def run_question(question: dict, run_dir: Path) -> dict:
    """Run two-agent dialogue on a single question."""
    
    q_text = question["question"]
    q_id = question["id"]
    
    print(f"\n{'='*60}")
    print(f"  QUESTION: {q_id}")
    print(f"  Domain: {question['domain']}")
    print(f"  Expected: {question['expected']}")
    print(f"{'='*60}\n")
    
    # Initialize agents
    tl = Agent("team_lead", build_tl_prompt())
    worker = Agent("worker", build_worker_prompt())
    
    dialogue_log = []
    start_time = time.time()
    
    def log(sender, receiver, msg_type, content, thinking="", **meta):
        entry = {
            "ts": datetime.utcnow().isoformat(),
            "from": sender, "to": receiver,
            "type": msg_type, "content": content[:3000],
            **meta
        }
        if thinking:
            entry["thinking_excerpt"] = thinking[:2000]
        dialogue_log.append(entry)
        
        # Also write to JSONL in real-time
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
        # Fallback: use full question text directly
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
        
        # Worker executes domain
        w_text, w_think = worker.send(instruction)
        log("worker", "team_lead", "domain_output", w_text, w_think, domain=domain)
        
        # Team Lead reflects
        depth = "full" if domain == "D5" else "quick"
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
            # Try to find verdict in text
            for v in ["threshold_reached", "pass", "iterate", "paradigm_shift", "plateau"]:
                if v in tl_text.lower():
                    verdict = v
                    break
            if not verdict:
                verdict = "pass"  # default
        
        log("team_lead", "team_lead", "reflect", tl_text, tl_think, 
            domain=domain, verdict=verdict)
        
        # Update conspectus
        new_conspectus = extract(tl_text, "conspectus")
        if new_conspectus:
            conspectus = new_conspectus
            (run_dir / "conspectus.md").write_text(conspectus, encoding="utf-8")
        
        print(f"  [TL] Verdict: {verdict}")
        
        # Handle terminal verdicts
        if verdict in ("threshold_reached", "plateau", "fundamentally_uncertain"):
            # EXTRACTION PRIORITY CHAIN:
            # 1. Parse verdicts from conspectus (most reliable — structured data)
            # 2. Extract <final_answer> block and parse "answer:" line
            # 3. Dedicated extraction call to TL (last resort)
            
            final_answer = extract_answer_from_conspectus(conspectus)
            
            if not final_answer:
                fa_block = extract(tl_text, "final_answer")
                if fa_block:
                    final_answer = extract_clean_answer(fa_block)
            
            if not final_answer:
                # Last resort: ask TL for clean answer only
                print("  [TL] Extracting clean answer...")
                tl_extract, _ = tl.send(
                    "Output ONLY the final answer. No explanation. No analysis.\n"
                    "Format: <final_answer>I, II, IV, VI</final_answer>\n"
                    "Replace with the actual correct statements from your analysis."
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
        # Try conspectus first
        final_answer = extract_answer_from_conspectus(conspectus)
    
    if not final_answer:
        # Dedicated extraction call — strict format
        print("  [TL] Extracting clean answer...")
        tl_text, tl_think = tl.send(
            "Output ONLY the final answer set. No explanation. No analysis. No bullet points.\n\n"
            "Format exactly like this example:\n"
            "<final_answer>I, II, IV, VI</final_answer>\n\n"
            "Replace with the actual correct statements from your conspectus."
        )
        fa_block = extract(tl_text, "final_answer")
        if fa_block:
            final_answer = fa_block.strip()
        else:
            final_answer = extract_clean_answer(tl_text)
        log("team_lead", "orchestrator", "final", tl_text, tl_think, verdict="extracted")
    
    elapsed = time.time() - start_time
    
    # ── BUILD RESULT ──
    normalized = normalize_answer(final_answer)
    expected_normalized = normalize_answer(question["expected"])
    
    print(f"  [Extract] final_answer raw: {repr(final_answer[:200] if final_answer else 'None')}")
    print(f"  [Extract] normalized: {normalized}")
    
    result = {
        "question_id": q_id,
        "question": q_text,
        "expected": question["expected"],
        "expected_normalized": expected_normalized,
        "answer_raw": final_answer,
        "answer_normalized": normalized,
        "correct": normalized == expected_normalized,
        "elapsed_seconds": round(elapsed, 1),
        "team_lead_stats": tl.stats(),
        "worker_stats": worker.stats(),
        "total_calls": tl.call_count + worker.call_count,
        "total_tokens": tl.total_input + tl.total_output + worker.total_input + worker.total_output,
    }
    
    # Save result
    (run_dir / "result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    
    # Save final conspectus
    (run_dir / "conspectus.md").write_text(conspectus, encoding="utf-8")
    
    # Build passport (full trace)
    passport = {
        "version": "1.0",
        "run_id": run_dir.name,
        "question": question,
        "result": result,
        "dialogue": dialogue_log,
        "conspectus_final": conspectus,
    }
    (run_dir / "passport.json").write_text(
        json.dumps(passport, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    
    # Print summary
    match = normalized == expected_normalized
    print(f"\n  {'─'*50}")
    print(f"  Answer:     {normalized}")
    print(f"  Expected:   {expected_normalized}")
    print(f"  Match:      {'✓' if match else '✗'}")
    print(f"  Time:       {elapsed:.1f}s")
    print(f"  Calls:      TL={tl.call_count}, W={worker.call_count}")
    print(f"  Tokens:     {result['total_tokens']:,}")
    print(f"  {'─'*50}")
    
    return result


def extract_clean_answer(raw_final_answer: str) -> str:
    """
    Extract the actual answer from a final_answer block.
    Priority chain: answer: line → "X are correct" pattern → comma-separated list → fallback.
    """
    if not raw_final_answer:
        return ""
    
    text = raw_final_answer
    
    # Strip markdown bold/italic before pattern matching
    text_clean = re.sub(r'\*{1,2}', '', text)
    text_clean = re.sub(r'[✅❌✓✗•]', '', text_clean)
    
    # Priority 1: "answer:" line (from our format spec)
    answer_line = re.search(r'^answer:\s*(.+?)$', text_clean, re.IGNORECASE | re.MULTILINE)
    if answer_line:
        return answer_line.group(1).strip()
    
    # Priority 2: "Statements X, Y, and Z are correct" pattern
    # Handle separators: ", " and ", and " and " and " and " & "
    correct_pattern = re.search(
        r'[Ss]tatements?\s+((?:[IVX]+(?:\s*,\s*(?:and\s+)?|\s+and\s+|\s*&\s*))*[IVX]+)\s+are\s+correct',
        text_clean
    )
    if correct_pattern:
        return correct_pattern.group(1)
    
    # Priority 3: "correct:? X, Y, Z" or "answer is X, Y, Z"
    list_pattern = re.search(
        r'(?:correct|answer(?:\s+is)?)[:\s]+((?:[IVX]+(?:\s*,\s*(?:and\s+)?|\s+and\s+))*[IVX]+)',
        text_clean, re.IGNORECASE
    )
    if list_pattern:
        return list_pattern.group(1)
    
    # Priority 4: First line that is ONLY a comma-separated roman numeral list
    for line in text_clean.split('\n'):
        line = line.strip().rstrip('.')
        if re.match(r'^[IVX]+(?:\s*,\s*[IVX]+)+$', line):
            return line
    
    # Priority 5: Return empty — don't return raw text that would confuse normalize_answer
    return ""


def extract_answer_from_conspectus(conspectus: str) -> str:
    """
    Parse structured verdicts from conspectus to compose answer.
    Conspectus has D4/D5 sections with per-element verdicts.
    This is the MOST RELIABLE source because it's structured data.
    """
    if not conspectus:
        return ""
    
    # Strategy 1: Find explicit "Conclusion:" or "Answer:" in D5 section
    d5_section = re.search(r'###?\s*D5.*?(?=###?\s*D6|###?\s*Convergence|###?\s*Attention|###?\s*Open|###?\s*Disagree|$)', 
                           conspectus, re.DOTALL | re.IGNORECASE)
    if d5_section:
        d5_text = d5_section.group(0)
        # Look for "Conclusion: I, II, IV, VI" or "Answer: I, III, V"
        conclusion = re.search(r'(?:conclusion|answer|correct)[:\s]+([IVX,\s\+and&]+)', 
                               d5_text, re.IGNORECASE)
        if conclusion:
            return conclusion.group(1).strip()
    
    # Strategy 2: Parse per-element verdicts from D4 section
    d4_section = re.search(r'###?\s*D4.*?(?=###?\s*D5|$)', conspectus, re.DOTALL | re.IGNORECASE)
    if d4_section:
        d4_text = d4_section.group(0)
        # Find patterns like "E1: true", "I: TRUE(95%)", "Statement I: true"
        true_statements = []
        
        # Pattern: "I: true/TRUE" or "E1: true" or "Statement I: true"
        for match in re.finditer(
            r'(?:E(\d+)|(?:Statement\s+)?([IVX]+))[:\s]+(?:\*\*)?true(?:\*\*)?(?:\s*\(?\d+%?\)?)?',
            d4_text, re.IGNORECASE
        ):
            if match.group(1):  # E1, E2 format
                true_statements.append(int(match.group(1)))
            elif match.group(2):  # Roman numeral format
                roman_to_int = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}
                val = roman_to_int.get(match.group(2).upper(), 0)
                if val:
                    true_statements.append(val)
        
        if true_statements:
            int_to_roman = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI"}
            return ", ".join(int_to_roman[i] for i in sorted(set(true_statements)) if i in int_to_roman)
    
    # Strategy 3: Look for ANY "answer:" line anywhere in conspectus
    answer_line = re.search(r'^(?:\*\*)?answer(?:\*\*)?[:\s]+(.+?)$', conspectus, 
                            re.IGNORECASE | re.MULTILINE)
    if answer_line:
        return answer_line.group(1).strip()
    
    return ""


def normalize_answer(text: str) -> str:
    """Normalize answer for comparison. Handles multiple formats."""
    if not text:
        return ""
    
    # Clean extraction first
    clean = extract_clean_answer(text)
    
    # Strip markdown formatting
    clean = re.sub(r'\*\*', '', clean)
    clean = re.sub(r'[✅❌✓✗]', '', clean)
    clean = clean.replace(' and ', ', ')
    clean = clean.replace(' & ', ', ')
    
    # Extract roman numerals — but ONLY from the clean answer string
    nums = re.findall(r'\b(I{1,3}|IV|VI?|V)\b', clean.upper())
    
    # Convert to sorted set (deduplicate)
    roman_to_int = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}
    ints = sorted(set(roman_to_int.get(n, 0) for n in nums))
    int_to_roman = {v: k for k, v in roman_to_int.items()}
    return ", ".join(int_to_roman.get(i, str(i)) for i in ints if i > 0)


# ─── MAIN ─────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*60)
    print("  REGULUS v3 PILOT — Two-Agent Dialogue Test")
    print("  Model: Opus 4.6 + Thinking")
    print(f"  Questions: {len(QUESTIONS)}")
    print("="*60)
    
    # Check skills
    print("\nChecking skills...")
    required = ["analyze-v2.md", "d6-ask.md", "d6-reflect.md",
                 "d1-recognize.md", "d2-clarify.md", "d3-framework.md",
                 "d4-compare.md", "d5-infer.md"]
    missing = [s for s in required if not (SKILLS_DIR / s).exists()]
    if missing:
        print(f"  ⚠ Missing skills: {missing}")
        print(f"  Copy them to ./{SKILLS_DIR}/ before running.")
        print(f"  Available: {[f.name for f in SKILLS_DIR.iterdir() if f.is_file()]}" if SKILLS_DIR.exists() else "")
        return
    print("  ✓ All skills found")
    
    # Create runs directory
    RUNS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    results = []
    
    for q in QUESTIONS:
        run_dir = RUNS_DIR / f"{timestamp}_{q['id']}"
        run_dir.mkdir(parents=True)
        
        try:
            result = run_question(q, run_dir)
            results.append(result)
        except Exception as e:
            print(f"\n  ✗ ERROR on {q['id']}: {e}")
            import traceback
            traceback.print_exc()
            results.append({"question_id": q["id"], "error": str(e)})
    
    # ── SUMMARY ──
    print("\n" + "="*60)
    print("  SUMMARY")
    print("="*60)
    
    correct = 0
    total = 0
    total_tokens = 0
    total_time = 0
    
    for r in results:
        if "error" in r:
            print(f"  {r['question_id']}: ERROR — {r['error']}")
            continue
        
        total += 1
        match = r.get("correct", False)
        if match:
            correct += 1
        total_tokens += r.get("total_tokens", 0)
        total_time += r.get("elapsed_seconds", 0)
        
        print(f"  {r['question_id']}: {'✓' if match else '✗'}")
        print(f"    Got:      {r.get('answer_normalized', 'N/A')}")
        print(f"    Expected: {r.get('expected_normalized', 'N/A')}")
        print(f"    Time:     {r.get('elapsed_seconds', 0):.1f}s | Tokens: {r.get('total_tokens', 0):,}")
    
    print(f"\n  Accuracy: {correct}/{total} ({100*correct/total if total else 0:.0f}%)")
    print(f"  Total tokens: {total_tokens:,}")
    print(f"  Total time: {total_time:.0f}s")
    print(f"  Results saved to: {RUNS_DIR}/")


if __name__ == "__main__":
    main()
