# D3 — Framework Selection

## FUNCTION
Choose the evaluation framework BEFORE evaluating. Determine the coordinate system for comparison.

**Principle of Hierarchy:** Begin from the highest level. Before comparing characteristics → verify comparability at the information level. Before information → verify data existence.

**Grounded in L5 (Order):** D3 must NOT be governed by D5. Conclusion cannot precede framework selection. If you already "know" the answer before selecting a framework — that's confirmation bias (L2 violation).

## CRITICAL WARNING: UNCONSCIOUS SELECTION

D3 is the domain **most vulnerable to bias**. Frameworks feel like "the natural way to see things" — the choice goes unnoticed. Unlike D1 (where perception feels immediate), D3 invisibility comes from frameworks feeling OBVIOUS.

**Watson-Crick vs Pauling:** Same problem (DNA structure). Pauling used purely chemical framework. Watson-Crick used functional framework ("how does structure enable copying?"). Better framework > better chemistry. Pauling erred not because he knew less, but because his framework didn't match the problem's nature.

**For AI:** The equivalent is defaulting to the most common approach from training data without considering whether it fits THIS specific problem.

## INPUT
Read d2_output.json. You receive:
- Clarified elements with definitions and depth levels
- Clarified rules with precise statements and conditions
- Updated status and hidden assumptions
- Critical clarification and d1_gaps

## THE L2 OBJECTIVITY TEST (mandatory)

Before selecting a framework, ask:

> **"Am I ready to accept ANY answer this framework produces?"**

If the framework is constructed so that one result is impossible — that is rationalization, not inquiry.

| | Honest Frame | Dishonest Frame |
|-|-------------|-----------------|
| **Honest Question** | Genuine inquiry ✅ | Hidden bias ⚠️ |
| **Dishonest Question** | Misguided but correctable | Full rationalization ❌ |

## DUAL CRITERION (both must be satisfied)

The framework must match:
1. **Nature of the phenomenon** — Does the framework fit what we're examining? (Chemical vs functional lens for DNA)
2. **Purpose of the inquiry** — Does the framework serve what we need to find? (Exact value? Classification? Proof?)

Fits phenomenon but not purpose → doesn't fit. Fits purpose but not phenomenon → doesn't fit.

## 4 LEVELS OF SELECTION COMPLEXITY

Identify which level applies to this question:

| Level | Description | Action | Example |
|-------|-------------|--------|---------|
| 1. **Obvious** | Question dictates framework | Apply directly | "Calculate X" → computational framework |
| 2. **Competing** | Several frameworks valid, each gives different answer | Compare, justify choice | Legal vs moral vs economic analysis |
| 3. **Creating new** | Existing frameworks don't work | Construct from elements | Novel interdisciplinary problem |
| 4. **Meta-frame** | Need to integrate multiple frameworks | Build unified structure | Biopsychosocial model |

For HLE: Most are Level 1-2. Some interdisciplinary questions are Level 3-4.

## FRAMEWORK HIERARCHY CHECK

Verify you're starting at the right level:

```
Level 4 (Data):          Is there anything to compare at all? (foundation)
Level 3 (Information):   Data completeness — how many datasets per object?
Level 2 (Quality):       Categories — which dimensions are present/absent?
Level 1 (Characteristic): Concrete values — specific comparisons
```

**L5 Rule:** Start from the top. Don't compare characteristics before verifying data exists.

## ERR CONSUMPTION

D3 is a **meta-level ERR operation**: you're selecting Rules that will govern D4's comparison.

From D2 output:
- **Elements** → what needs to be compared
- **Clarified Rules** → which existing rules constrain the comparison
- **Status** → what's known vs unknown determines framework requirements

Your framework selection = choosing which additional Rules (criteria) to apply in D4.

## FAILURE MODES

| Failure | Description | L-violation | Detection |
|---------|-------------|-------------|-----------|
| **Confirmation bias** | Framework chosen for desired conclusion | L2 + L5 | L2 test: "ready to accept any answer?" |
| **False dilemma** | Binary framework where multiple options exist | — | Count alternatives: if only 2, check for more |
| **Category mistake** | Framework for one type applied to another | — | Dual criterion check |
| **Unconscious selection** | "Natural way" adopted without awareness | — | Can you NAME the framework explicitly? |
| **Wrong hierarchy level** | Starting from characteristics without checking data | L5 | Hierarchy check |
| **Frame paralysis** | Endless cycling without proceeding to D4 | L5 | Anti-paralysis: adequate > perfect |

## META-OBSERVER CHECKLIST

```
SUFFICIENT?
  ├─ Framework selected explicitly? (can you NAME it?)
  ├─ Evaluation criteria defined for D4?
  ├─ Dual criterion checked? (nature + purpose)
  └─ Comparison can begin with this framework?

CORRECT?
  ├─ No Confirmation Bias? (L2 test: ready to accept ANY answer?)
  ├─ No Category Mistake? (framework matches phenomenon type)
  ├─ D5 not governing D3? (conclusion doesn't precede reasoning — L5)
  ├─ Hierarchy level correct? (start from top)
  └─ Selection conscious, not defaulted?

COMPLETE?
  ├─ At least one alternative considered and rejection justified?
  ├─ Framework limitations noted? (what it doesn't illuminate)
  └─ Ready for revision if D4/D5 reveals problems?
```

## OUTPUT FORMAT

Write to d3_output.json:

```json
{
  "d3_output": {
    "selection_complexity": "obvious|competing|creating_new|meta_frame",
    "framework": {
      "name": "Framework name",
      "description": "How it works",
      "justification_nature": "Why it fits the phenomenon",
      "justification_purpose": "Why it serves the inquiry goal",
      "criteria": [
        {"id": "K1", "name": "Criterion", "description": "What it measures", "applies_to": ["E1", "E2"]}
      ]
    },
    "alternatives_considered": [
      {"name": "Alternative", "reason_rejected": "Why not this — specific, not generic"}
    ],
    "objectivity_test": {
      "l2_passed": true,
      "ready_to_accept_any_answer": "Yes/No — if No, explain what answer would be unacceptable and why",
      "confirmation_bias_risk": "none|low|high — explain"
    },
    "hierarchy_check": {
      "starting_level": "data|information|quality|characteristic",
      "justified": "Why starting at this level"
    },
    "framework_limitations": "What this framework does NOT illuminate",
    "approach_plan": "Step-by-step how D4 should apply this framework",
    "failure_check": {
      "unconscious_selection": "none|risk:[details]",
      "category_mistake": "none|risk:[details]",
      "false_dilemma": "none|risk:[details]"
    }
  }
}
```

Update state.json: D3 → "complete".

## RULES FOR D3

1. ALWAYS run the L2 objectivity test: "Am I ready to accept ANY answer?"
2. Check dual criterion: nature of phenomenon + purpose of inquiry
3. NAME the framework explicitly — if you can't name it, it's unconscious
4. Consider at least ONE alternative with specific rejection reason
5. Start at the right hierarchy level (top-down)
6. Define criteria that D4 will apply — be specific, not vague
7. Note framework limitations honestly
8. Anti-paralysis: adequate framework > perfect framework. Proceed to D4.
9. Do NOT compare or evaluate (that's D4)
10. Do NOT draw conclusions (that's D5)
