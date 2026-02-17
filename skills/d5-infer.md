# D5 — Inference

## FUNCTION
Draw conclusions EARNED by D4's evidence. Nothing more, nothing less.

**Principle of Sufficient Reason (L4):** Every conclusion must have sufficient grounds in the evidence. No ungrounded leaps.

**Grounded in L5 (Order/Direction):** Reasoning flows premises → conclusion, NEVER conclusion → premises. If you "know" the answer before examining evidence, that's L5 reversal — the most dangerous D5 failure.

## INPUT
Read d4_output.json. You receive:
- Comparisons with evidence for/against/gaps
- Computation trace
- Aristotle check results
- MC elimination status
- Status updates and key findings
- Disconfirming evidence

## THE L5 DIRECTION CHECK (mandatory)

Before stating your conclusion, verify:

> **"Did I arrive at this answer FROM the evidence, or did I select evidence FOR this answer?"**

| Direction | Name | Status |
|-----------|------|--------|
| Premises → Conclusion | **Deduction** | ✅ Valid |
| Conclusion → Premises | **Rationalization** | ❌ L5 violation |

**How to detect L5 reversal:** If you can't trace a clear chain Evidence₁ + Evidence₂ + Rule → Conclusion, you may be rationalizing. Write out the chain explicitly.

## L5 STRUCTURAL CONSTRAINTS (cannot be overridden)

D5 draws conclusions from D4 evidence. But some D4 findings are not mere evidence — they are **structural constraints** grounded in the Laws of Logic. These constraints LIMIT what conclusions D5 can draw.

### Identifying structural constraints:

A D4 finding is a structural constraint if:
- It is derived from a RULE with `source: structural_L5` (process ordering)
- It is derived from a RULE with `source: structural_L1` (identity preservation)
- It is flagged as `empirically_dependent: false` AND `derivable: true`

### The override prohibition:

> **D5 may NOT override a structural constraint with an interpretive argument.**
>
> Specifically: if D2 resolved a directional expression using RULE_ORD (L5 ordering),
> D5 cannot reverse that resolution by arguing that "linguistically, the phrase
> could also mean [symmetric interpretation]."
>
> **Why:** L5 is a Law. Linguistic convention is not a Law. When they conflict,
> the Law prevails. A process ordering is a structural fact — it does not become
> symmetric because a natural language phrase could be read symmetrically in
> a different context.

### The D5 escape valve:

D5 CAN challenge a structural constraint, but ONLY by:
1. Showing the constraint itself is WRONG (e.g., the process ordering was misidentified in D1)
2. Showing the constraint does not APPLY (e.g., the question explicitly asks about structural overlap, not provenance)
3. Requesting a RETURN to D1/D2 to re-examine the constraint

D5 CANNOT simply reinterpret the constraint's meaning. That would be an L1 violation (changing the definition of a term mid-reasoning).

### Example of prohibited vs. permitted override:

**PROHIBITED (what happened in Q3):**
> "D2 says provenance → 0, but linguistically 'from 7' just means 'belonging to 7's structure,' so the answer is 1."
> ← This overrides L5 ordering with linguistic reinterpretation. VIOLATION.

**PERMITTED:**
> "D2 says provenance → 0, but D1 misidentified the process ordering. Compound 7 is actually created before compound 10. Return to D1 for correction."
> ← This challenges the CONSTRAINT ITSELF, not its application. VALID (if factually correct).

**PERMITTED:**
> "D2 says provenance → 0, but the question explicitly says 'shared atoms' in a later clause, changing the meaning. Return to D2 for re-clarification."
> ← This adds new evidence that the constraint doesn't apply. VALID (if the text supports it).

## THREE DEGREES OF CERTAINTY

Every conclusion MUST be marked with its certainty type:

| Type | Criterion | Strength | Example |
|------|-----------|----------|---------|
| **Necessary** | Denying it produces contradiction | Deductive proof only | "2+2=4", "All bachelors are unmarried" |
| **Probabilistic** | Denial possible but unlikely given evidence | Most HLE answers | "Based on computation, answer ≈ 1.117" |
| **Evaluative** | Depends on values, perspective, or interpretation | Judgment calls | "Option B is the best interpretation" |

**Do NOT mark as "necessary" unless you have a complete deductive proof.** Most HLE answers are probabilistic.

## EMPIRICAL DEPENDENCY CONFIDENCE CAP

If D4 marked any empirical claim as `empirically_dependent` AND that claim influences the final answer:

| Situation | Confidence Cap |
|-----------|---------------|
| Binary empirical choice (A or B), no data to decide | **60%** |
| Multi-way empirical choice (>2 options), no data | **75%** |
| Empirical claim with partial support (domain convention) | **80%** |
| All empirical claims verified from question text | No cap |

This cap applies AFTER all other confidence adjustments. Self-reported confidence cannot exceed the cap.

**Rationale (L4):** Confidence without sufficient reason is not confidence — it is assertion. When the answer depends on an unverified empirical premise, the conclusion inherits the uncertainty of the premise regardless of how rigorous the downstream reasoning is.

## FOUR HONESTY REQUIREMENTS

| # | Requirement | Check | Violation |
|---|-------------|-------|-----------|
| 1 | **Correspondence** | Does conclusion match the grounds? | Conclusion says more than evidence supports |
| 2 | **Marking** | Is certainty degree explicitly stated? | Presenting probabilistic as necessary |
| 3 | **Withhold** | Does NOT conclude beyond evidence? | Overreach — claiming what wasn't shown |
| 4 | **Accept** | Uncomfortable conclusions NOT rejected without grounds? | Avoidance — earned conclusion evaded because "it can't be right" |

**Requirement 4 is critical for HLE:** If the math says the answer is 4 but "it should be 5", go with the math. Do not reject earned conclusions because they seem unlikely.

## ERR IN D5

D5 is where ERR culminates:

- **Elements** = Premises (the evidence from D1-D4)
- **Roles**: 
  - "Premise" = foundation (must be from D1-D4, not invented here)
  - "Link" = logical connection (inference rule, calculation step)
  - "Conclusion" = result
- **Rules** = Logic used: deductive, inductive, abductive, mathematical
- **Status** = Conclusion's certainty: necessary / probable / evaluative / unjustified
- **Dependencies** = D1-D4 chain → premises. Conclusion depends on ALL prior domains.

**Check:** Is every premise traceable to a D4 finding? If you're using a premise that didn't appear in D4, it's an INJECTED premise — flag it.

## FAILURE MODES

| Failure | Description | Detection |
|---------|-------------|-----------|
| **Non sequitur** | Conclusion doesn't follow from premises | Trace the chain: can you write P1 + P2 → C explicitly? |
| **L5 reversal** | Conclusion predetermined, evidence selected to fit | L5 direction check |
| **Hasty generalization** | Insufficient evidence for strength of conclusion | Check: certainty marking matches evidence strength? |
| **Affirming consequent** | "If A then B; B; therefore A" | Check logical form explicitly |
| **Injected premise** | Using information not from D1-D4 | Check: is every premise traceable? |
| **Equivocation (inherited)** | Term changed meaning between D2 and D5 | Check: meanings stable? (L1) |
| **Avoidance** | Rejecting an earned conclusion because it's uncomfortable | Requirement 4: Accept check |

## DIAGNOSTIC SELF-CHECK

1. Can I write the inference chain explicitly? (P1 + P2 + Rule → Conclusion)
2. Did I arrive at this FROM the evidence? Or did I start with the answer? (L5)
3. Is my certainty marking honest? (necessary only for deductive proofs)
4. Am I adding any premises not from D4? (injected premise check)
5. Am I avoiding a conclusion because it seems unlikely? (Requirement 4)
6. Does my conclusion correspond to what was asked? (answering the right question)

## OUTPUT FORMAT

Write to d5_output.json:

```json
{
  "d5_output": {
    "answer": "The specific answer (value, letter, expression, etc.)",
    "conclusion_statement": "Full sentence conclusion",
    "inference_chain": [
      {"step": 1, "from": "D4 finding: ...", "via": "rule/calculation", "to": "intermediate conclusion"},
      {"step": 2, "from": "intermediate + ...", "via": "...", "to": "final conclusion"}
    ],
    "certainty_type": "necessary|probabilistic|evaluative",
    "certainty_level": 85,
    "l5_direction_check": {
      "passed": true,
      "direction": "premises→conclusion",
      "traceable": "All premises from D4: [list which findings]"
    },
    "four_requirements": {
      "correspondence": "Conclusion matches grounds: [explain]",
      "marking": "Certainty level justified: [explain]",
      "withhold": "Conclusion does NOT claim: [what it doesn't claim]",
      "accept": "No evaded conclusions: [or describe what was uncomfortable but accepted]"
    },
    "injected_premises": "none|[list any premises not from D1-D4]",
    "failure_check": {
      "non_sequitur": "none|risk:[details]",
      "l5_reversal": "none|risk:[details]",
      "hasty_generalization": "none|risk:[details]",
      "avoidance": "none|risk:[details]"
    }
  }
}
```

Update state.json: D5 → "complete".

## RULES FOR D5

1. ALWAYS run the L5 direction check before stating conclusion
2. Mark certainty type honestly — "necessary" only for complete proofs
3. Write inference chain explicitly — every step traceable
4. Check all four honesty requirements
5. Do NOT inject premises not from D1-D4
6. Do NOT avoid uncomfortable conclusions (Requirement 4)
7. State the answer clearly in the exact format expected (value, letter, etc.)
8. If uncertain: state best answer + honest certainty level, not "I don't know"
9. Do NOT reflect on limitations (that's D6)
