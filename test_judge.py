#!/usr/bin/env python3
"""
Test judge_answer fix against known P0 failure cases.
Run: python test_judge.py
Does NOT require API key for Stage 1/2/2.5 tests (no LLM calls).
"""

import sys
sys.path.insert(0, '.')

from hle_pilot import judge_answer, normalize_answer, extract_core_answer

# ─── TEST CASES ──────────────────────────────────────────────────────

test_cases = [
    # === P0 BUG CASES (previously marked correct, should be incorrect) ===
    {
        "name": "P0-1: S₄ vs D₂ (point groups)",
        "model": "D₂",
        "expected": "S₄",
        "type": "exactMatch",
        "want": False,
    },
    {
        "name": "P0-2: 2,1,1 vs 2,1,0 (atom tracking)",
        "model": "2, 1, 1",
        "expected": "2, 1, 0",
        "type": "exactMatch",
        "want": False,
    },
    {
        "name": "P0-3: D2 vs S4 (plain text variant)",
        "model": "D2",
        "expected": "S4",
        "type": "exactMatch",
        "want": False,
    },
    {
        "name": "P0-4: 5.57 vs 5.58 (close numbers)",
        "model": "5.57",
        "expected": "5.58",
        "type": "exactMatch",
        "want": False,
    },

    # === TRUE POSITIVES (should be correct) ===
    {
        "name": "TP-1: FeCl₂ = FeCl2 (formatting)",
        "model": "FeCl₂",
        "expected": "FeCl2",
        "type": "exactMatch",
        "want": True,
    },
    {
        "name": "TP-2: S₄ = S4 (subscript normalization)",
        "model": "S₄",
        "expected": "S4",
        "type": "exactMatch",
        "want": True,
    },
    {
        "name": "TP-3: Exact string match",
        "model": "2, 1, 0",
        "expected": "2, 1, 0",
        "type": "exactMatch",
        "want": True,
    },
    {
        "name": "TP-4: 0.5 = 1/2 (numeric equivalence)",
        "model": "0.5",
        "expected": "1/2",
        "type": "exactMatch",
        "want": True,
    },
    {
        "name": "TP-5: Answer with wrapper text",
        "model": "The answer is S4",
        "expected": "S4",
        "type": "exactMatch",
        "want": True,
    },
    {
        "name": "TP-6: LaTeX dollar signs",
        "model": "$42$",
        "expected": "42",
        "type": "exactMatch",
        "want": True,
    },
    {
        "name": "TP-7: Integer as float",
        "model": "42.0",
        "expected": "42",
        "type": "exactMatch",
        "want": True,
    },

    # === TRUE NEGATIVES (should be incorrect) ===
    {
        "name": "TN-1: Empty answer",
        "model": "",
        "expected": "42",
        "type": "exactMatch",
        "want": False,
    },
    {
        "name": "TN-2: Completely different",
        "model": "glucose",
        "expected": "fructose",
        "type": "exactMatch",
        "want": False,
    },
    {
        "name": "TN-3: 42 vs 43 (off by one)",
        "model": "42",
        "expected": "43",
        "type": "exactMatch",
        "want": False,
    },
    {
        "name": "TN-4: Close but different numbers",
        "model": "3.14159",
        "expected": "3.14160",
        "type": "exactMatch",
        "want": False,
    },

    # === MULTIPLE CHOICE ===
    {
        "name": "MC-1: Correct letter",
        "model": "The answer is B",
        "expected": "B",
        "type": "multipleChoice",
        "want": True,
    },
    {
        "name": "MC-2: Wrong letter",
        "model": "I think A",
        "expected": "C",
        "type": "multipleChoice",
        "want": False,
    },

    # === EDGE CASES ===
    {
        "name": "Edge-1: Answer in XML tag",
        "model": "<final_answer>S4</final_answer>\nThis is because...",
        "expected": "S4",
        "type": "exactMatch",
        "want": True,
    },
    {
        "name": "Edge-2: Comma-separated with different spacing",
        "model": "2,1,0",
        "expected": "2, 1, 0",
        "type": "exactMatch",
        "want": True,
    },
    {
        "name": "Edge-3: Negative number",
        "model": "-3",
        "expected": "-3",
        "type": "exactMatch",
        "want": True,
    },
    {
        "name": "Edge-4: Large integer",
        "model": "1000000",
        "expected": "1000000",
        "type": "exactMatch",
        "want": True,
    },
]


# ─── RUN TESTS ───────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  JUDGE FIX VERIFICATION")
    print("=" * 60)

    passed = 0
    failed = 0
    errors = []

    for tc in test_cases:
        print(f"\n  Testing: {tc['name']}")
        print(f"    Model:    '{tc['model'][:50]}'")
        print(f"    Expected: '{tc['expected'][:50]}'")
        print(f"    Want:     {'correct' if tc['want'] else 'incorrect'}")

        try:
            got = judge_answer(tc['model'], tc['expected'], tc['type'])
            status = "PASS" if got == tc['want'] else "FAIL"

            if status == "PASS":
                passed += 1
                print(f"    → {status} ✅")
            else:
                failed += 1
                errors.append(tc['name'])
                print(f"    → {status} ❌ (got {'correct' if got else 'incorrect'}, want {'correct' if tc['want'] else 'incorrect'})")

        except Exception as e:
            # If we get an API error on Stage 3 tests, that's expected without API key
            if "ANTHROPIC_API_KEY" in str(e) or "auth" in str(e).lower():
                print(f"    → SKIP (no API key for Stage 3 LLM judge)")
            else:
                failed += 1
                errors.append(tc['name'])
                print(f"    → ERROR: {e}")

    print(f"\n{'=' * 60}")
    print(f"  Results: {passed} passed, {failed} failed")
    if errors:
        print(f"  Failed tests:")
        for e in errors:
            print(f"    - {e}")
    else:
        print(f"  All tests passed! ✅")
    print(f"{'=' * 60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
