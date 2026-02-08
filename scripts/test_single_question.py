"""Run a single question through JUST the auditor (no reasoning model) to verify D3 behavior."""
import asyncio
import json
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

from regulus.audit.auditor import Auditor
from regulus.llm.openai import OpenAIClient
from regulus.reasoning.provider import TraceFormat


async def test_audit(question: str, trace: str, answer: str):
    audit_llm = OpenAIClient(api_key=os.environ["OPENAI_API_KEY"], model="gpt-4o-mini")
    auditor = Auditor(llm_client=audit_llm)

    result = await auditor.audit(
        trace=trace,
        answer=answer,
        query=question,
        trace_format=TraceFormat.FULL_COT,
    )

    audit = result.to_dict()
    print(f"Total weight: {audit['total_weight']}")
    print(f"Gates passed: {audit['all_gates_passed']}")
    print(f"Violations: {audit.get('violation_patterns', [])}")
    print()

    for d in audit["domains"]:
        gate_str = "PASS" if d["gate_passed"] else "FAIL"
        summary = d.get("segment_summary", "")[:120]
        print(f"  {d['domain']} W={d['weight']:>3} gate={gate_str} | {summary}")

        signals = []
        if d.get("d1_depth") is not None:
            signals.append(f"d1_depth={d['d1_depth']}")
        if d.get("d2_depth") is not None:
            signals.append(f"d2_depth={d['d2_depth']}")
        if "d3_objectivity_pass" in d:
            v = d["d3_objectivity_pass"]
            label = "null" if v is None else str(v)
            signals.append(f"obj={label}")
        if d.get("d4_aristotle_ok") is not None:
            signals.append(f"arist={'OK' if d['d4_aristotle_ok'] else 'FAIL'}")
        if d.get("d5_certainty_type"):
            signals.append(f"cert={d['d5_certainty_type']}")
        if d.get("d6_genuine") is not None:
            signals.append(f"genuine={'OK' if d['d6_genuine'] else 'FAIL'}")
        if signals:
            print(f"         {' | '.join(signals)}")

        if d.get("issues"):
            for iss in d["issues"]:
                print(f"         ISSUE: {iss}")


if __name__ == "__main__":
    # Bracket counting task with a plausible trace
    question = "Count the maximum nesting depth of ( [ { } ] ( ) )"
    trace = """
    D1 Recognition: The input is a bracket sequence with three types: (), [], {}.
    I need to find the maximum nesting depth. There are 8 characters total.
    The sequence is: ( [ { } ] ( ) )

    D2 Clarification: Maximum nesting depth means the maximum number of simultaneously
    open brackets at any position. An open bracket increases depth, a close bracket decreases.

    D3 Framework: I will use sequential bracket parsing - process left to right,
    track a depth counter, record the maximum.

    D4 Comparison: Processing each character:
    Position 0: ( -> depth=1, max=1
    Position 1: [ -> depth=2, max=2
    Position 2: { -> depth=3, max=3
    Position 3: } -> depth=2
    Position 4: ] -> depth=1
    Position 5: ( -> depth=2
    Position 6: ) -> depth=1
    Position 7: ) -> depth=0

    D5 Inference: The maximum nesting depth is 3, reached at position 2.
    This is a deterministic result from sequential processing.

    D6 Reflection: The method assumes all brackets are properly matched.
    If the sequence contained unmatched brackets, the counting approach
    would still work but the depth at the end wouldn't return to 0.
    """
    answer = "3"

    asyncio.run(test_audit(question, trace, answer))
