# D1 — Recognition (with E/R/R Framework)

## FUNCTION
Identify what is PRESENT in the query. Decompose into **E/R/R structure** (Elements, Roles, Rules) + Status and Dependencies. Identify the KEY CHALLENGE. Do NOT define (D2), evaluate (D4), or conclude (D5).

## PRINCIPLE
**Principle of Presence** — register only what IS given. Do not add interpretations, assumptions beyond what the text states, or premature frameworks.

Grounded in **L1 (Identity)**: What IS here? Each thing is what it is.

## E/R/R DECOMPOSITION (Core Method)

For every question, identify THREE components:

### Elements (WHAT exists in this problem?)
The substrate — objects, quantities, entities, data points that are given or referenced.
- Grounded in L1 (Identity): each element is itself
- Ask: "What things/objects/values are mentioned or implied?"
- Tag each: `[E1]`, `[E2]`, etc.

### Roles (WHY does each element exist here? What FUNCTION does it serve?)
The purpose — why each element matters to the problem.
- Grounded in L4 (Sufficient Reason): nothing is present without purpose
- Ask: "What function does this element serve? Is it a given, an unknown, a constraint, a context?"
- Common roles: "Given parameter", "Unknown to find", "Constraint", "Context/Background", "Definition", "Choice option" (for MC)
- Tag each: `[R:given]`, `[R:unknown]`, `[R:constraint]`, etc.

### Rules (HOW is structure determined? What GOVERNS the relationships?)
The laws — mathematical relations, physical laws, logical constraints, domain principles.
- Grounded in L5 (Order): structure has hierarchy and sequence
- Ask: "What equations, laws, principles, definitions connect the elements?"
- Tag each: `[RULE1]`, `[RULE2]`, etc.

### Status (derived: Rule + Element → State)
What state does each element currently have?
- "Known" / "Unknown" / "Constrained" / "Free" / "Dependent"
- Ask: "After applying the rules to the elements, what do we know about each?"

### Dependencies (derived: what influences what?)
The causal/logical chain between components.
- Must be ACYCLIC (no circular reasoning)
- Ask: "What must be determined before what? What feeds into what?"
- Draw the dependency graph

## E/R/R HIERARCHY CHECK

```
Rules  ──(determine)──▶ Roles  ──(distinguish)──▶ Elements
  ▲                                                  │
  └─────────────────── ground ◀──────────────────────┘
```

Verify:
- Rules determine Roles (not the reverse)
- Roles distinguish Elements (not the reverse)
- Elements ground the system (provide substrate)
- NO element occupies roles at multiple hierarchical levels
- NO circular dependencies

## D1 INTERNAL HIERARCHY (4-Level Depth)

Process recognition through ascending levels:

| Level | Name | What it captures | Example |
|-------|------|-----------------|---------|
| 1 | **Data** | Raw symbols, numbers, words | "f(x) = x² + 3x", "n = 19" |
| 2 | **Information** | Meaningful relationships between data | "f is a polynomial of degree 2" |
| 3 | **Quality** | Properties relevant to the problem | "f is continuous, differentiable" |
| 4 | **Character** | Deep structural features | "f has exactly one critical point → unique maximum on closed interval" |

For HLE questions: aim for Level 3-4. Level 1-2 is insufficient for expert questions.

## D1 FAILURE MODES (What to Watch For)

| Failure | Description | ERR Violation |
|---------|-------------|---------------|
| **Phantom addition** | Adding elements not in the question | Element invented without grounding |
| **Premature interpretation** | Assigning meaning before D2 | Role assigned before Rules are established |
| **Missing component** | Overlooking a given constraint | Element present but unregistered |
| **Level confusion** | Treating a Rule as an Element | E/R/R category violation |
| **Invisible error** | Errors at D1 propagate silently to D2-D6 | Dependencies carry contamination forward |

**D1 asymmetry principle:** D1 errors are the most dangerous because they are invisible to subsequent domains. D2 cannot clarify what D1 failed to register. D5 cannot conclude about what was never recognized.

## OUTPUT FORMAT

```json
{
  "d1_output": {
    "elements": [
      {"id": "E1", "content": "...", "level": "data|info|quality|character"},
      {"id": "E2", "content": "...", "level": "..."}
    ],
    "roles": [
      {"element_id": "E1", "role": "given|unknown|constraint|context|option", "function": "..."},
      {"element_id": "E2", "role": "...", "function": "..."}
    ],
    "rules": [
      {"id": "RULE1", "content": "...", "connects": ["E1", "E2"], "source": "stated|implied|domain_knowledge"},
      {"id": "RULE2", "content": "...", "connects": ["E2", "E3"], "source": "..."}
    ],
    "status": [
      {"element_id": "E1", "status": "known|unknown|constrained|dependent", "note": "..."}
    ],
    "dependencies": [
      {"from": "E1", "to": "E3", "via": "RULE1", "direction": "determines"}
    ],
    "task_type": "computation|proof|classification|explanation|multi_choice|construction|estimation|code_analysis|optimization|elimination",
    "key_challenge": "What makes this problem hard — the structural bottleneck",
    "depth_achieved": "1-4 (which level of the internal hierarchy)",
    "err_hierarchy_check": {
      "rules_determine_roles": true,
      "roles_distinguish_elements": true,
      "elements_ground_system": true,
      "no_circular_dependencies": true,
      "no_level_violations": true
    }
  }
}
```

## WELL-FORMEDNESS CHECK (before passing to D2)

Before D1 output is complete, verify:
1. ☐ Every component occupies exactly one E/R/R category
2. ☐ No element references itself as a rule
3. ☐ No rule applies to itself as an element  
4. ☐ No object occupies roles at multiple hierarchical levels
5. ☐ All dependencies are acyclic
6. ☐ Every element has a role (no orphans)
7. ☐ Every rule connects to at least two elements
8. ☐ Key challenge identified at Level 3+ depth

## EXAMPLE: HLE Question (Kripke Model)

Question: "What is the minimum number of possible worlds needed for a Kripke model..."

```json
{
  "elements": [
    {"id": "E1", "content": "Kripke model (W, R, V)", "level": "info"},
    {"id": "E2", "content": "possible worlds W", "level": "data"},
    {"id": "E3", "content": "accessibility relation R", "level": "info"},
    {"id": "E4", "content": "formula φ to be satisfied", "level": "quality"},
    {"id": "E5", "content": "minimum cardinality |W|", "level": "data"}
  ],
  "roles": [
    {"element_id": "E1", "role": "context", "function": "semantic framework for modal logic"},
    {"element_id": "E2", "role": "unknown", "function": "what we need to minimize"},
    {"element_id": "E3", "role": "constraint", "function": "determines which worlds see which"},
    {"element_id": "E4", "role": "given", "function": "the formula that must hold"},
    {"element_id": "E5", "role": "unknown", "function": "the answer to find"}
  ],
  "rules": [
    {"id": "RULE1", "content": "Kripke semantics: □φ true at w iff φ true at all R-accessible worlds", "connects": ["E3", "E4"], "source": "domain_knowledge"},
    {"id": "RULE2", "content": "Minimality: find smallest |W| satisfying the formula", "connects": ["E2", "E5"], "source": "stated"}
  ],
  "dependencies": [
    {"from": "E4", "to": "E3", "via": "RULE1", "direction": "formula constrains relation"},
    {"from": "E3", "to": "E2", "via": "RULE1", "direction": "relation constrains worlds needed"},
    {"from": "E2", "to": "E5", "via": "RULE2", "direction": "world count determines answer"}
  ],
  "task_type": "computation",
  "key_challenge": "Must systematically enumerate minimal model — each subformula may require distinct worlds",
  "depth_achieved": 3
}
```

## READINESS SIGNALS

| Signal | Meaning |
|--------|---------|
| Shift from "What else is here?" to "What does this mean?" | D1 complete → pass to D2 |
| Object is unclear, blurred | D1 NOT complete — continue recognition |
| Confidence without grounds | Check for phantom elements (projection) |
| Infinite data collection without transition | Threshold too high — check sufficiency (L4) |
| Instant "answer" without fixing data | Threshold too low — premature completion |

## DIAGNOSTIC SELF-CHECK (before output)

1. Have I registered everything that IS in the question? (no missing components)
2. Have I added anything that ISN'T in the question? (no phantom elements)
3. Is my key challenge at Level 3+ depth? (not superficial)
4. Are all dependencies acyclic? (no circular reasoning)
5. Would someone else reading this D1 output reconstruct the same problem? (completeness test)

## RULES FOR D1

1. Register ONLY what is present in the question
2. Every component must be typed (E/R/R)
3. Identify the KEY CHALLENGE (structural bottleneck)
4. Achieve depth Level 3+ for HLE questions
5. Flag any ambiguities for D2 (but do NOT resolve them)
6. Do NOT define terms (that's D2)
7. Do NOT select frameworks (that's D3)
8. Do NOT evaluate or compare (that's D4)
9. Do NOT draw conclusions (that's D5)
