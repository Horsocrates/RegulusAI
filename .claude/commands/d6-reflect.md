# D6 — Reflection

## FUNCTION
Analyze the reasoning process itself. Verify the entire D1-D5 chain. Determine limits, assumptions, and whether a return to an earlier domain is needed.

**Principle of Limitation:** Every answer has scope, boundaries, and opens new questions. A conclusion that claims no limits is claiming too much.

**Dual function:** D6 is both the FINAL domain AND a parallel observer that monitors throughout.

## INPUT
Read ALL previous outputs: d1_output.json through d5_output.json and state.json.

## GENUINE VS FAKE REFLECTION (critical distinction)

| Type | Example | Value |
|------|---------|-------|
| **GENUINE** | "This conclusion assumes constant temperature. If T varies, answer changes to Y." | Adds real information |
| **GENUINE** | "D4 computation used approximation at step 3. Exact calculation might differ by ±5%." | Identifies specific risk |
| **FAKE** | "I have carefully analyzed and am confident." | Restates D5 — adds nothing |
| **FAKE** | "There might be errors." | Generic — applies to anything |
| **FAKE** | "Further research is needed." | Cliché — no specific direction |

**Rule:** Every D6 statement must ADD something that wasn't in D5. If you can delete the statement and lose no information — it's fake.

## 3+1 REFLECTION CLASSES

Complete reflection covers ALL classes:

### Class I: Object (What happened?)
- **Factual reflection:** What exactly was found? What was the sequence of reasoning?

### Class II: Process (How did I think?)
- **Perceptive:** What did D1 notice? What might it have missed?
- **Procedural:** Which domains were strong? Where could reasoning have gone wrong?
- **Perspectival:** From what viewpoint was this analyzed? How would a different framework (D3) change the answer?
- **Fundamental:** What assumptions underlie the conclusion? What was accepted without proof?

### Class III: Self (Meta-level)
- **Emotional/Reactive:** (Less relevant for AI, but: was there a "default" pattern? Training bias?)
  
### Integration
- **Meaning-making:** What lesson for future problems? What changes in approach?

**Minimum for HLE:** Class I + at least 2 from Class II.

## 3 RETURN TYPES

If D6 finds a problem, specify the type of return:

| Return Type | When | Action |
|-------------|------|--------|
| **Corrective** | Error found in D1-D5 | Return to earliest broken domain, fix, re-run downstream |
| **Deepening** | Domain adequate but could go deeper | Return to same domain with request for more depth |
| **Expanding** | Missing perspective or element | Return to D1 (new element) or D3 (new framework) |

**Key principle: Fix the EARLIEST broken domain.** Fixing D5 when the error is in D2 = pointless.

## REVERSE DIAGNOSTICS (error tracing)

When something feels wrong, trace backward:

| Domain | Diagnostic Questions | If OK → |
|--------|---------------------|---------|
| **D5** | Does conclusion follow from D4? Logical leap? Injected premises? | Problem is earlier |
| **D4** | All elements compared? Framework applied consistently? Anomalies missed? | Problem is earlier |
| **D3** | Why this framework? Did it predetermine the answer? Alternatives? | Problem is earlier |
| **D2** | Key terms defined? Ambiguities remaining? Depth sufficient? | Problem is earlier |
| **D1** | Everything noticed? Nothing added? Perception distorted? | Problem outside reasoning |

## ERR CHAIN VERIFICATION

D6 verifies the ENTIRE ERR pipeline:

```
D1: Elements correctly identified?     Status: registered/missed/phantom?
D2: Elements correctly defined?         Status: clarified/ambiguous/false_clarity?
D3: Framework consciously selected?     Status: selected/defaulted/rejected_with_reason?
D4: Criteria applied systematically?    Status: compared/omitted/incomparable?
D5: Conclusion follows from evidence?   Status: necessary/probable/evaluative/unjustified?
D6: Limits recognized?                  Status: bounded/unbounded/returned?
```

Check:
- ☐ ERR structure consistent across domains (no elements appearing/disappearing without explanation)
- ☐ Dependencies remain acyclic (no circular reasoning)
- ☐ Status transitions are justified (each change has a reason)
- ☐ No level violations (Rules governing Rules, Elements acting as Rules)

## META-OBSERVER CHECKLIST

```
SUFFICIENT?
  ├─ Boundaries recognized — where conclusion works, where it stops?
  ├─ Assumptions identified — what was accepted without proof?
  ├─ New questions acknowledged — what does the conclusion reveal but not solve?
  └─ All 3 classes covered? (Object + Process + Integration minimum)

CORRECT?
  ├─ Every statement ADDS something (no fake reflection)?
  ├─ Reverse diagnostics run if any doubt?
  ├─ ERR chain verified across all domains?
  └─ Confidence adjustment justified?

COMPLETE?
  ├─ Return decision made (return to Dₙ OR confirm completion)?
  ├─ If returning: type specified (corrective/deepening/expanding)?
  └─ If completing: scope limitations stated?
```

## OUTPUT FORMAT

Write to d6_output.json:

```json
{
  "d6_output": {
    "scope": {
      "applies_when": "Specific conditions where conclusion holds",
      "fails_when": "Specific conditions where it breaks"
    },
    "assumptions_made": [
      "Specific assumption 1 — impact if wrong: ...",
      "Specific assumption 2 — impact if wrong: ..."
    ],
    "reflection_by_class": {
      "class_i_object": "What was found and how?",
      "class_ii_process": {
        "perceptive": "What might D1 have missed?",
        "procedural": "Which domain was weakest? Where could reasoning have failed?",
        "perspectival": "How would a different D3 framework change the answer?",
        "fundamental": "What was accepted without proof?"
      },
      "integration": "What lesson for similar problems?"
    },
    "return_assessment": {
      "d1_quality": "ERR structure complete? Elements correctly identified?",
      "d2_quality": "Definitions precise? Depth sufficient?",
      "d3_quality": "Framework appropriate? L2 test passed?",
      "d4_quality": "Comparison systematic? Computation verified?",
      "d5_quality": "Conclusion follows? L5 direction valid?",
      "errors_found": ["Specific errors or 'none'"],
      "return_needed": "none|corrective|deepening|expanding",
      "return_target": "none|D1|D2|D3|D4|D5",
      "return_reason": "Why return (or 'completion confirmed')"
    },
    "err_chain_check": {
      "elements_consistent": true,
      "dependencies_acyclic": true,
      "status_transitions_justified": true,
      "no_level_violations": true
    },
    "confidence_adjustment": {
      "d5_confidence": 85,
      "d6_adjusted": 80,
      "reason": "Why adjusted (or 'confirmed — no change')"
    },
    "limitations": [
      "Specific limitation 1 (NOT generic 'there might be errors')",
      "Specific limitation 2"
    ]
  }
}
```

Update state.json: D6 → "complete".

## RULES FOR D6

1. Every statement must ADD information — no fake reflection
2. Cover at least Class I + 2 items from Class II
3. Run reverse diagnostics if ANYTHING feels wrong
4. Verify ERR chain across all 6 domains
5. If error found: specify return type + target domain
6. Fix EARLIEST broken domain, not the symptom
7. State assumptions with their impact if wrong
8. Adjust confidence with specific reason
9. Scope limitations must be SPECIFIC to this problem
10. Do NOT restate D5's conclusion — that's fake reflection
