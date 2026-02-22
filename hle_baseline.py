#!/usr/bin/env python3
"""
Baseline test: Raw GLM-5 (thinking + tools) on HLE questions.
No pipeline, no framework — just the question directly to the model.

Usage: python hle_baseline.py seeds/hle_seed_round2_3q.json
"""

import anthropic
import json
import os
import re
import sys
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

# Z.ai key mapping
if os.environ.get("ZAI_API_KEY") and not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
    os.environ["ANTHROPIC_AUTH_TOKEN"] = os.environ["ZAI_API_KEY"]

# Safe encoding for Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

BASE_URL = "https://api.z.ai/api/anthropic"
MODEL = "glm-5"
THINKING_BUDGET = 64000
MAX_OUTPUT = 128000

# Python execution tool (same as pipeline)
TOOLS = [
    {
        "name": "python_exec",
        "description": "Execute Python 3 code. Use for calculations, simulations, data analysis. Returns stdout+stderr. Max 30s timeout.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python 3 code to execute"}
            },
            "required": ["code"]
        }
    }
]


def run_python(code: str) -> str:
    """Execute Python code and return output."""
    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout
        if result.stderr:
            output += "\n[stderr]\n" + result.stderr
        return output[:5000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "[ERROR] Execution timed out (30s)"
    except Exception as e:
        return f"[ERROR] {e}"


def ask_model(question: str, answer_type: str) -> dict:
    """Send question directly to GLM-5 with thinking and tools."""

    if answer_type == "multipleChoice":
        format_instruction = """
Answer with EXACTLY this format:
answer: [letter]
confidence: [0-100]%
justification: [brief explanation]
"""
    else:
        format_instruction = """
Answer with EXACTLY this format:
answer: [your answer]
confidence: [0-100]%
justification: [brief explanation]
"""

    system_prompt = f"""You are an expert problem solver. Think carefully and use tools (Python) when helpful.
Give your final answer in the specified format.

{format_instruction}"""

    client = anthropic.Anthropic(base_url=BASE_URL)

    messages = [{"role": "user", "content": question}]

    total_input = 0
    total_output = 0
    tool_calls = 0

    # Tool use loop (max 30 iterations — let model work until it's done)
    for iteration in range(30):
        # Use streaming to avoid 10-min timeout on long thinking requests
        collected_blocks = []
        input_tokens = 0
        output_tokens = 0

        with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_OUTPUT,
            system=system_prompt,
            messages=messages,
            tools=TOOLS,
            thinking={
                "type": "enabled",
                "budget_tokens": THINKING_BUDGET
            }
        ) as stream:
            response = stream.get_final_message()

        total_input += response.usage.input_tokens
        total_output += response.usage.output_tokens

        # Check if model wants to use tools
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b for b in response.content if b.type == "text"]

        if not tool_use_blocks:
            # No more tool calls — extract answer from text
            answer_text = "\n".join(b.text for b in text_blocks)
            return {
                "answer_raw": answer_text,
                "total_input": total_input,
                "total_output": total_output,
                "total_tokens": total_input + total_output,
                "tool_calls": tool_calls,
                "iterations": iteration + 1
            }

        # Process tool calls
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for tb in tool_use_blocks:
            tool_calls += 1
            if tb.name == "python_exec":
                result = run_python(tb.input.get("code", ""))
                print(f"    [tool] python_exec → {len(result)} chars")
            else:
                result = f"Unknown tool: {tb.name}"
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tb.id,
                "content": result
            })

        messages.append({"role": "user", "content": tool_results})

    # Exhausted iterations
    return {
        "answer_raw": "(max tool iterations reached)",
        "total_input": total_input,
        "total_output": total_output,
        "total_tokens": total_input + total_output,
        "tool_calls": tool_calls,
        "iterations": 30
    }


def extract_answer(raw: str) -> str:
    """Extract answer from raw model output."""
    # P7 fix: handle **Answer:** markdown bold + various value types
    m = re.search(r'\*{0,2}answer\*{0,2}[:\s]+\*{0,2}(.+?)(?:\n|$)', raw, re.IGNORECASE)
    if m:
        ans = m.group(1).strip()
        ans = re.sub(r'\*+$', '', ans).strip()
        # If answer is a single letter (MC), extract it
        letter_match = re.match(r'^([A-Z])(?:\s*[\.\)\-:]|\s|$)', ans, re.IGNORECASE)
        if letter_match:
            return letter_match.group(1).upper()
        # If answer starts with a number, extract it
        num_match = re.match(r'^(\d+(?:\.\d+)?)', ans)
        if num_match:
            return num_match.group(1)
        # If "Yes" followed by explanation, extract number if present
        yes_match = re.match(r'^yes\b.*?(\d+)', ans, re.IGNORECASE)
        if yes_match:
            return yes_match.group(1)
        return ans[:100]
    return raw[:100]


def judge(model_answer: str, expected: str, answer_type: str) -> bool:
    """Simple exact match judge."""
    m = model_answer.strip().upper()
    e = expected.strip().upper()
    if answer_type == "multipleChoice":
        return m == e
    else:
        # For exact match, try numeric comparison too
        try:
            return float(m) == float(e)
        except:
            return m == e


def main():
    if len(sys.argv) < 2:
        print("Usage: python hle_baseline.py <seed_file.json> [max_questions]")
        sys.exit(1)

    seed_path = Path(sys.argv[1])
    max_q = int(sys.argv[2]) if len(sys.argv) > 2 else 999

    with open(seed_path) as f:
        seed = json.load(f)

    questions = seed["questions"][:max_q]

    print("=" * 60)
    print(f"  BASELINE TEST — Raw GLM-5 (thinking + tools)")
    print(f"  Model: {MODEL}")
    print(f"  Base URL: {BASE_URL}")
    print(f"  Questions: {len(questions)}")
    print(f"  Seed: {seed_path.name}")
    print("=" * 60)

    # Output directory
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("runs_hle") / f"{ts}_baseline"
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    correct = 0

    for i, q in enumerate(questions, 1):
        qid = q["hle_id"][:20]
        subject = q.get("raw_subject", "?")
        expected = q["answer"]
        answer_type = q.get("answer_type", "exactMatch")

        print(f"\n  [{i}/{len(questions)}] {qid} — {subject} ({answer_type})")
        print(f"  Expected: {expected[:30]}...")

        t0 = time.time()
        try:
            result = ask_model(q["question"], answer_type)
            elapsed = time.time() - t0

            model_answer = extract_answer(result["answer_raw"])
            is_correct = judge(model_answer, expected, answer_type)

            if is_correct:
                correct += 1

            r = {
                "question_id": q["hle_id"],
                "subject": subject,
                "answer_type": answer_type,
                "expected": expected,
                "model_answer": model_answer,
                "answer_raw": result["answer_raw"][:500],
                "correct": is_correct,
                "elapsed_seconds": round(elapsed, 1),
                "total_tokens": result["total_tokens"],
                "tool_calls": result["tool_calls"],
                "iterations": result["iterations"]
            }
            results.append(r)

            status = "CORRECT" if is_correct else "INCORRECT"
            print(f"  Answer:   {model_answer}")
            print(f"  Judge:    {status}")
            print(f"  Time:     {elapsed:.0f}s | Tokens: {result['total_tokens']:,} | Tools: {result['tool_calls']}")

        except Exception as e:
            elapsed = time.time() - t0
            print(f"  ERROR: {e}")
            results.append({
                "question_id": q["hle_id"],
                "subject": subject,
                "expected": expected,
                "error": str(e),
                "elapsed_seconds": round(elapsed, 1)
            })

    # Summary
    completed = [r for r in results if "correct" in r]
    errors = [r for r in results if "error" in r]

    print("\n" + "=" * 60)
    print(f"  BASELINE SUMMARY")
    print(f"  Correct:  {correct}/{len(completed)} ({100*correct/max(1,len(completed)):.0f}%)")
    if errors:
        print(f"  Errors:   {len(errors)}")
    total_tokens = sum(r.get("total_tokens", 0) for r in results)
    total_time = sum(r.get("elapsed_seconds", 0) for r in results)
    print(f"  Tokens:   {total_tokens:,}")
    print(f"  Time:     {total_time:.0f}s")
    print("=" * 60)

    # Save report
    report = {
        "type": "baseline",
        "model": MODEL,
        "timestamp": ts,
        "seed": str(seed_path),
        "accuracy": f"{correct}/{len(completed)}",
        "results": results
    }

    report_path = out_dir / "baseline_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n  Report: {report_path}")


if __name__ == "__main__":
    main()
