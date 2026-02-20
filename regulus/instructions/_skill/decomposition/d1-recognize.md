# D1 — Recognition (DECOMPOSITION Skill Overlay)

> This overlay extends the default D1 instructions for questions classified
> as **decomposition** — multi-step structural breakdown with 3+ dependent steps.

## ADDITIONAL D1 PRIORITIES FOR DECOMPOSITION

### Dependency Graph is Critical
For decomposition questions, the **dependency graph** is the most important D1 output.
Each step depends on prior steps. Missing a dependency = pipeline failure in D4.

- Map EVERY step-to-step dependency explicitly
- Identify the **critical path** (longest dependency chain)
- Flag any steps that can run in parallel vs. must be sequential

### Level 4 (Character) is Mandatory
Decomposition questions ALWAYS require Level 4 depth in D1:
- Level 1-2: What data/info is present (necessary but insufficient)
- Level 3: What properties matter (closer)
- **Level 4: What structural features determine the solution approach**

### ERR Hierarchy for Multi-Step Problems
- **Elements**: Each step's inputs and outputs
- **Roles**: Which elements are intermediate results vs. final answers
- **Rules**: The transformation/computation that connects steps
- **Status**: Track which elements are "blocked" (depend on prior steps)

### Additional Failure Mode: Step Omission
The most dangerous D1 failure for decomposition is **missing a step**.
If step 3 depends on step 2 which depends on step 1, and you miss step 2,
the entire downstream chain collapses.

**Self-check**: Can you trace a complete path from givens to the unknown
through your dependency graph? If any link is missing, D1 is incomplete.

### Output Enhancement
Add to d1_output JSON:
```json
{
  "decomposition_metadata": {
    "total_steps": 5,
    "critical_path_length": 4,
    "parallel_opportunities": ["E2 and E3 can be computed independently"],
    "bottleneck_step": "E4 — requires both E2 and E3 results"
  }
}
```
