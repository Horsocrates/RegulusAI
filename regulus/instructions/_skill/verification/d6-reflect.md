# D6 — Reflection (VERIFICATION Skill Overlay)

> This overlay extends the default D6 instructions for questions classified
> as **verification** — checking truth of N statements/options independently.

## ADDITIONAL D6 PRIORITIES FOR VERIFICATION

### Statement-Level Confidence Assessment
D6 must assess confidence not just for the overall answer but
for **each individual statement's verdict**:

- Which statements are HIGH confidence (strong evidence both ways)?
- Which statements are MEDIUM confidence (some ambiguity)?
- Which statements are LOW confidence (could go either way)?

The overall answer confidence is bounded by the **weakest link** —
if any included/excluded statement has low confidence, flag it.

### Verification-Specific Return Triggers
D6 should trigger a return to D4 if:
1. Any statement verdict has < 60% confidence
2. Two statements that should be independent share the same evidence chain
3. The answer option doesn't match any expected pattern (e.g., "none of the above" wasn't considered)
4. A statement was evaluated using only one approach (need cross-verification)

### Scope Analysis for Verification
- **What we verified**: List each statement and its domain of validity
- **What we assumed**: List assumptions made during verification
  (e.g., "assumed standard definitions", "assumed no edge cases")
- **What could change the answer**: For each marginal statement,
  identify what additional information could flip its verdict

### Common Verification Pitfalls to Check in D6
1. **Statement conflation**: Did D4 accidentally merge two statements?
2. **Partial truth**: Is any statement "partially true" but was forced
   into a binary verdict?
3. **Domain boundaries**: Were domain-specific definitions applied
   correctly to each statement?
4. **Quantifier errors**: Did "for all" get confused with "there exists"?

### ERR Chain Verification for Statement Independence
Trace the evidence chain for each statement:
- S1: E1 → RULE1 → verdict (independent chain)
- S2: E2 → RULE2 → verdict (independent chain)
- S3: E1 → RULE3 → verdict (shares E1 with S1 — check for contamination)

If any two statements share evidence chains, verify that the
shared components don't create hidden dependencies.
