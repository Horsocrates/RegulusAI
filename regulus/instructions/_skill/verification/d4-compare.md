# D4 — Comparison (VERIFICATION Skill Overlay)

> This overlay extends the default D4 instructions for questions classified
> as **verification** — checking truth of N statements/options independently.

## ADDITIONAL D4 PRIORITIES FOR VERIFICATION

### Test Each Statement Independently
The core D4 task for verification is to evaluate each statement
against the established criteria and domain rules:

1. Take statement S1 → apply relevant rules → verdict (true/false/uncertain)
2. Take statement S2 → apply relevant rules → verdict
3. Continue for ALL statements — do NOT stop early

**CRITICAL**: Do not let the verdict of one statement influence
your evaluation of another, unless D1 flagged an explicit logical
dependency between them.

### Disconfirmation is the Primary Tool
For verification, the default approach should be **trying to disprove**
each statement rather than confirm it:
- For "true" candidates: look for counterexamples
- For "false" candidates: try to construct a proof of truth
- Flip your initial intuition and test the opposite

### Aristotle's Rules Applied to Verification
- **Same relation**: Each statement must be evaluated in the same domain context
- **Same criterion**: Apply the same standard of evidence to all statements
- **Same state**: Don't compare a statement under ideal conditions to another under edge cases

### Evidence Table (Required for Verification)
```
| Statement | Evidence FOR | Evidence AGAINST | Verdict | Confidence |
|-----------|-------------|-----------------|---------|------------|
| S1        | ...         | ...             | TRUE    | HIGH       |
| S2        | ...         | ...             | FALSE   | HIGH       |
| S3        | ...         | ...             | TRUE    | MEDIUM     |
```

### Cross-Statement Consistency Check
After evaluating all statements individually:
1. Are the individual verdicts mutually consistent?
2. If the question asks "which statements are true", does your
   combination make sense as a whole?
3. Check for the **common trap**: a statement that LOOKS true
   in isolation but contradicts another verified statement.

### MC Elimination for Verification Questions
If the question provides answer options (e.g., "I, III, and VI"):
- First: evaluate each roman-numeral statement independently
- Then: check which answer option matches your verdict pattern
- Finally: verify that your selected option is the ONLY consistent one

### Additional Failure Mode: Anchoring Bias
The most common D4 failure in verification is **anchoring on the first
statement evaluated**. If S1 is true, there's a bias toward expecting
S2 to also be true. Guard against this by randomizing evaluation order
or explicitly checking your confidence calibration.
