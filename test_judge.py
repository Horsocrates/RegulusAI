#!/usr/bin/env python3
"""Quick test of the improved judge prompt."""

import anthropic
import functools
print = functools.partial(print, flush=True)

JUDGE_MODEL = "claude-sonnet-4-20250514"

def judge_answer(model_answer: str, expected_answer: str) -> bool:
    client = anthropic.Anthropic()
    judge_prompt = f"""You are a STRICT judge comparing a model's answer to the expected answer.

Expected answer: {expected_answer}
Model's answer: {model_answer}

RULES:
1. Extract the CORE answer from the model's response (ignore explanations, confidence scores, justifications)
2. The core answer must be EXACTLY equivalent to the expected answer
3. Minor formatting differences are OK (e.g., subscripts, LaTeX vs plain text)
4. Mathematical equivalence is OK (e.g., 1/2 = 0.5)
5. BUT different values are NEVER equivalent:
   - "D2" and "S4" are DIFFERENT point groups → incorrect
   - "2, 1, 1" and "2, 1, 0" are DIFFERENT → incorrect
   - "5.57" and "5.58" are DIFFERENT → incorrect
6. Chemical formula equivalence is OK (FeCl₂ = FeCl2)
7. When in doubt, answer "incorrect"

Respond with ONLY "correct" or "incorrect"."""

    response = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=100,
        messages=[{"role": "user", "content": judge_prompt}]
    )
    judge_text = response.content[0].text.strip().lower()
    if "incorrect" in judge_text:
        result = False
    else:
        result = "correct" in judge_text
    return result, judge_text

# Test cases from our run
tests = [
    ("D₂", "S4", False, "Different point groups"),
    ("Fe + 2FeCl₃ = 3FeCl₂", "Fe + 2FeCl3 = 3FeCl2", True, "Same equation, formatting"),
    ("2, 1, 1", "2, 1, 0", False, "Different values"),
    ("S₄", "S4", True, "Same, subscript diff"),
    ("thiocyanatobenzene", "thiocyanatobenzene", True, "Exact match"),
    ("Methylcyclopropane", "Methylcyclopropane", True, "Exact match"),
]

print("Testing improved judge prompt:\n")
for model_ans, expected, should_be, desc in tests:
    result, raw = judge_answer(model_ans, expected)
    status = "PASS" if result == should_be else "FAIL"
    print(f"  [{status}] {desc}")
    print(f"    Model: {model_ans} | Expected: {expected}")
    print(f"    Judge: {raw} | Should be: {'correct' if should_be else 'incorrect'}")
    print()
