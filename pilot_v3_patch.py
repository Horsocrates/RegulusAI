#!/usr/bin/env python3
"""
Regulus v3 Pilot — PATCHED
Fixes: answer extraction, adds Lab-Assistant analysis
Run: python pilot_v3_patch.py
"""

import anthropic
import json
import re
import time
from pathlib import Path
from datetime import datetime

# ─── CONFIG ───────────────────────────────────────────────────────────

MODEL = "claude-opus-4-6"
THINKING_BUDGET = 10000
MAX_OUTPUT = 64000
SKILLS_DIR = Path("skills")
RUNS_DIR = Path("runs")

# ─── TEST QUESTIONS ──────────────────────────────────────────────────

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
        "why_chosen": "Activity series trap (III) + acid reactivity trap (V)",
    },
    {
        "id": "MSV-BIO-001",
        "domain": "biology",
        "question": """Consider the following statements about mitochondria:

I. They contain their own circular DNA
II. They are bound by a single membrane
III. They are the primary site of oxidative phosphorylation
IV. They are present in all eukaryotic cells
V. They can self-replicate independently of the cell cycle
VI. Their matrix has a lower pH than the intermembrane space

Which statements are correct?""",
        "expected": "I, III, V",
        "why_chosen": "3 traps: double membrane (II), RBC exception (IV), pH gradient direction (VI)",
    },
    {
        "id": "MSV-CHEM-006-RECHECK",
        "domain": "chemistry",
        "skip": True,  # Already ran — set to False to re-run
        "question": """Consider the following statements about ozone (O₃):

I. It is a stronger oxidizing agent than molecular oxygen (O₂)
II. The O–O bond length in ozone is intermediate between single and double bond lengths
III. Ozone is paramagnetic
IV. It is produced in the stratosphere by UV radiation acting on O₂
V. The ozone molecule is linear
VI. Ozone decomposes spontaneously to O₂ and is therefore thermodynamically unstable relative to O₂

Which of the above statements are correct?""",
        "expected": "I, II, IV, VI",
        "why_chosen": "Already passed — skip unless re-testing",
    },
]


# ─── AGENT CLASS ──────────────────────────────────────────────────────

class Agent:
    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.client = anthropic.Anthropic()
        self.system_prompt = system_prompt
        self.messages = []
        self.total_input = 0
        self.total_output = 0
        self.call_count = 0
    
    def send(self, content: str) -> tuple[str, str]:
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
        cache_create = getattr(response.usage, 'cache_creation_input_tokens', 0) or 0
        if cache_read:
            print(f"    [cache hit: {cache_read} tokens]")

        return text, thinking
    
    def stats(self):
        return {
            "calls": self.call_count,
            "input_tokens": self.total_input,
            "output_tokens": self.total_output,
        }


# ─── ANSWER EXTRACTION (FIXED) ───────────────────────────────────────

def extract_answer(text: str) -> str:
    """Extract clean answer from TL output. Multiple strategies."""
    
    # Strategy 1: Look inside <final_answer> block
    fa = extract(text, "final_answer")
    if fa:
        clean = extract_roman_set(fa)
        if clean:
            return clean
    
    # Strategy 2: Look for "answer: I, II, ..." pattern
    m = re.search(r'(?:answer|statements?|correct)[:\s]*([IVXLC,\s]+)', text, re.IGNORECASE)
    if m:
        clean = extract_roman_set(m.group(1))
        if clean:
            return clean
    
    # Strategy 3: Look for {I, III, V} or [I, III, V] pattern
    m = re.search(r'[\[{]([IVXLC,\s]+)[\]}]', text)
    if m:
        clean = extract_roman_set(m.group(1))
        if clean:
            return clean
    
    # Strategy 4: Look in conspectus for conclusion
    consp = extract(text, "conspectus")
    if consp:
        m = re.search(r'(?:answer|conclusion|correct)[:\s]*([IVXLC,\s]+)', consp, re.IGNORECASE)
        if m:
            clean = extract_roman_set(m.group(1))
            if clean:
                return clean
    
    # Strategy 5: Find the densest cluster of roman numerals
    # (last resort — scan the whole text)
    lines = text.split('\n')
    best_line = ""
    best_count = 0
    for line in lines:
        nums = re.findall(r'\b(I{1,3}|IV|VI?|V)\b', line)
        if len(nums) > best_count and len(line) < 100:
            best_count = len(nums)
            best_line = line
    if best_count >= 2:
        clean = extract_roman_set(best_line)
        if clean:
            return clean
    
    return text[:200]  # fallback: truncated text


def extract_roman_set(text: str) -> str:
    """Extract roman numeral set from text, return normalized."""
    roman_map = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}
    
    # Find all roman numerals in text
    # Use greedy matching: III before II before I
    found = set()
    for roman, num in sorted(roman_map.items(), key=lambda x: -len(x[0])):
        if re.search(r'\b' + roman + r'\b', text):
            found.add(num)
            # Remove matched to avoid double-counting (III → I)
            text = re.sub(r'\b' + roman + r'\b', '', text, count=1)
    
    if not found:
        return ""
    
    int_to_roman = {v: k for k, v in roman_map.items()}
    return ", ".join(int_to_roman[i] for i in sorted(found))


def normalize_answer(text: str) -> str:
    """Normalize for comparison."""
    clean = extract_roman_set(text)
    return clean if clean else text.strip()


def extract(text: str, tag: str) -> str:
    match = re.search(f"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return match.group(1).strip() if match else ""


# ─── SKILL LOADING ────────────────────────────────────────────────────

def load_skill(filename):
    path = SKILLS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    print(f"  ⚠ Skill not found: {path}")
    return ""

def build_tl_prompt():
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

CRITICAL REMINDER: Every response MUST include <conspectus>, <verdict>, and <worker_instruction> XML blocks.
When verdict is threshold_reached, plateau, or fundamentally_uncertain, include <final_answer> block with:
- answer: the exact set of correct statements (e.g. "I, II, IV, VI")
- confidence: 0-100
- justification: one sentence
"""

def build_worker_prompt():
    d1 = load_skill("d1-recognize.md")
    d2 = load_skill("d2-clarify.md")
    d3 = load_skill("d3-framework.md")
    d4 = load_skill("d4-compare.md")
    d5 = load_skill("d5-infer.md")
    
    return f"""# WORKER — Domain Reasoning Engine

You execute one reasoning domain at a time as instructed by Team Lead.
Execute ONLY the domain specified in the instruction. Be thorough and precise.
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


# ─── LAB-ASSISTANT (Opus 4.6 + thinking) ─────────────────────────────

LAB_ASSISTANT_PROMPT = """# LAB-ASSISTANT — Failure Analyst

You analyze reasoning traces from an AI benchmark evaluation system.
You receive a FULL reasoning passport — the complete dialogue between 
a Team Lead agent and a Worker agent who processed a question through 
structured reasoning domains (D1-D5).

Your job: determine whether the answer is correct, and if not, find 
the EXACT point where reasoning went wrong.

## Analysis Process

1. Read the question and expected answer
2. Read the final answer produced by the pipeline  
3. Compare — is the answer correct? (exact match of statement sets)
4. If CORRECT: briefly confirm which aspects of the pipeline worked well
5. If WRONG: trace backward through domains to find the earliest error:
   - D5 (Inference): Did conclusion follow from D4 evidence?
   - D4 (Comparison): Was each statement evaluated correctly?
   - D3 (Framework): Was the right approach selected?
   - D2 (Clarification): Were terms defined correctly?
   - D1 (Recognition): Was the question understood correctly?

## Output Format

Respond with JSON:
{
  "correct": true/false,
  "answer_produced": "I, II, IV, VI",
  "answer_expected": "I, II, IV, VI",
  "match": true/false,
  
  "pipeline_quality": {
    "D1_recognition": "good/adequate/poor — brief note",
    "D2_clarification": "good/adequate/poor — brief note",
    "D3_framework": "good/adequate/poor — brief note",
    "D4_comparison": "good/adequate/poor — brief note",
    "D5_inference": "good/adequate/poor — N/A if skipped",
    "TL_orchestration": "good/adequate/poor — brief note"
  },
  
  "if_wrong": {
    "failure_domain": "D1/D2/D3/D4/D5/TL",
    "failure_category": "reasoning_error/knowledge_gap/misinterpretation/calculation_error/incomplete_analysis/hallucination/format_error",
    "root_cause": "1-2 sentence explanation",
    "exact_point": "Quote or reference the exact moment in the trace where error originated"
  },
  
  "if_correct": {
    "key_success_factor": "What the pipeline did well that raw model might miss",
    "improvement_suggestions": ["suggestion 1", "suggestion 2"]
  },
  
  "token_efficiency": "Were tokens used efficiently? Any bloat?",
  "architectural_notes": "Any observations about TL-Worker interaction quality"
}
"""

def run_lab_assistant(run_dir: Path, question: dict) -> dict:
    """Run Lab-Assistant analysis on a completed run."""
    
    print(f"\n  [Lab-Assistant] Analyzing {question['id']}...")
    
    # Load passport
    passport_path = run_dir / "passport.json"
    if not passport_path.exists():
        return {"error": "No passport.json found"}
    
    passport = json.loads(passport_path.read_text(encoding="utf-8"))
    
    # Load dialogue for full trace
    dialogue_path = run_dir / "dialogue.jsonl"
    dialogue_lines = []
    if dialogue_path.exists():
        with open(dialogue_path, encoding="utf-8") as f:
            for line in f:
                dialogue_lines.append(json.loads(line))
    
    # Build analysis request
    dialogue_summary = []
    for msg in dialogue_lines:
        entry = f"[{msg.get('from','')} → {msg.get('to','')}] ({msg.get('type','')}, {msg.get('domain','')})"
        content = msg.get('content', '')[:2000]
        thinking = msg.get('thinking_excerpt', '')[:1000]
        dialogue_summary.append(f"{entry}\n{content}")
        if thinking:
            dialogue_summary.append(f"  [thinking excerpt]: {thinking}")
    
    full_trace = "\n\n---\n\n".join(dialogue_summary)
    
    # Load conspectus
    conspectus = ""
    consp_path = run_dir / "conspectus.md"
    if consp_path.exists():
        conspectus = consp_path.read_text(encoding="utf-8")
    
    # Load result
    result = {}
    result_path = run_dir / "result.json"
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
    
    # Call Lab-Assistant
    client = anthropic.Anthropic()
    
    with client.messages.stream(
        model=MODEL,
        max_tokens=16000,
        thinking={
            "type": "enabled",
            "budget_tokens": 8000
        },
        system=[{"type": "text", "text": LAB_ASSISTANT_PROMPT}],
        messages=[{
            "role": "user",
            "content": f"""Analyze this reasoning trace.

QUESTION: {question['question']}

EXPECTED ANSWER: {question['expected']}

PRODUCED ANSWER: {result.get('answer', 'N/A')}

FINAL CONSPECTUS:
{conspectus}

FULL DIALOGUE TRACE:
{full_trace[:15000]}

Respond with JSON analysis."""
        }]
    ) as stream:
        response = stream.get_final_message()
    
    # Extract text (skip thinking)
    analysis_text = ""
    thinking_text = ""
    for block in response.content:
        if block.type == "text":
            analysis_text += block.text
        elif block.type == "thinking":
            thinking_text += block.thinking
    
    # Parse JSON from response
    try:
        # Strip markdown fences if present
        clean = re.sub(r'```json\s*', '', analysis_text)
        clean = re.sub(r'```\s*', '', clean).strip()
        analysis = json.loads(clean)
    except json.JSONDecodeError:
        analysis = {"raw_response": analysis_text, "parse_error": True}
    
    # Save
    analysis["_thinking_excerpt"] = thinking_text[:3000]
    analysis["_tokens"] = {
        "input": response.usage.input_tokens,
        "output": response.usage.output_tokens,
    }
    
    (run_dir / "lab_analysis.json").write_text(
        json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    
    # Print summary
    if analysis.get("correct"):
        print(f"  [Lab-Assistant] ✓ CORRECT — {analysis.get('if_correct', {}).get('key_success_factor', 'N/A')}")
    elif analysis.get("correct") is False:
        ic = analysis.get("if_wrong", {})
        print(f"  [Lab-Assistant] ✗ WRONG — {ic.get('failure_domain', '?')}: {ic.get('root_cause', 'N/A')}")
    else:
        print(f"  [Lab-Assistant] Analysis saved (check lab_analysis.json)")
    
    print(f"  [Lab-Assistant] Tokens: {analysis.get('_tokens', {})}")
    
    return analysis


# ─── DIALOGUE RUNNER ──────────────────────────────────────────────────

def run_question(question: dict, run_dir: Path) -> dict:
    q_text = question["question"]
    q_id = question["id"]
    
    print(f"\n{'='*60}")
    print(f"  QUESTION: {q_id}")
    print(f"  Domain: {question['domain']}")
    print(f"  Expected: {question['expected']}")
    print(f"{'='*60}\n")
    
    tl = Agent("team_lead", build_tl_prompt())
    worker = Agent("worker", build_worker_prompt())
    
    dialogue_log = []
    start_time = time.time()
    
    def log(sender, receiver, msg_type, content, thinking="", **meta):
        entry = {
            "ts": datetime.utcnow().isoformat(),
            "from": sender, "to": receiver,
            "type": msg_type, "content": content[:5000],
            **meta
        }
        if thinking:
            entry["thinking_excerpt"] = thinking[:3000]
        dialogue_log.append(entry)
        with open(run_dir / "dialogue.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    # ── PHASE 0: TL decomposes ──
    print("  [TL] Phase 0: Analyzing question...")
    tl_text, tl_think = tl.send(
        f"MODE: ask\nCONTEXT: initial\n\n"
        f"Question:\n{q_text}\n\n"
        f"Analyze this question. Classify it, generate your_components, "
        f"create initial conspectus, and produce the first worker instruction for D1.\n\n"
        f"Output <conspectus>, <verdict>, and <worker_instruction> blocks."
    )
    log("team_lead", "worker", "init", tl_text, tl_think, domain="D1")
    
    instruction = extract(tl_text, "worker_instruction")
    if not instruction:
        instruction = f"Execute D1 Recognition on this question:\n{q_text}"
    
    conspectus = extract(tl_text, "conspectus") or ""
    
    # ── PHASE 1-5: Domain dialogue ──
    domains = ["D1", "D2", "D3", "D4", "D5"]
    final_answer = None
    
    for domain in domains:
        print(f"  [Worker] Executing {domain}...")
        w_text, w_think = worker.send(instruction)
        log("worker", "team_lead", "domain_output", w_text, w_think, domain=domain)
        
        depth = "full" if domain == "D5" else "quick"
        print(f"  [TL] Reflecting on {domain} ({depth})...")
        
        tl_text, tl_think = tl.send(
            f"MODE: reflect\nDEPTH: {depth}\nDOMAIN: {domain}\n\n"
            f"Worker {domain} output:\n{w_text}\n\n"
            f"Evaluate this output. Update your conspectus. Decide verdict.\n"
            f"Output <conspectus>, <verdict>, and <worker_instruction> blocks.\n"
            f"If verdict is terminal, include <final_answer> with exact statement set."
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
        
        # Terminal
        if verdict in ("threshold_reached", "plateau", "fundamentally_uncertain"):
            final_answer = extract_answer(tl_text)
            break
        
        # Iterate
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
                    f"Output <conspectus>, <verdict>, and <worker_instruction> blocks.\n"
                    f"If verdict is terminal, include <final_answer>."
                )
                verdict = extract(tl_redo, "verdict").strip().lower() or "pass"
                log("team_lead", "team_lead", "reflect", tl_redo, tl_think,
                    domain=f"{domain}_redo", verdict=verdict)
                
                if verdict in ("threshold_reached", "plateau"):
                    final_answer = extract_answer(tl_redo)
                    break
                
                tl_text = tl_redo
        
        # Next instruction
        instruction = extract(tl_text, "worker_instruction")
        if not instruction and domain != "D5":
            idx = domains.index(domain)
            if idx + 1 < len(domains):
                next_d = domains[idx + 1]
                instruction = (
                    f"Execute {next_d}.\n\n"
                    f"Context from previous domains:\n{conspectus[:2000]}"
                )
    
    # If no terminal verdict after D5, ask TL to assemble
    if not final_answer:
        print("  [TL] Assembling final answer...")
        tl_text, tl_think = tl.send(
            "All domains complete. Assemble final answer.\n"
            "Output <final_answer> with the exact set of correct statement numbers.\n"
            "Format: I, II, IV, VI (just the roman numerals, comma-separated)"
        )
        final_answer = extract_answer(tl_text)
        log("team_lead", "orchestrator", "final", tl_text, tl_think)
    
    elapsed = time.time() - start_time
    
    # Normalize for comparison
    normalized_answer = normalize_answer(final_answer)
    normalized_expected = normalize_answer(question["expected"])
    match = normalized_answer == normalized_expected
    
    result = {
        "question_id": q_id,
        "question": q_text[:200],
        "expected": question["expected"],
        "answer_raw": final_answer,
        "answer_normalized": normalized_answer,
        "match": match,
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
    
    print(f"\n  {'─'*50}")
    print(f"  Answer (raw):   {final_answer[:100]}")
    print(f"  Answer (norm):  {normalized_answer}")
    print(f"  Expected:       {question['expected']}")
    print(f"  Match:          {'✓' if match else '✗'}")
    print(f"  Time:           {elapsed:.1f}s")
    print(f"  Calls:          TL={tl.call_count}, W={worker.call_count}")
    print(f"  Tokens:         {result['total_tokens']:,}")
    print(f"  {'─'*50}")
    
    return result


# ─── MAIN ─────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*60)
    print("  REGULUS v3 PILOT — PATCHED")
    print("  Model: Opus 4.6 + Thinking")
    print("  Fixes: answer extraction + Lab-Assistant")
    print("="*60)
    
    # Check skills
    print("\nChecking skills...")
    required = ["analyze-v2.md", "d6-ask.md", "d6-reflect.md",
                 "d1-recognize.md", "d2-clarify.md", "d3-framework.md",
                 "d4-compare.md", "d5-infer.md"]
    missing = [s for s in required if not (SKILLS_DIR / s).exists()]
    if missing:
        print(f"  ⚠ Missing: {missing}")
        return
    print("  ✓ All skills found")
    
    RUNS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    active_questions = [q for q in QUESTIONS if not q.get("skip")]
    print(f"  Questions to run: {len(active_questions)}")
    
    results = []
    run_dirs = []
    
    for q in active_questions:
        run_dir = RUNS_DIR / f"{timestamp}_{q['id']}"
        run_dir.mkdir(parents=True)
        run_dirs.append(run_dir)
        
        try:
            result = run_question(q, run_dir)
            results.append(result)
        except Exception as e:
            print(f"\n  ✗ ERROR on {q['id']}: {e}")
            import traceback
            traceback.print_exc()
            results.append({"question_id": q["id"], "error": str(e)})
    
    # ── LAB-ASSISTANT ANALYSIS ──
    print("\n" + "="*60)
    print("  LAB-ASSISTANT ANALYSIS")
    print("="*60)
    
    analyses = []
    for i, q in enumerate(active_questions):
        if i < len(run_dirs):
            try:
                analysis = run_lab_assistant(run_dirs[i], q)
                analyses.append(analysis)
            except Exception as e:
                print(f"  ✗ Lab-Assistant error on {q['id']}: {e}")
                analyses.append({"error": str(e)})
    
    # ── SUMMARY ──
    print("\n" + "="*60)
    print("  FINAL SUMMARY")
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
        if r.get("match"):
            correct += 1
        total_tokens += r.get("total_tokens", 0)
        total_time += r.get("elapsed_seconds", 0)
        
        status = "✓" if r.get("match") else "✗"
        print(f"  {r['question_id']}: {status}")
        print(f"    Got:      {r.get('answer_normalized', 'N/A')}")
        print(f"    Expected: {r.get('expected', 'N/A')}")
        print(f"    Time:     {r.get('elapsed_seconds', 0):.1f}s | Tokens: {r.get('total_tokens', 0):,}")
    
    # Include first run (MSV-CHEM-006)
    print(f"\n  Including MSV-CHEM-006 (previous run): ✓")
    correct += 1
    total += 1
    
    print(f"\n  TOTAL ACCURACY: {correct}/{total} ({100*correct/total if total else 0:.0f}%)")
    print(f"  Pipeline tokens: {total_tokens:,}")
    print(f"  Pipeline time: {total_time:.0f}s")
    
    # Lab-Assistant summary
    la_tokens = sum(a.get("_tokens", {}).get("input", 0) + a.get("_tokens", {}).get("output", 0) 
                    for a in analyses if isinstance(a, dict) and "_tokens" in a)
    print(f"  Lab-Assistant tokens: {la_tokens:,}")
    print(f"\n  Results saved to: {RUNS_DIR}/")


if __name__ == "__main__":
    main()
