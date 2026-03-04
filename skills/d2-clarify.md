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
| **Premature closure** | "Defined" but collapses under pressure. **Includes:** resolving D1 ambiguity flags by choosing the simpler reading without testing alternatives | Test: can you give a counterexample? For ambiguity flags: did you enumerate ALL readings before choosing one? |
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

## AMBIGUITY PROTOCOL (L4 — Sufficient Reason for closure)

When D1 flags an ambiguity (especially those marked "trap", "unusual", or "FLAG"), D2 must NOT silently choose one interpretation. Instead:

### Step 1: Enumerate ALL viable interpretations
For each ambiguity, list every semantically distinct reading. Do not filter by "most likely" — filter only by "logically possible given the text."

### Step 2: Test each against context
- Does interpretation A align with the structure of other sub-questions?
- Does interpretation B require assumptions not present in the text?
- Does the question's phrasing have a standard meaning in the domain?

### Step 2.5: Directional Expression Resolution (L5)

When the ambiguity involves directional language ("from X in Y"):

1. **Retrieve RULE_ORD** from D1 output
2. **Determine causal direction:** In the process described, does X precede Y or does Y precede X?
3. **Apply the Provenance Principle (L5):**

   > **"From X in Y" means: atoms/components that ORIGINATE IN X and are found IN Y.**
   > Origination requires that X existed as a source. If X was created AFTER Y in the process,
   > then X cannot be a source for Y. The answer to "how many [things] from X in Y" is 0.

4. **If the question reverses the process direction — this is a SIGNAL, not noise:**
   - The question likely tests whether the reasoner understands the ordering
   - The answer under provenance semantics is typically 0 or null
   - Do NOT reinterpret the direction as "shared" or "overlapping" — this collapses the asymmetry that L5 requires

5. **Log the resolution explicitly:**

```json
{
  "flag": "FLAG_DIRECTION",
  "expression": "from 7 in 10",
  "process_order": "10 → 7 (10 created before 7)",
  "direction": "REVERSE — question asks about source that was created AFTER target",
  "provenance_answer": 0,
  "shared_atoms_answer": 1,
  "resolution": "L5 provenance: 0. Process ordering is structural (RULE_ORD), not interpretive.",
  "confidence": "high — consistent with Q1 and Q2 forward direction pattern"
}
```

### Worked Example

Question: "How many nitrogens from compound 7 are present in compound 10?"

| Check | Result |
|-------|--------|
| RULE_ORD | Synthesis: 11→12→10→7→13→14→15→1 |
| Direction | 10 is created BEFORE 7 |
| "From 7 in 10" | Asks: atoms originating FROM 7 found IN 10 |
| L5 test | 7 does not exist when 10 is created → 7 cannot be a source for 10 |
| Provenance answer | **0** |
| "Shared atoms" answer | 1 (they share the same nitrogen) |
| Pattern check | Q1: from 11 in 1 (forward ✅). Q2: from 11 in 14 (forward ✅). Q3: from 7 in 10 (**reverse** — intentional trap) |
| Resolution | **0** — L5 ordering is structural, not reinterpretable |

### Step 3: COMMIT or REGISTER AS UNRESOLVED

**COMMIT** (single interpretation) — only if:
- All other readings violate L1 (Identity) or domain conventions
- The context unambiguously resolves the ambiguity
- You can state why the alternative is WRONG, not just why yours is "more natural"

**REGISTER AS UNRESOLVED** — if:
- Two or more readings are viable after testing
- D1 flagged the ambiguity as a potential trap
- The alternative interpretation would change the answer

When unresolved, add to `unresolved_ambiguities` with ALL viable readings:

```json
"unresolved_ambiguities": [
  {
    "id": "AMB1",
    "source_flag": "FLAG ID from D1",
    "readings": [
      {"label": "Reading A", "basis": "Why viable", "requires": ["A1: assumption"]},
      {"label": "Reading B", "basis": "Why viable", "requires": ["A2: assumption"]}
    ],
    "impact": "Different readings lead to different answers",
    "note": "D3 must generate separate hypotheses for each viable reading"
  }
]
```

**CRITICAL:** D2 does NOT form hypotheses or predict answers. D2 ONLY clarifies terms, verifies rules, and registers what is resolved vs unresolved. Hypothesis formation is D3's job — D3 will use D2's clarifications and unresolved ambiguities to enumerate ALL possible answer-hypotheses.

**CRITICAL:** Do NOT choose between readings based on "likelihood" or "what the question probably means." If multiple readings are viable, register ALL of them. D3 will form hypotheses and D4 will test them.

### Worked example (from HLE error):

Question: "How many nitrogens from compound 7 are present in compound 10?"
D1 flag: "Synthesis goes 10->7, but question asks 7->10. May be a trap."

**WRONG (premature closure):**
> "Since 10 and 7 share the same nitrogen, the answer is 1."

**RIGHT (register unresolved):**
> AMB1: "from X in Y" has two viable readings:
>   Reading A: shared atoms between X and Y
>   Reading B: atoms that originate FROM X and end up IN Y (provenance)
> Impact: Reading A → answer 1, Reading B → answer 0
> Note: D3 must generate hypotheses for both readings. Q1 and Q2 follow forward direction — pattern break here is a signal.

## PROOF CHAIN PROTOCOL (L4 — Sufficient Reason for every derivation step)

When you derive any claim in D2 (rule verification, constraint derivation, structural proof), output it as a **PROOF CHAIN** — a numbered sequence of steps with explicit tracking of what each step assumes.

**Grounding:** L4 (Sufficient Reason) requires that every conclusion have grounds. A "proof" with unstated assumptions has INSUFFICIENT grounds. The proof chain makes every ground explicit, so TL can audit which are solid and which are sand.

### Format

For each derivation in D2, output:

```yaml
proof_chain:
  claim: "The unknown chloride must be MCl₂ (divalent)"
  steps:
    - step: 1
      statement: "Metal A replaces metal M in MCl_n"
      justification: "Standard displacement reaction pattern"
      assumes: ["A1: Reaction is simple displacement (one metal replaces another)"]
      status: ASSUMED  # not PROVEN from the question text

    - step: 2
      statement: "The displaced metal M precipitates as solid"
      justification: "Standard outcome of displacement"
      assumes: ["A2: Product metal is insoluble at reaction conditions"]
      status: ASSUMED

    - step: 3
      statement: "Charge balance: A^{2+} replaces M^{n+}, so n = 2"
      justification: "If A is divalent (given) and reaction is 1:1, then M must also be divalent"
      assumes: ["A1", "A3: Stoichiometry is 1:1 (one A atom replaces one M atom)"]
      status: CONDITIONAL  # depends on A1 and A3

  hidden_assumptions:
    - "A1: Reaction is simple displacement — but what if A and M are the SAME element in different oxidation states (comproportionation)?"
    - "A3: 1:1 stoichiometry — but comproportionation/disproportionation have different ratios"

  conclusion_strength: CONDITIONAL  # not PROVEN — at least one step is ASSUMED
  if_wrong: "If A1 false (e.g., comproportionation), the chloride could be MCl₃ with the SAME metal A"
```

### Proof Chain Rules

1. **Every step must list its assumptions explicitly.** No step is "obvious" — what is obvious in one context may be false in another (L1: identity of problem matters).

2. **Assumption statuses:**
   | Status | Meaning | Example |
   |--------|---------|---------|
   | PROVEN | Stated in question text or derived from D1 ERR | "Metal A is divalent" (given in question) |
   | IMPORTED | From domain knowledge — must justify transfer | "120° angles are optimal" (from Steiner) |
   | ASSUMED | Taken as given without proof | "Reaction is 1:1 displacement" |
   | CONDITIONAL | Depends on ASSUMED/IMPORTED steps | "Therefore n = 2" (depends on A1, A3) |

3. **CONDITIONAL conclusions CANNOT close D1 flags.** If D1 raised FLAG: "Can |R(X)| = 0?" and D2's proof that |R(X)| ≥ 1 is CONDITIONAL (depends on unproven connectedness), the flag MUST remain OPEN. Only PROVEN conclusions can close flags.

4. **conclusion_strength** is determined by the weakest step:
   - All steps PROVEN → conclusion PROVEN
   - Any step ASSUMED or IMPORTED → conclusion CONDITIONAL
   - Untested claim → conclusion UNVERIFIED

5. **if_wrong field is MANDATORY.** Forces you to consider what happens if the proof fails. This is the most important field — it reveals whether the proof matters or is just cosmetic.

### Common Hidden Premises to Check

| Domain | Hidden Premise | What Could Break |
|--------|---------------|------------------|
| Chemistry | "Reaction is type X" | Could be comproportionation, disproportionation, redox |
| Chemistry | "Stoichiometry is 1:1" | Could be 1:2, 2:3, or other |
| Topology | "This set is connected" | Exotic spaces violate this |
| Topology | "Closure preserves property P" | Not true for all P |
| Probability | "Symmetry applies" | Asymmetric distributions break symmetry arguments |
| Algebra | "Unique solution exists" | Multiple solutions or no solution possible |

### Worked Example: When Proof Chain Catches an Error

**Question:** Metal plate placed in chloride solution. Mass decreased. Find metal and reaction.

**Without proof chain:** "By charge balance, MCl₂. Confidence: 100%." → TL accepts → WRONG (correct answer is comproportionation Fe + 2FeCl₃ = 3FeCl₂)

**With proof chain:**
- Step 1: "Reaction is simple displacement" → status: **ASSUMED** (not stated in question)
- Step 2: "Stoichiometry is 1:1" → status: **ASSUMED**
- Step 3: "Therefore MCl₂" → status: **CONDITIONAL**
- hidden_assumptions: "What if A and M are the same element?"
- conclusion_strength: **CONDITIONAL**
- if_wrong: "Chloride could be MCl₃ with same metal A in different oxidation state"

→ TL sees CONDITIONAL → D1 flag remains OPEN → D3 considers both displacement AND comproportionation frameworks → D4 tests both → comproportionation gives 0.00% error → CORRECT

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
  ├─ ERR structure from D1 consumed and extended?
  └─ All derivations structured as proof chains?
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
    "unresolved_ambiguities": [
      {
        "id": "AMB1",
        "source_flag": "FLAG ID from D1 that triggered this",
        "readings": [
          {"label": "Reading A", "basis": "Why viable", "requires": ["assumptions needed"]},
          {"label": "Reading B", "basis": "Why viable", "requires": ["assumptions needed"]}
        ],
        "impact": "How different readings affect downstream analysis",
        "note": "D3 must generate separate hypotheses for each viable reading"
      }
    ],
    "proof_chains": [
      {
        "claim": "Statement being proven",
        "steps": [
          {
            "step": 1,
            "statement": "First step of the proof",
            "justification": "Why this step follows",
            "assumes": ["A1: assumption text"],
            "status": "PROVEN|IMPORTED|ASSUMED|CONDITIONAL"
          }
        ],
        "hidden_assumptions": ["Unstated premises the proof depends on"],
        "conclusion_strength": "PROVEN|CONDITIONAL|UNVERIFIED",
        "if_wrong": "What changes if this proof fails"
      }
    ],
    "d1_flag_resolution": [
      {
        "flag_id": "FLAG from D1",
        "resolution": "resolved|open",
        "basis": "PROVEN proof chain | CONDITIONAL proof chain",
        "note": "If CONDITIONAL → flag remains OPEN, forwarded to D3-D5"
      }
    ],
    "ambiguity_status": "all_resolved | unresolved:[count] ambiguities forwarded to D3",
    "d1_gaps": ["Any elements D1 missed that clarification revealed (do NOT add — flag for Team Lead)"],
    "critical_clarification": "The single most important clarification for this question",
    "depth_summary": "Deepest level achieved and whether sufficient for task",
    "failure_check": {
      "equivocation": "none|detected:[details]",
      "premature_closure": "none|risk:[details]",
      "circularity": "none|detected:[details]",
      "depth_mismatch": "none|detected:[details]",
      "conditional_flag_closure": "none|detected:[which D1 flags closed by CONDITIONAL proofs]"
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
10. When D1 flags an ambiguity — follow the AMBIGUITY PROTOCOL. Enumerate all readings, test against context, then COMMIT or REGISTER AS UNRESOLVED. Never silently resolve a D1 flag.
11. D2 does NOT form hypotheses about the answer. Register unresolved ambiguities for D3. D3 will form hypotheses based on D2's clarifications.
12. Pattern consistency: if a multi-part question has parts 1-N following one pattern, and part N+1 breaks the pattern — this is likely intentional. Flag the pattern break; do not normalize it.
13. Every derivation or proof must follow the PROOF CHAIN PROTOCOL — numbered steps with explicit assumptions and conclusion_strength classification.
14. CONDITIONAL proofs CANNOT close D1 flags. Only PROVEN conclusions (all steps derived from question text or D1 ERR) may close a flag. If you close a flag with a CONDITIONAL proof, state this explicitly so TL can re-open it.
15. The if_wrong field is mandatory for every proof chain — you MUST state what changes if the proof fails. This is not optional.
