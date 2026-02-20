"""
Run P2 (Opus + Regulus v2 audit pipeline) on HLE questions.
Reads ONLY from questions/ (no answers). Outputs to results/.

Uses Regulus v2 AuditOrchestrator:
  Query → [Claude thinking] → Trace → [Auditor] → Answer

Usage:
  python tests/HLE/run_regulus.py --batch batch_001 [--reasoning claude-thinking]
"""

import json
import re
import time
import os
import sys
import asyncio
import argparse
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

from regulus.audit.orchestrator import AuditOrchestrator
from regulus.audit.types import AuditConfig
from regulus.reasoning.factory import get_provider as get_reasoning_provider
from regulus.llm.claude import ClaudeClient


def extract_answer_from_response(answer_text: str, answer_type: str) -> str:
    """Extract a concise answer from Regulus v2 output."""
    text = answer_text.strip()

    # Priority 1: EXACT_ANSWER tag (ToS prompt format)
    m = re.search(r"EXACT_ANSWER:\s*(.+?)(?:\n|$)", text)
    if m:
        answer = m.group(1).strip().rstrip(".")
        if answer_type == "multipleChoice":
            letter = re.search(r"^([A-N])\b", answer)
            if letter:
                return letter.group(1)
        return answer

    # Priority 2: "Exact Answer:" field (HLE format)
    m = re.search(r"Exact Answer:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
    if m:
        answer = m.group(1).strip().rstrip(".")
        if answer_type == "multipleChoice":
            letter = re.search(r"^([A-N])\b", answer)
            if letter:
                return letter.group(1)
        return answer

    # Priority 3: \boxed{} LaTeX pattern
    m = re.search(r"\\boxed\{([^}]+)\}", text)
    if m:
        answer = m.group(1).strip()
        if answer_type == "multipleChoice":
            letter = re.search(r"^([A-N])\b", answer)
            if letter:
                return letter.group(1)
        return answer

    # Priority 4: "answer is/:" patterns
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    if answer_type == "multipleChoice":
        for line in reversed(lines):
            m = re.search(r"(?:answer|Answer)\s*(?:is|:)\s*\**([A-N])", line)
            if m:
                return m.group(1)
            m = re.match(r"^\**([A-N])[\.\)\*]", line)
            if m:
                return m.group(1)
        for line in reversed(lines):
            m = re.search(r"\b([A-N])\b", line)
            if m:
                return m.group(1)

    for line in reversed(lines):
        m = re.search(r"(?:answer|Answer)\s*(?:is|:)\s*(.+)", line)
        if m:
            return m.group(1).strip().rstrip(".")

    # Fallback: last line
    return lines[-1].rstrip(".") if lines else ""


async def run_regulus_batch(batch_name: str, reasoning_model: str = "claude-thinking"):
    base = os.path.dirname(os.path.abspath(__file__))
    q_path = os.path.join(base, "questions", f"{batch_name}.json")
    out_path = os.path.join(base, ".judge_only", f"p2_{batch_name}.json")

    if not os.path.exists(q_path):
        print(f"ERROR: Questions file not found: {q_path}")
        return

    with open(q_path) as f:
        questions = json.load(f)

    # Contamination check
    for q in questions:
        if "answer" in q:
            print("ABORT: Question file contains 'answer' field — contamination!")
            return

    print(f"Running P2 (Regulus v2) on {batch_name} ({len(questions)} questions)")
    print(f"Reasoning: {reasoning_model}")

    # Set up providers
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    reasoning_provider = get_reasoning_provider(
        reasoning_model,
        api_key=anthropic_key,
        budget_tokens=10000,
        use_tos_prompt=True,
    )
    audit_llm = ClaudeClient(api_key=anthropic_key, model="claude-sonnet-4-20250514")
    config = AuditConfig(min_domains=4, weight_threshold=60, max_corrections=2)

    results = []

    for i, q in enumerate(questions, 1):
        num = f"{i:02d}"
        subject = q.get("raw_subject", "?")[:30]
        print(f"  Q{num}: {subject:30s} ...", end="", flush=True)

        t0 = time.time()
        try:
            orchestrator = AuditOrchestrator(
                reasoning_provider=reasoning_provider,
                audit_llm=audit_llm,
                config=config,
            )
            v2_response = await orchestrator.process_query(q["question"])
            elapsed = time.time() - t0

            answer_text = v2_response.answer
            extracted = extract_answer_from_response(answer_text, q["answer_type"])

            audit = v2_response.final_audit
            total_weight = audit.total_weight if audit else 0
            domains_present = sum(1 for d in audit.domains if d.present) if audit else 0
            gates_ok = audit.all_gates_passed if audit else False

            result = {
                "question_id": q["id"],
                "participant": "p2_regulus_v2",
                "answer": extracted,
                "explanation": answer_text,
                "confidence": -1,  # Regulus doesn't output HLE confidence format
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tokens_used": v2_response.input_tokens + v2_response.output_tokens,
                "time_seconds": round(elapsed, 1),
                "model": v2_response.reasoning_model,
                "regulus_v2": {
                    "valid": v2_response.valid,
                    "total_weight": total_weight,
                    "domains_present": domains_present,
                    "gates_passed": gates_ok,
                    "audit_rounds": v2_response.audit_rounds,
                    "corrections": len(v2_response.corrections),
                },
                "contamination_check": {
                    "fresh_session": True,
                    "answer_file_read": False,
                },
            }
        except Exception as e:
            elapsed = time.time() - t0
            result = {
                "question_id": q["id"],
                "participant": "p2_regulus_v2",
                "answer": f"ERROR: {e}",
                "explanation": f"ERROR: {e}",
                "confidence": -1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tokens_used": 0,
                "time_seconds": round(elapsed, 1),
                "model": reasoning_model,
                "regulus_v2": {
                    "valid": False,
                    "total_weight": 0,
                    "domains_present": 0,
                    "gates_passed": False,
                    "audit_rounds": 0,
                    "corrections": 0,
                },
                "contamination_check": {
                    "fresh_session": True,
                    "answer_file_read": False,
                },
            }
            extracted = f"ERROR: {e}"

        results.append(result)

        # Safe print
        safe_answer = str(extracted)[:50].encode('ascii', 'replace').decode('ascii')
        valid = result["regulus_v2"]["valid"]
        w = result["regulus_v2"]["total_weight"]
        print(f" [{elapsed:.1f}s] W={w} valid={valid} answer='{safe_answer}'")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to {out_path}")
    print(f"Total: {len(results)} questions processed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run P2 (Regulus v2) on HLE")
    parser.add_argument("--batch", required=True, help="Batch name (e.g. batch_001)")
    parser.add_argument("--reasoning", default="claude-thinking",
                        help="Reasoning provider (claude-thinking, deepseek, openai-reasoning)")
    args = parser.parse_args()

    asyncio.run(run_regulus_batch(args.batch, args.reasoning))
