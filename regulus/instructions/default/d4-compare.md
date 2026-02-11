# D4 — Comparison

## FUNCTION
Systematically apply D3's criteria to D1/D2's components. Collect evidence. This is where the actual analytical work happens — computation, derivation, elimination, verification.

**Principle of Systematicity:** Apply the framework to ALL elements without exception. Selective comparison = biased comparison.

**Grounded in L1 (Presence):** Compare what IS present, not what is absent. Evidence must come from the problem, not from what you wish were there.

## INPUT
Read d2_output.json (clarified elements, rules, status) and d3_output.json (framework, criteria, approach plan).

## ARISTOTLE'S THREE RULES (mandatory verification)

Every comparison must satisfy:

| Rule | Question | Violation Example |
|------|----------|-------------------|
| **Same relation** | Are we comparing in the same respect? | Comparing price of A to quality of B |
| **Same criterion** | One standard applied to all? | Stricter standard for one option |
| **Same time/state** | Comparable conditions? | Comparing peak performance of A to average of B |

If any rule is violated, the comparison is INVALID. Flag it and fix before proceeding.

## ERR IN D4

D4 is where ERR structure gets **applied**:

- **Elements** (from D1/D2): the items being compared
- **Roles** (from D1/D2): determines what KIND of comparison (given vs unknown, constraint vs context)
- **Rules** (from D1/D2 + D3 criteria): the laws and criteria governing comparison
- **Status updates**: comparison changes status from "uncommitted" to "compared on criterion X" or "incomparable"
- **Dependencies**: comparison may reveal new dependencies between elements

Track status changes explicitly: what was unknown BEFORE D4, what becomes known/constrained AFTER.

## COMPUTATION AND DERIVATION

For HLE questions, D4 is typically the LONGEST domain. Here is where you:

- **Compute**: Execute calculations step by step. Show ALL intermediate steps. No skipping.
- **Derive**: Build proof chains explicitly. State each inference rule used.
- **Eliminate**: For MC questions, test each option against criteria. Don't just confirm the "obvious" answer.
- **Verify**: Cross-check results using alternative methods when possible.

**ALWAYS show computation trace for quantitative questions.** "If applicable" = ALWAYS for computation, proof, and estimation tasks.

**Use tools:** If Python/computation would help verify, say so explicitly. Numerical verification catches algebraic errors.

## FAILURE MODES

| Failure | Description | Detection |
|---------|-------------|-----------|
| **Selective comparison** | Only comparing evidence that supports preferred answer | Check: did you apply ALL criteria to ALL elements? |
| **False equivalence** | Treating different things as same | Check: Aristotle's same-relation rule |
| **Scale distortion** | Comparing at wrong scale (absolute vs relative) | Check: are units/scales consistent? |
| **Confirmation-driven** | Seeking evidence FOR rather than testing AGAINST | Check: did you look for DISconfirming evidence? |
| **False analogy** | Analogy breaks down at critical point | Check: where does the analogy FAIL? |
| **Simpson's paradox** | Aggregate trend reverses in subgroups | Check: does conclusion hold when you split the data? |
| **Premature termination** | Stopping comparison when "good enough" | Check: are there untested criteria or unexamined elements? |

## DIAGNOSTIC SELF-CHECK

1. Have I applied EVERY criterion from D3 to EVERY relevant element?
2. Have I looked for evidence AGAINST my emerging conclusion, not just FOR?
3. Are my comparisons using the same standard throughout? (Aristotle)
4. Where are the GAPS — what information would I need but don't have?
5. Is my computation trace complete — could someone verify each step?
6. Have I considered extreme/edge cases?

## META-OBSERVER CHECKLIST

```
SUFFICIENT?
  ├─ Every criterion applied to every relevant element?
  ├─ Computation/derivation shown step by step?
  ├─ Supporting AND contradicting evidence collected?
  └─ Gaps identified?

CORRECT?
  ├─ Aristotle's 3 rules satisfied? (same relation, criterion, state)
  ├─ No selective comparison? (ALL elements, not just convenient ones)
  ├─ No false equivalence?
  └─ Scale/units consistent?

COMPLETE?
  ├─ All MC options tested (if applicable)?
  ├─ Cross-verification attempted?
  ├─ Edge cases checked?
  └─ Status of each element updated?
```

## OUTPUT FORMAT

Write to d4_output.json:

```json
{
  "d4_output": {
    "comparisons": [
      {
        "criterion": "K1: [name from D3]",
        "elements_compared": ["E1", "E2"],
        "analysis": "Detailed analysis applying this criterion",
        "evidence_for": "Evidence supporting...",
        "evidence_against": "Evidence contradicting...",
        "gaps": "What's missing"
      }
    ],
    "computation_trace": "Step-by-step computation (ALWAYS for quantitative tasks):\nStep 1: ...\nStep 2: ...\n...",
    "aristotle_check": {
      "same_relation": true,
      "same_criterion": true,
      "same_state": true,
      "violations": "none|[describe violation]"
    },
    "mc_elimination": [
      {"option": "A", "status": "eliminated|viable|confirmed", "reason": "..."},
      {"option": "B", "status": "...", "reason": "..."}
    ],
    "status_updates": [
      {"element_id": "E1", "status_before": "unknown", "status_after": "constrained", "via": "K1 comparison"}
    ],
    "key_findings": ["Most important finding 1", "..."],
    "disconfirming_evidence": "What evidence AGAINST the emerging conclusion exists?",
    "cross_verification": "Alternative method used to check result (or 'not applicable')",
    "failure_check": {
      "selective_comparison": "none|risk:[details]",
      "false_equivalence": "none|risk:[details]",
      "confirmation_driven": "none|risk:[details]"
    }
  }
}
```

Update state.json: D4 → "complete".

## RULES FOR D4

1. Apply EVERY D3 criterion to EVERY relevant element — no exceptions
2. Show ALL computation steps — no skipping
3. Look for DISconfirming evidence, not just confirming
4. Verify Aristotle's 3 rules on every comparison
5. For MC: test ALL options, don't just confirm the obvious one
6. Use cross-verification when possible (alternative method, numerical check)
7. Track status changes explicitly
8. Flag gaps honestly — what would you need but don't have?
9. Do NOT draw final conclusions (that's D5)
10. Do NOT reflect on limits (that's D6)
