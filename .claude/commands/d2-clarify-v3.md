# D2 — Clarification

## ROLE
Transform D1's components from NOTICED to DEFINED. Fill in MEANING with sufficient depth for the task. Add D2 section to the Reasoning Passport. Do NOT select frameworks (D3), compare (D4), or conclude (D5).

## INPUT
Read the Reasoning Passport — D1 section. You receive:
- Elements (E1, E2...) with hierarchy levels (data/info/quality/character)
- Roles (given/unknown/constraint-explicit/implicit/context/option)
- Rules with connections and sources
- Status, Dependencies
- Ambiguities (with severity), Missing Data, Assumptions Surfaced
- Key challenge, task type, alternative reading

Your job: define every element, verify every rule, resolve every ambiguity — WITHOUT restructuring D1's ERR. You EXTEND it, not replace it.

## PRINCIPLES

**Principle of Questioning (L4):** Clarification has no natural stopping point. The stop is determined by sufficiency for the purpose of reasoning, not by the feeling of "enough." Stop too early = premature closure. Stop too late = overexplanation obscuring clarity.

**Meaning Stability (L1):** A term must preserve its meaning throughout reasoning. If "X" means one thing at the start and another at the end — L1 violated. D2's core obligation: lock meanings so downstream domains can rely on them.

**State Change, Not Accumulation.** The difference between "knowing a word" and "understanding the meaning" is qualitative, not quantitative. Clarification is a change of state — from recognition to understanding. The criterion: can you EXPLAIN, not just RECOGNIZE?

**False Insight Warning.** The subjective "aha!" correlates with confidence but NOT with correctness. False understanding is experienced as vividly as genuine understanding. Feeling of obviousness ≠ guarantee of truth. Criterion of genuine understanding: ability to withstand verification — explain, apply, defend against objections.

**D2 is where most defective paradoxes break.** 20 of 25 defective paradoxes in the catalog dissolve at D2 — through exposing conceptual indeterminacy, hidden contradictions, or false premises. D2 is the primary defense against problems that SEEM coherent but aren't.

## DEPTH LEVELS

Calibrate depth to the task. Expert questions typically require Level 3–4.

| Level | Name | What You Know | Test |
|-------|------|---------------|------|
| 1 | **Nominal** | Can point to examples. Recognize but can't explain WHY | "That bright dot" |
| 2 | **Dictionary** | Can define. Know what distinguishes X from Y | "Self-luminous celestial body" (≠ planet) |
| 3 | **Functional** | Understand the mechanism. Can predict and explain | "H→He fusion; color = temperature" |
| 4 | **Essential** | Grasp the nature at the level of PRINCIPLE | "Not a thing but a PROCESS: equilibrium of gravity vs nuclear pressure" |

**Rule:** State the depth level achieved for each key component. If depth < 3 for an expert question, flag it.

## CLARIFICATION TOOLS

Select the right tool for each component:

| Tool | How It Works | Best For |
|------|-------------|----------|
| **Genus + differentia** | "X = genus + distinguishing feature" | Clear categorical concepts |
| **Examples and counterexamples** | Delineate boundaries of a concept | Fuzzy, ethical concepts |
| **Extreme cases** | Does definition work at boundaries? (Gettier-type) | Exposing hidden assumptions |
| **Usage analysis** | Meaning = use in context. Collect cases, find pattern | Abstract concepts |
| **Operational definition** | How to verify/test? | Scientific, computational tasks |
| **Analysis of the opposite** | What is NOT-X? | When direct definition is hard |
| **Comparison with similar** | How does X differ from Y? | Close concepts, risk of conflation |
| **Etymological analysis** | Where does the word come from? | Points to forgotten meanings |
| **Genetic analysis** | How did the concept arise? What problem did it solve? | Limits of applicability |

For expert questions: **operational definition** and **extreme cases** are most critical.

## PROCESS

### Step 0: CONSUME D1 PASSPORT
Read D1 section completely. Inventory:
- Which elements need definition? (ALL — but prioritize by role: unknowns and constraints first)
- Which ambiguities are blocking? (Must resolve before proceeding)
- Which rules have source="implied"? (Must verify)
- What assumptions did D1 surface? (Must either confirm or reject)
- What was the alternative reading? (Must address — does clarification resolve it?)

### Step 1: DEFINE ELEMENTS
For each D1 element:
1. Select appropriate clarification tool
2. Define at target depth level
3. Specify scope: what counts IN, what's EXCLUDED
4. Test: "Would a competent expert accept this definition?"
5. Test: "Does a counterexample break it?"

**Priority order:** unknowns → constraints → givens → context. Unknowns define what we're looking for; constraints define the boundaries; getting these wrong = everything else wrong.

### Step 2: RESOLVE AMBIGUITIES
For each D1 ambiguity:
1. Examine each reading D1 identified
2. Apply domain conventions if applicable
3. Select one meaning — state WHY (with evidence from text or domain)
4. If genuinely irresolvable → mark as unresolved, note impact on downstream domains

**Blocking ambiguities MUST be resolved here.** If D2 cannot resolve → flag for human, do not guess.

### Step 3: VERIFY RULES
For each D1 rule:
- **source=stated:** Verify precise formulation. Are conditions complete? Edge cases?
- **source=implied:** Is this actually true? Under what conditions? What if it's wrong?
- **source=domain_knowledge:** Is this the right domain? Correct version of the principle?

### Step 4: SURFACE HIDDEN CONTENT
- **Presuppositions:** What does the question ASSUME to be true without stating it?
- **Hidden constraints:** What domain knowledge restricts the problem that isn't stated?
- **Premise coherence check:** Are the stated conditions compatible? (Unexpected Hanging pattern: conditions that SEEM compatible but contain hidden contradiction)

### Step 5: UPDATE ERR STATUS
After clarification:
- Some "unknown" elements may become "constrained" or "known"
- Some "implied" rules may become "verified" or "rejected"
- Dependencies may change if clarification reveals new connections
- If D1 missed an element → note in `d1_gaps` — do NOT silently add

## ANTI-PATTERNS

### AP1: Equivocation — meaning drift within reasoning
**НЕ ДЕЛАЙ:** Use the same term with different meanings in different parts of the analysis.
**ВМЕСТО:** Lock each term's meaning at first use. If the term genuinely has multiple meanings → distinguish explicitly (X₁ vs X₂).
**ПРИМЕР:** "Freedom" = political liberty in premise, = absence of constraints in conclusion. Ship of Theseus = "same" drifts between material/functional/legal identity.
**DIAGNOSTIC:** "Does this key term mean EXACTLY the same thing each time it appears?"

### AP2: Premature closure — "defined" but collapses under pressure
**НЕ ДЕЛАЙ:** Accept first definition that feels right.
**ВМЕСТО:** Test with counterexample. If first counterexample destroys definition → depth insufficient.
**ПРИМЕР:** "Knowledge = justified true belief" collapses at Gettier cases.
**DIAGNOSTIC:** "Can I give a counterexample that breaks this definition?"

### AP3: Definitional circularity — X defined through X
**НЕ ДЕЛАЙ:** Define concept using equally unclear terms or itself.
**ВМЕСТО:** Unpack until you reach terms the audience already understands.
**ПРИМЕР:** "Justice is just treatment." "Time is what clocks measure."
**DIAGNOSTIC:** "Would someone unfamiliar with X understand this definition?"

### AP4: False insight — vivid "got it!" without correctness
**НЕ ДЕЛАЙ:** Trust the "aha!" feeling as confirmation of understanding.
**ВМЕСТО:** Test: can you EXPLAIN (not just recognize)? Can you APPLY? Can you DEFEND against objections?
**ПРИМЕР:** "Obviously this is a simple optimization problem" — but boundary conditions make it NP-hard.

### AP5: Depth mismatch — stopping too shallow for the task
**НЕ ДЕЛАЙ:** Provide Level 1–2 definition when task requires Level 3–4.
**ВМЕСТО:** Check: does the task require knowing the MECHANISM (Level 3) or the PRINCIPLE (Level 4)?
**ПРИМЕР:** Expert chemistry question defined at dictionary level ("acid = substance that donates protons") when functional level needed (pKa, conjugate base stability, solvent effects).
**DIAGNOSTIC:** "At what depth level am I operating? Does it match the task?"

### AP6: Scope confusion — unclear what's IN vs OUT
**НЕ ДЕЛАЙ:** Leave definition boundaries fuzzy.
**ВМЕСТО:** Explicitly state what the definition INCLUDES and EXCLUDES.
**ПРИМЕР:** "Mammal" — whale is IN (despite appearing fish-like), platypus is IN (despite laying eggs). Without scope → classification errors downstream.

### AP7: Hidden agent — passive voice concealing responsibility
**НЕ ДЕЛАЙ:** Accept "it has been decided" or "mistakes were made" without identifying WHO.
**ВМЕСТО:** Convert passive → active. Name the agent.
**ПРИМЕР:** "The policy was implemented" → WHO implemented it? The answer changes accountability.
**DIAGNOSTIC:** "Who actually did this? Why is the agent not named?"

### AP8: Treating comparative concepts as absolute
**НЕ ДЕЛАЙ:** Apply absolute yes/no classification to essentially comparative concepts.
**ВМЕСТО:** Supply the comparison class: "X relative to WHAT?"
**ПРИМЕР:** Sorites paradox — "heap" is comparative, not absolute. "Tall" requires "compared to whom?" "Rich" requires "in what context?"
**DIAGNOSTIC:** "Does this concept require a reference point that hasn't been specified?"

### AP9: Accepting incoherent premises
**НЕ ДЕЛАЙ:** Reason from premises without checking their coherence.
**ВМЕСТО:** Before building on premises, test: can all stated conditions be simultaneously satisfied?
**ПРИМЕР:** Unexpected Hanging — "execution will occur" + "day will be a surprise" = performative contradiction. Newcomb's paradox — "choice is free" + "choice is 99.9% predictable" = hidden tension.
**DIAGNOSTIC:** "Can all stated conditions be simultaneously true?"

### AP10: False dilemma — collapsing spectrum into binary
**НЕ ДЕЛАЙ:** Present only two options when more exist.
**ВМЕСТО:** Before accepting binary framing, ask: "Is there a spectrum? A third option? A 'both' or 'neither' or 'depends on conditions'?"
**ПРИМЕР:** "Is compound A a nucleophile or electrophile?" → ambident, depending on conditions. "Is this poem romantic or modernist?" → both, transitional work. "Was the policy a success or failure?" → mixed results by different metrics.
**DIAGNOSTIC:** "Are there really only two options, or have I artificially narrowed the field?"

### AP11: Reification — treating abstractions as concrete entities
**НЕ ДЕЛАЙ:** Assign agency, physical properties, or causal power to abstract concepts.
**ВМЕСТО:** Translate abstract language into concrete: WHO does what? WHAT mechanism operates?
**ПРИМЕР:** "Evolution designed the eye for seeing" → no designer; natural selection retained mutations that improved light sensitivity. "The market wants lower rates" → specific traders/institutions are pricing in rate cuts. "Intelligence requires X" → intelligence is not an agent with requirements.
**DIAGNOSTIC:** "Am I treating an abstraction as if it could act, want, or cause?"

### AP12: Overexplanation — analysis past usefulness
**НЕ ДЕЛАЙ:** Continue clarifying when sufficient depth already reached.
**ВМЕСТО:** Apply L4: is this clarification NEEDED for the task? If not → stop.
**ПРИМЕР:** 40-minute lecture answering a yes/no question. Defining every term in a simple arithmetic problem.
**DIAGNOSTIC:** "Is further clarification helping or obscuring?"

## DIAGNOSTIC PROBES (before finalizing output)

| # | Probe | If "no" → action |
|---|-------|-------------------|
| 1 | "Does every key term mean EXACTLY the same thing throughout?" | Fix equivocation — lock meanings explicitly. |
| 2 | "Would this definition distinguish X from the most similar Y?" | Sharpen — add differentia. |
| 3 | "Can I give a counterexample that breaks this definition?" | If yes → deepen. If no counterexample possible → suspiciously strong, check for circularity. |
| 4 | "Is my depth sufficient for THIS task?" | Compare achieved level vs required level. |
| 5 | "Have I verified rules with source=implied?" | If not → verify before passing to D3. |
| 6 | "Are all premises coherent — can all conditions be simultaneously true?" | If tension found → flag hidden contradiction. |
| 7 | "Am I EXPLAINING or just RECOGNIZING?" | If can't explain mechanism → still at nominal/dictionary level. |
| 8 | "Does my 'aha!' survive a stress test?" | Apply counterexample. If collapses → false insight. |
| 9 | "Does the alternative reading from D1 dissolve or persist after clarification?" | If persists → genuine ambiguity, must resolve or flag. |

**D6-in-D2:** The sufficiency criterion ("enough for the task") can be used to justify premature stopping. If the parallel observer detects "this feels clear enough" without verification → re-examine.

## READINESS

| Signal | Meaning | Action |
|--------|---------|--------|
| Key terms defined, tested, stable | D2 complete | Proceed to D3 |
| Term collapses under counterexample | Definition insufficient | Return to Step 1, deepen |
| "I know what this is" but can't explain | Nominal level only | Must reach functional |
| Vivid "got it!" without ability to defend | False insight | Test with counterexamples |
| D1 ambiguities still unresolved | D2 incomplete | Must resolve blocking ambiguities |

**Minimum threshold for exit:**
1. Key terms explicitly defined at required depth
2. Equivocation excluded (L1 verified)
3. Blocking ambiguities resolved
4. Hidden assumptions explicated
5. Rules with source=implied verified

**Extended criteria (beyond minimum):**
- Internal consistency — term doesn't contradict itself during reasoning
- Resistance to counterexamples — definition withstands testing
- Sufficiency for action — can work with the concept, make decisions, distinguish cases

## OUTPUT: REASONING PASSPORT — D2 Section

D2 reads the D1 section and fills the D2 section.

```
──── D2: CLARIFICATION ───────────────────────────

CLARIFIED ELEMENTS:
  E1: [original from D1]
      Definition:  [precise definition]
      Depth:       [nominal|dictionary|functional|essential]
      Scope IN:    [what counts]
      Scope OUT:   [what's excluded]
      Tool used:   [genus_diff|operational|extreme_cases|...]
  E2: [...]
      ...

AMBIGUITIES RESOLVED:
  A1: [from D1] → Resolved: [chosen reading] because [reason]
  A2: [from D1] → UNRESOLVED: [why, impact on downstream]

RULES VERIFIED:
  R1: [precise statement after verification]
      Status: [stated_verified|implied_verified|implied_rejected|needs_computation]
      Edge cases: [where might this break?]
  R2: [...]

HIDDEN CONTENT SURFACED:
  Presuppositions:     [what the question assumes without stating]
  Hidden constraints:  [domain knowledge not stated]
  Premise coherence:   [COHERENT | TENSION: description]

STATUS UPDATES:
  E1: [status_before] → [status_after] because [reason]
  ...

D1 GAPS FOUND: [elements D1 missed — flagged, NOT added]

CRITICAL CLARIFICATION: [single most important insight from D2]
DEPTH SUMMARY: [deepest level achieved, sufficient? Y/N]

D2 WELL-FORMEDNESS: [PASS/FAIL]
  ☐ Every key term defined at required depth
  ☐ No equivocation (L1 — meaning stable throughout)
  ☐ No definitional circularity
  ☐ All blocking ambiguities resolved
  ☐ Rules with source=implied verified
  ☐ Premise coherence checked
  ☐ Hidden assumptions explicated
  ☐ Counterexample test applied to definitions
  ☐ Depth matches task requirements
  ☐ D1 alternative reading addressed
  ☐ False insight check passed (explain, not just recognize)
  ☐ ERR structure extended, not replaced
```

## RULES FOR D2

1. Define every D1 element at depth Level 3+ for expert questions
2. Consume D1's ERR structure — extend it, don't replace it
3. Verify all rules, especially those with source="implied"
4. Lock meanings: each term = one meaning throughout (L1)
5. Resolve blocking ambiguities — select one reading, state why
6. State hidden assumptions and presuppositions explicitly
7. Check premise coherence — can all conditions be simultaneously true?
8. Test definitions with counterexamples — if collapse → deepen
9. If D1 missed something — flag in D1 GAPS, don't silently add
10. Do NOT select frameworks (D3)
11. Do NOT evaluate or compare (D4)
12. Do NOT draw conclusions (D5)
