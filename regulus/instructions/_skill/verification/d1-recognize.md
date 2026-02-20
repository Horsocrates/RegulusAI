# D1 — Recognition (VERIFICATION Skill Overlay)

> This overlay extends the default D1 instructions for questions classified
> as **verification** — checking truth of N statements/options independently.

## ADDITIONAL D1 PRIORITIES FOR VERIFICATION

### Statement Independence is Critical
For verification questions, D1 must identify each statement/claim
as a **separate, independently testable element**.

- Tag each statement: `[S1]`, `[S2]`, `[S3]`, etc.
- Each statement gets its own Role (claim-to-verify)
- Statements may share Elements but have independent truth values
- Do NOT assume statements are related unless explicitly linked

### ERR for Verification
- **Elements**: The entities/values referenced across all statements
- **Roles**: Each statement is a `[R:claim]` that needs independent verification
- **Rules**: The domain laws/definitions that determine each statement's truth
- **Status**: Each statement starts as `[unverified]` — NOT true/false yet

### Key Challenge: Hidden Dependencies Between Statements
Some verification questions contain statements that LOOK independent
but share hidden premises. D1 must flag:
- Shared elements between statements (same variable, same entity)
- Statements that contradict each other (at most one can be true)
- Statements that are logically entailed by others

### Level 3+ Depth for Each Statement
Each statement needs its own depth assessment:
- Level 1: What does the statement literally say?
- Level 2: What domain concepts does it reference?
- **Level 3: What conditions must hold for it to be true/false?**
- Level 4: What edge cases or exceptions could apply?

### Output Enhancement
Add to d1_output JSON:
```json
{
  "verification_metadata": {
    "total_statements": 6,
    "statement_elements": {
      "S1": ["E1", "E3"],
      "S2": ["E2", "E4"],
      "S3": ["E1", "E2"]
    },
    "shared_elements": ["E1 appears in S1 and S3"],
    "potential_contradictions": ["S2 and S5 cannot both be true if..."]
  }
}
```
