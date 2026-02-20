"""
Run raw Opus baseline (P1) on HLE questions.
Reads ONLY from questions/ (no answers). Outputs to results/.
Uses official HLE prompt format.

Usage:
  python tests/HLE/run_baseline.py --batch batch_001 [--model claude-opus-4-6]
"""

import json
import re
import time
import os
import argparse
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

import anthropic

# Official HLE system prompt
SYSTEM_PROMPT = (
    "Your response should be in the following format:\n"
    "Explanation: {your explanation for your final answer}\n"
    "Exact Answer: {your succinct, final answer}\n"
    "Confidence: {your confidence score between 0% and 100% for your answer}"
)


def extract_answer(full_response: str, answer_type: str) -> str:
    """Extract the actual answer from a response following HLE format."""
    text = full_response.strip()

    # Try to find "Exact Answer:" field
    m = re.search(r"Exact Answer:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
    if m:
        answer = m.group(1).strip().rstrip(".")
        # For MC, extract just the letter
        if answer_type == "multipleChoice":
            letter = re.search(r"^([A-N])\b", answer)
            if letter:
                return letter.group(1)
        return answer

    # Fallback: look for answer patterns
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    if answer_type == "multipleChoice":
        for line in reversed(lines):
            m = re.search(r"(?:answer|Answer)\s*(?:is|:)\s*([A-N])", line)
            if m:
                return m.group(1)
            m = re.match(r"^([A-N])\.?$", line)
            if m:
                return m.group(1)
        for line in reversed(lines):
            m = re.search(r"\b([A-N])\b", line)
            if m:
                return m.group(1)
        return lines[-1] if lines else ""
    else:
        for line in reversed(lines):
            m = re.search(r"(?:answer|Answer)\s*(?:is|:)\s*(.+)", line)
            if m:
                return m.group(1).strip().rstrip(".")
        return lines[-1].rstrip(".") if lines else ""


def extract_confidence(full_response: str) -> int:
    """Extract confidence from HLE format response."""
    m = re.search(r"Confidence:\s*(\d+)%", full_response)
    if m:
        return int(m.group(1))
    return -1


def run_baseline(batch_name: str, model: str = "claude-opus-4-6"):
    base = os.path.dirname(os.path.abspath(__file__))
    q_path = os.path.join(base, "questions", f"{batch_name}.json")
    out_path = os.path.join(base, ".judge_only", f"p1_{batch_name}.json")

    if not os.path.exists(q_path):
        print(f"ERROR: Questions file not found: {q_path}")
        return

    with open(q_path) as f:
        questions = json.load(f)

    # Verify no answer contamination
    for q in questions:
        if "answer" in q:
            print("ABORT: Question file contains 'answer' field — contamination!")
            return

    print(f"Running P1 baseline on {batch_name} ({len(questions)} questions)")
    print(f"Model: {model}")

    client = anthropic.Anthropic()
    results = []

    for i, q in enumerate(questions, 1):
        num = f"{i:02d}"
        print(f"  Q{num}: {q.get('raw_subject', '?')[:30]:30s} ...", end="", flush=True)

        t0 = time.time()
        try:
            response = client.messages.create(
                model=model,
                max_tokens=8192,
                temperature=0,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": q["question"]}],
            )
            elapsed = time.time() - t0
            answer_text = response.content[0].text.strip()
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
        except Exception as e:
            elapsed = time.time() - t0
            answer_text = f"ERROR: {e}"
            input_tokens = 0
            output_tokens = 0

        extracted = extract_answer(answer_text, q["answer_type"])
        confidence = extract_confidence(answer_text)

        result = {
            "question_id": q["id"],
            "participant": "p1_raw_opus",
            "answer": extracted,
            "explanation": answer_text,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tokens_used": input_tokens + output_tokens,
            "time_seconds": round(elapsed, 1),
            "model": model,
            "contamination_check": {
                "fresh_session": True,
                "answer_file_read": False,
            },
        }
        results.append(result)

        # Safe print (handle non-ASCII)
        safe_answer = extracted[:50].encode('ascii', 'replace').decode('ascii')
        print(f" [{elapsed:.1f}s] answer='{safe_answer}'")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to {out_path}")
    print(f"Total: {len(results)} questions processed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run P1 (raw Opus) baseline")
    parser.add_argument("--batch", required=True, help="Batch name (e.g. batch_001)")
    parser.add_argument("--model", default="claude-opus-4-6", help="Model to use")
    args = parser.parse_args()

    run_baseline(args.batch, args.model)
