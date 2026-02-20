# D3 — Framework Selection (DECOMPOSITION Skill Overlay)

> This overlay extends the default D3 instructions for questions classified
> as **decomposition** — multi-step structural breakdown with 3+ dependent steps.

## ADDITIONAL D3 PRIORITIES FOR DECOMPOSITION

### Framework Must Match Step Structure
The D3 framework for decomposition questions must explicitly account for
the multi-step nature revealed by D1/D2:

1. **Identify the solution strategy**: Which mathematical/logical technique
   applies to each step in the dependency chain?
2. **Define criteria per step**: Each step needs its own evaluation criteria,
   not just one global criterion.
3. **Specify step ordering**: The framework must respect D1's dependency graph.

### Dual Criterion for Step Transitions
At each step boundary, verify:
- **Completion criterion**: Is the current step's output well-defined?
- **Readiness criterion**: Does the next step have all required inputs?

### Framework Selection Bias to Watch
For decomposition, the common bias is choosing a framework that handles
the FIRST step well but ignores later steps. Ensure the framework
covers the **entire dependency chain**, especially the bottleneck step.

### Output Enhancement
Add to d3_output JSON:
```json
{
  "step_frameworks": [
    {"step": "E1→E2", "method": "...", "criterion": "K1"},
    {"step": "E2+E3→E4", "method": "...", "criterion": "K2"}
  ],
  "transition_criteria": [
    {"from": "step_1", "to": "step_2", "ready_when": "..."}
  ]
}
```
