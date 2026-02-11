# D2 — Clarification

## FUNCTION
Understand what was recognized. Transform D1's components from NOTICED to DEFINED. Fill in MEANING with sufficient depth for the task.

**Principle of Questioning:** Clarification has no natural stopping point — stop is determined by sufficiency for the purpose of reasoning (L4 Sufficient Reason).

**Grounded in L1 (Identity):** A term must preserve its meaning throughout reasoning. If "X" means one thing at the start and another at the end — L1 violated.

## INPUT
Read d1_output.json. You receive:
- Elements (E1, E2...) with levels (data/info/quality/character)
- Roles (given/unknown/constraint/context)
- Rules (stated/implied/domain_knowledge)
- Status and Dependencies
- Key challenge and task type

Your job: define every element, verify every rule, and clarify every ambiguity — WITHOUT changing the ERR structure. You EXTEND it, not replace it.

## DEPTH LEVELS

Calibrate depth to the task. HLE questions typically require Level 3-4.

| Level | Name | What You Know | Example (star) | Example (justice) |
|-------|------|---------------|----------------|-------------------|
| 1 | **Nominal** | Can point to examples. Recognize but can't explain WHY | "That bright dot" | "When things are fair" |
| 2 | **Dictionary** | Can define. Know what distinguishes X from Y | "Self-luminous celestial body" (≠ planet) | "Giving each their due" (≠ mercy) |
| 3 | **Functional** | Understand the mechanism. Can predict and explain | "H→He fusion; color = temperature" | "Procedural vs distributive; Rawls' veil" |
| 4 | **Essential** | Grasp the nature at the level of PRINCIPLE | "Not a thing but a PROCESS: equilibrium of gravity vs nuclear pressure" (→ P4) | "Formal structure of reciprocity under impartiality constraint" |

**Rule:** State the depth level achieved for each component. If depth < 3 for an HLE question, flag it.

## CLARIFICATION TOOLS

Select the right tool for each component:

| Tool | How It Works | Best For |
|------|-------------|----------|
| **Genus + differentia** (Aristotle) | "X = genus + distinguishing feature" | Clear categorical concepts |
| **Examples and counterexamples** | Delineate boundaries of a concept | Fuzzy, ethical concepts |
| **Extreme cases** | Does definition work at boundaries? (Gettier-type) | Exposing hidden assumptions |
| **Usage analysis** (Wittgenstein) | Meaning = use in context. Collect cases, find pattern | Abstract concepts |
| **Operational definition** | How to verify/test? | Scientific, computational tasks |
| **Analysis of the opposite** | What is NOT-X? | When direct definition is hard |
| **Comparison with similar** | How does X differ from Y? | Close concepts, risk of conflation |

For HLE: **operational definition** and **extreme cases** are most useful. Can this be computed? What breaks at edge cases?

## ERR CONSUMPTION AND EXTENSION

You RECEIVE ERR from D1. You must:

1. **For each Element:** Add definition, depth level, scope (IN/OUT)
2. **For each Role:** Verify role assignment is correct after clarification
3. **For each Rule:** Verify rule is correctly stated. Add precision. Flag if source="implied" needs verification
4. **Update Status:** After clarification, some "unknown" may become "constrained" or "known"
5. **Update Dependencies:** Clarification may reveal new dependencies

**Do NOT restructure ERR.** If you discover D1 missed an element, note it in `d1_gaps` field — don't silently add it.

## FAILURE MODES

| Failure | Description | How to Detect |
|---------|-------------|---------------|
| **Equivocation** | Term changes meaning during reasoning | Check: is term used identically in D1 elements and rules? |
| **Premature closure** | "Defined" but collapses under pressure | Test: can you give a counterexample that breaks the definition? |
| **Definitional circularity** | X defined through X or equally unclear terms | Check: would someone unfamiliar understand the definition? |
| **False insight** | Vivid "got it!" without actual correctness | Test: can you EXPLAIN, not just recognize? |
| **Depth mismatch** | Stopping at Level 1-2 when task requires 3-4 | Check: depth_achieved vs task complexity |
| **Scope confusion** | Unclear what's IN vs OUT of a definition | Check: can you name what the definition EXCLUDES? |

## DIAGNOSTIC SELF-CHECK (before output)

Ask yourself:
1. What exactly do I mean by [key term]? (prevent equivocation)
2. Would this definition distinguish X from similar Y? (test distinction power)
3. At what depth level am I operating? Does it match the task? (calibrate)
4. Can I give a counterexample that breaks this definition? (test robustness)
5. Is this term used identically throughout? (L1 compliance)

## META-OBSERVER CHECKLIST

```
SUFFICIENT?
  ├─ Key terms explicitly defined?
  ├─ All participants would understand them identically?
  └─ Depth sufficient for the purpose of reasoning?

CORRECT?
  ├─ No equivocation? (term doesn't change meaning)
  ├─ No definitional circularity?
  └─ Meanings stable throughout? (L1 Identity: A = A)

COMPLETE?
  ├─ Hidden assumptions explicated?
  ├─ Presuppositions named?
  ├─ Equivocation excluded?
  └─ ERR structure from D1 consumed and extended?
```

## OUTPUT FORMAT

Write to d2_output.json:

```json
{
  "d2_output": {
    "clarified_elements": [
      {
        "element_id": "E1",
        "original": "content from D1",
        "definition": "Precise technical definition",
        "depth_level": "nominal|dictionary|functional|essential",
        "scope_in": "What counts as this element",
        "scope_out": "What is excluded",
        "tool_used": "operational_definition|genus_differentia|etc",
        "ambiguities_resolved": ["Any ambiguity found and how resolved"],
        "domain_conventions": "Field-specific meaning if applicable"
      }
    ],
    "clarified_rules": [
      {
        "rule_id": "RULE1",
        "original": "from D1",
        "precise_statement": "Exact formulation after clarification",
        "verification": "stated_verified|implied_verified|implied_unverified|needs_computation",
        "conditions": "Under what conditions does this rule apply?",
        "edge_cases": "Where might this rule break?"
      }
    ],
    "updated_status": [
      {
        "element_id": "E1",
        "status_before": "from D1",
        "status_after": "after clarification",
        "reason": "Why status changed (or 'unchanged')"
      }
    ],
    "hidden_assumptions": [
      "Assumption 1: what is taken for granted",
      "Assumption 2: ..."
    ],
    "d1_gaps": ["Any elements D1 missed that clarification revealed (do NOT add — flag for Team Lead)"],
    "critical_clarification": "The single most important clarification for this question",
    "depth_summary": "Deepest level achieved and whether sufficient for task",
    "failure_check": {
      "equivocation": "none|detected:[details]",
      "premature_closure": "none|risk:[details]",
      "circularity": "none|detected:[details]",
      "depth_mismatch": "none|detected:[details]"
    }
  }
}
```

Update state.json: D2 status → "complete".

## RULES FOR D2

1. Define every D1 element at depth Level 3+ for HLE questions
2. Consume D1's ERR structure — extend it, don't replace it
3. Verify all rules, especially those with source="implied"
4. Flag ambiguities and resolve them (pick one meaning, state why)
5. State hidden assumptions explicitly
6. Do NOT select frameworks (that's D3)
7. Do NOT evaluate or compare (that's D4)
8. Do NOT draw conclusions (that's D5)
9. If you discover D1 missed something — flag it in d1_gaps, don't silently add
