# D4 — Comparison (DECOMPOSITION Skill Overlay)

> This overlay extends the default D4 instructions for questions classified
> as **decomposition** — multi-step structural breakdown with 3+ dependent steps.

## ADDITIONAL D4 PRIORITIES FOR DECOMPOSITION

### Execute Steps in Dependency Order
D4 for decomposition is where each step is **actually computed**.
Follow D1's dependency graph strictly:

1. Compute step 1 → verify output
2. Feed step 1 output into step 2 → compute → verify
3. Continue through the entire chain

**NEVER skip ahead.** Each step must be completed and verified before
its dependents can start.

### Error Propagation Check
After each step, check:
- Does this intermediate result make sense? (sanity check)
- Is the magnitude/type consistent with expectations?
- If this step is wrong, which downstream steps are affected?

Flag any step where you are uncertain — this is where D4 most often
fails in decomposition questions.

### Parallel Steps
If D1 identified parallel opportunities (steps that don't depend on
each other), compute them independently and then merge results
at the convergence point.

### Cross-Verification for Decomposition
After completing all steps, perform a **global consistency check**:
- Does the final result satisfy all constraints from D1?
- Can you work backward from the answer through each step?
- Are intermediate results internally consistent?

### Computation Trace Format
For decomposition, the computation trace must show:
```
Step 1 (E1→E2): [detailed computation]
  → Result: [value/expression]
  → Sanity check: [pass/flag]

Step 2 (E2→E3): [detailed computation]
  → Input from Step 1: [value]
  → Result: [value/expression]
  → Sanity check: [pass/flag]

[...continue for all steps...]

Global consistency: [pass/flag]
```

### Additional Failure Mode: Accumulating Errors
In multi-step decomposition, small errors in early steps can
compound into large errors in later steps. After the final step,
estimate the error sensitivity: "If step 2's result were off by X%,
how would the final answer change?"
