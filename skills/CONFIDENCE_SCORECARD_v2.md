# Deterministic Confidence Scorecard v2

> **Principle:** Confidence is COMPUTED, not estimated. Each domain has a checklist of sub-elements with fixed point values. D6-Reflect evaluates each item, assigns score, and writes notes into the conspectus. Any sub-element below its iterate threshold triggers mandatory iteration.

## How It Works

1. After each domain output, D6-Reflect runs the domain's checklist
2. Each sub-element is scored according to its criterion
3. Notes are written into conspectus (rефлексия happens during scoring)
4. If ANY sub-element is below its iterate threshold → verdict = iterate
5. Domain score = sum of all sub-element scores (0-100)
6. Final confidence = weighted average of domain scores with hard cap overrides

## Domain Weights

| Domain | Weight | Rationale |
|--------|:------:|-----------|
| D1 Recognition | 0.10 | Foundation — errors propagate invisibly |
| D2 Clarification | 0.15 | Definitions determine all downstream quality |
| D3 Framework | 0.10 | Framework selection — critical but often straightforward |
| D4 Comparison | 0.35 | Actual analytical work happens here |
| D5 Inference | 0.30 | Conclusion and its justification |

## Zero-Gate Rule

If ERR is completely absent in any domain (no Elements, no Roles, no Rules), that domain score = 0.

---

# D1 RECOGNITION SCORECARD (100 points)

> **D1 Asymmetry Principle:** D1 errors are invisible to subsequent domains. D2 cannot clarify what D1 failed to register. Cost of iterate at D1 ≈ 30K tokens. Cost of propagated error ≈ 500K+ tokens wasted on wrong answer. Therefore: iterate thresholds are STRICT.

## F1: ERR Decomposition (19 points)

### F1.1 Elements identified (7 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Are ALL objects/entities/quantities from the problem text listed? | 3 | 3 = all traceable to text; 1 = ≥2 significant missed; 0 = Elements absent |
| Does each element have unique ID and content? | 2 | 2 = yes; 0 = no ID or content empty |
| Is Level (data/info/quality/character) specified for each? | 2 | 2 = yes; 1 = partial; 0 = no |

**Iterate trigger:** F1.1 < 7 (any gap = iterate)

**D6 notes:** _Which elements are missing? Compare with TL's your_components. Every missing element = blind spot for D2-D5._

### F1.2 Roles assigned (6 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Does each element have an assigned role? | 3 | 3 = all covered; 1 = ≥50%; 0 = roles absent |
| Role from correct enum (given/unknown/constraint-explicit/constraint-implicit/context/option)? | 2 | 2 = all from enum; 1 = present but arbitrary; 0 = no |
| Is there at least one unknown (what we're solving for)? | 1 | 1 = yes; 0 = no unknown → no problem |

**Iterate trigger:** F1.2 < 6 (incomplete roles = elements not understood)

**D6 notes:** _Element without role = orphan. Role not from enum = Worker doesn't understand element's function. No unknown = Worker doesn't understand what we're solving._

### F1.3 Rules identified (6 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Are laws/formulas/principles connecting elements identified? | 3 | 3 = ≥2 rules, each connects ≥2 elements; 1 = 1 rule; 0 = rules absent |
| Source specified (stated/implied/domain_knowledge)? | 2 | 2 = for each rule; 1 = partial; 0 = no |
| Implied/domain rules marked separately from stated? | 1 | 1 = clearly separated; 0 = no |

**Iterate trigger:** F1.3 < 6 (incomplete rules = connections between elements not established)

**D6 notes:** _Rule without source = unknown origin. Implied rule without marking = hidden assumption already in D1._

**ZERO-GATE:** If F1.1 + F1.2 + F1.3 all = 0 → D1 score = 0 (entire domain).

---

## F2: Hierarchical Depth (12 points)

### F2.1 Depth achieved (8 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| What level is extraction taken to? | 0-6 | Level 1 (Data)=0; Level 2 (Info)=2; Level 3 (Quality)=4; Level 4 (Character)=6 |
| For HLE/complex question — Level 3+ achieved? | 2 | 2 = yes; 0 = no |

**Iterate trigger:** F2.1 < 6 (Level ≤ 2 on HLE = guaranteed superficiality)

**D6 notes:** _Level 1-2 means Worker sees "what is written" but doesn't understand "how it works". D3 cannot select framework without Level 3 understanding._

### F2.2 Priority flag for higher-level differences (4 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Are differences checked at all 4 hierarchy levels? | 2 | 2 = explicitly noted; 0 = not checked |
| If higher-level difference found — marked as priority? | 2 | 2 = yes; 0 = no; N/A = 2 |

**Iterate trigger:** F2.2 < 2 (unchecked levels = may miss key difference)

**D6 notes:** _Higher-level difference has priority per L5. If Worker analyzes Level 1 details but missed Quality-level difference — all further work is built on wrong priority._

---

## F3: Status and Dependencies (10 points)

### F3.1 Status assigned (4 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Does each element have status? | 2 | 2 = all; 1 = ≥50%; 0 = no |
| Does status agree with role? | 2 | 2 = consistent; 1 = partial; 0 = contradictions |

**Iterate trigger:** F3.1 < 3 (status-role disagreement = logical conflict in foundation)

**D6 notes:** _Element with role=given but status=unknown = either role is wrong, or element is not actually given. Must resolve BEFORE D2._

### F3.2 Dependencies declared (3 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Is dependency graph built? | 1 | 1 = yes; 0 = no |
| Does each dependency have from/to/via-rule? | 1 | 1 = yes; 0 = no |
| Does graph cover all key elements? | 1 | 1 = all unknown and constrained in graph; 0 = disconnected nodes |

**Iterate trigger:** F3.2 < 2 (graph without via-rule = connections not justified)

**D6 notes:** _Unknown element not in graph = no path to determine it. How will D4 compute it?_

### F3.3 Acyclicity (3 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Is dependency graph checked for cycles? | 1 | 1 = checked; 0 = no |
| Is it acyclic? | 2 | 2 = acyclic; 0 = cycle found |

**Iterate trigger:** F3.3 < 3 (ALWAYS — cycle = logical defect)

**D6 notes:** _Cycle = circular reasoning in the foundation. If "A depends on B via R1" and "B depends on A via R2" — which rule is wrong?_

---

## F4: Key Challenge (14 points)

### F4.1 Key challenge identified (6 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Is key challenge formulated? | 2 | 2 = yes, separate field; 0 = no |
| Is it specific? (references elements/rules, not generic) | 2 | 2 = specific ("E3 depends on unresolved R2"); 1 = semi-specific; 0 = generic ("complex problem") |
| Does it point to structural bottleneck? | 2 | 2 = yes, bottleneck clear; 0 = descriptive but not bottleneck |

**Iterate trigger:** F4.1 < 4 (generic challenge → D3 selects wrong framework)

**D6 notes:** _"Solve the problem" is not a challenge. "E3 status=unknown depends on unresolved R2 which requires domain knowledge not stated" — that's a challenge. If TL's question_set doesn't match key challenge — who is right?_

### F4.2 Key challenge at Level 3+ (4 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Is challenge formulated at mechanism/principle level? | 4 | 4 = Level 3-4; 2 = Level 2; 0 = Level 1 |

**Iterate trigger:** F4.2 < 4 (for HLE mandatory)

**D6 notes:** _"Find the answer" = Level 1. "Determine which of two competing models fits" = Level 3. "Resolve tension between two structural principles" = Level 4._

### F4.3 Task type classified (4 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Task type from enum? | 2 | 2 = from enum; 0 = not specified |
| Task type justified? | 2 | 2 = justification referencing structure; 0 = just stated |

**Iterate trigger:** F4.3 < 2 (without task type → D3 doesn't know WHAT framework to search for)

**D6 notes:** _Task type determines entire D3. "computation" → D3 searches for formula. "proof" → D3 searches for theorem. Error here = error in framework._

---

## F5: Ambiguity Marking (21 points)

### F5.1 Ambiguities found (8 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Are ambiguities in the problem text found? | 3 | 3 = specific examples; 1 = "possibly some"; 0 = "none" (suspicious for HLE) |
| For each — ≥2 readings? | 3 | 3 = each with ≥2 readings; 1 = partial; 0 = no |
| Ambiguities NOT resolved (left for D2)? | 2 | 2 = all open; 0 = Worker chose a reading |

**Iterate trigger:** F5.1 < 6 (for HLE: incomplete ambiguities = missed trap)

**D6 notes:** _HLE questions ALWAYS contain ambiguities — that's their design. If Worker found 0 → anchoring (AP10). Command: "Name one way your reading could be WRONG."_

### F5.2 Severity assigned (5 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Does each ambiguity have severity? | 3 | 3 = all; 1 = partial; 0 = no |
| Are blocking ambiguities explicitly marked? | 2 | 2 = yes; 0 = no blocking flags |

**Iterate trigger:** F5.2 < 3 (ambiguity without severity = D2 doesn't know priority)

**D6 notes:** _Blocking = "D2 cannot choose definitions until this is resolved". Non-blocking = "can defer to D4". If Worker doesn't distinguish — D2 wastes time on non-blocking while missing blocking._

### F5.3 Alternative reading (4 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| ≥1 alternative reading of the entire problem? | 4 | 4 = concrete alternative; 2 = formal; 0 = none |

**Iterate trigger:** F5.3 < 4 (anti-anchoring — mandatory)

**D6 notes:** _No alternative reading = Worker is certain in a single reading. For HLE this is a red flag. Probe #9: "What ELSE could this be?"_

### F5.4 Directional FLAG (4 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| If process present → RULE_ORD extracted? | 2 | 2 = yes; 0 = process exists but ordering not extracted; N/A = 2 |
| If directional language → cross-referenced with RULE_ORD? | 2 | 2 = FLAG_DIRECTION on reverse; 0 = not checked; N/A = 2 |

**Iterate trigger:** F5.4 < 4 (if applicable)

**D6 notes:** _Q3 atom tracking: D1 correctly flagged → D2 misresolved. RULE_ORD = structural fact (L5), not interpretation. If FLAG_DIRECTION set → record: "D2 MUST NOT close this flag without PROVEN resolution."_

---

## F6: Implicit Assumptions (17 points)

### F6.1 Implicit constraints surfaced (7 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Are implicit constraints listed? | 3 | 3 = specific list with domain source; 1 = "possibly some"; 0 = none |
| Domain source specified? | 2 | 2 = yes ("chemistry: balanced equation assumed"); 0 = no source |
| Checked "What seems OBVIOUS but isn't stated"? | 2 | 2 = explicit check with result; 0 = not checked |

**Iterate trigger:** F6.1 < 5 (incomplete implicit constraints = hidden assumptions in foundation)

**D6 notes:** _Each implicit constraint → question: "If this is WRONG, how does the answer change?" If answer changes → CRITICAL implicit assumption, mark for D2._

### F6.2 Missing data identified (5 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Is standard information checked? | 2 | 2 = checked units, boundaries, domain; 0 = no |
| Are consequences of missing data marked? | 3 | 3 = "missing X → answer depends on assumption Y"; 1 = listed, no consequence; 0 = none |

**Iterate trigger:** F6.2 < 3 (missing data without consequences = hidden dependencies)

**D6 notes:** _Missing data = place where Worker MUST make an assumption. Each such place = potential error. Record in conspectus for D2 verification._

### F6.3 Explicit vs implicit separated (5 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| constraint-explicit and constraint-implicit separated in Roles? | 3 | 3 = clearly; 0 = all in one bucket |
| Implicit marked "flagged for D2 verification"? | 2 | 2 = yes; 0 = accepted as given |

**Iterate trigger:** F6.3 < 3 (mixed constraints = unverified assumptions in foundation)

**D6 notes:** _Implicit constraint without "needs verification" marking = already became an axiom. Worker will build everything on it without questioning._

---

## F7: Well-formedness (7 points)

### F7.1 ERR hierarchy check (3 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Rules→Roles→Elements hierarchy respected? | 1 | 1 = yes; 0 = no |
| No elements at multiple hierarchy levels? | 1 | 1 = yes; 0 = violation |
| All 5 checks passed? | 1 | 1 = all true; 0 = at least one false |

**Iterate trigger:** F7.1 < 3 (ALWAYS — structural defect)

**D6 notes:** _ERR hierarchy failure = Rules don't determine Roles, or Roles don't distinguish Elements. Fundamental defect — Worker doesn't understand the problem structure._

### F7.2 No phantoms (2 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Is each element traceable to the problem text? | 2 | 2 = all traceable; 0 = phantom exists |

**Iterate trigger:** F7.2 < 2 (ALWAYS — phantom = false data in foundation)

**D6 notes:** _Phantom = Worker added something not in the problem. For each element: "Quote the fragment of problem text." If cannot → phantom → delete._

### F7.3 No deformation (2 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Are formulations faithful to the original? | 2 | 2 = yes; 1 = minor shifts; 0 = significant distortion |

**Iterate trigger:** F7.3 < 1 (significant distortion = working on a different problem)

**D6 notes:** _Compare key terms with original literally. "Improve transit" ≠ "ban cars". "Copper carbonate" ≠ "basic copper carbonate". Shift = object deformation._

---

## D1 Summary Table

| ID | Sub-element | Max | Iterate if < |
|----|-------------|:---:|:------------:|
| **F1 ERR (19)** | | | |
| F1.1 | Elements identified | 7 | **7** |
| F1.2 | Roles assigned | 6 | **6** |
| F1.3 | Rules identified | 6 | **6** |
| **F2 Depth (12)** | | | |
| F2.1 | Depth achieved | 8 | **6** |
| F2.2 | Priority flag | 4 | **2** |
| **F3 Status/Deps (10)** | | | |
| F3.1 | Status assigned | 4 | **3** |
| F3.2 | Dependencies | 3 | **2** |
| F3.3 | Acyclicity | 3 | **3** |
| **F4 Key Challenge (14)** | | | |
| F4.1 | Key challenge | 6 | **4** |
| F4.2 | Challenge depth | 4 | **4** |
| F4.3 | Task type | 4 | **2** |
| **F5 Ambiguity (21)** | | | |
| F5.1 | Ambiguities found | 8 | **6** |
| F5.2 | Severity assigned | 5 | **3** |
| F5.3 | Alternative reading | 4 | **4** |
| F5.4 | Directional FLAG | 4 | **4*** |
| **F6 Assumptions (17)** | | | |
| F6.1 | Implicit constraints | 7 | **5** |
| F6.2 | Missing data | 5 | **3** |
| F6.3 | Explicit/implicit split | 5 | **3** |
| **F7 Form (7)** | | | |
| F7.1 | ERR hierarchy | 3 | **3** |
| F7.2 | No phantoms | 2 | **2** |
| F7.3 | No deformation | 2 | **1** |
| | **TOTAL** | **100** | |

*F5.4 — iterate only if applicable (question has directional structure)

**Rules:**
- **Zero-Gate:** F1.1 + F1.2 + F1.3 all = 0 → D1 score = 0
- **Iterate:** ANY sub-element below its threshold → iterate (no exceptions)
- **14 of 21** sub-elements have strict iterate thresholds
- **D6 notes** for each sub-element are written into conspectus during scoring

---

# D2 CLARIFICATION SCORECARD (100 points)

> **D2 Error Pattern:** D2 is the origin of the two most expensive errors in our data. Q1 FeCl3: D2 introduced ASSUMED premise as certain → 100% confidence on wrong model. Q3 Atom tracking: D2 closed D1 flag with CONDITIONAL proof → pipeline went blind. Therefore: Proof Chain Protocol and Flag Resolution have the highest weights.

## F1: ERR Consumption & Extension (9 points)

### F1.1 D1 ERR consumed (5 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Are all D1 elements addressed in clarified_elements? | 3 | 3 = ≥90% D1 elements; 1 = 50-89%; 0 = <50% |
| Is ERR structure preserved (extended, not restructured)? | 2 | 2 = extended only; 0 = restructured/replaced |

**Iterate trigger:** F1.1 < 5 (skipped elements = D1 work lost)

**D6 notes:** _Each D1 element must have corresponding clarification. If element skipped — D2 ignored it. If ERR restructured — D1 information lost._

### F1.2 D1 gaps flagged (4 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| If D2 found new elements — are they in d1_gaps (not smuggled)? | 2 | 2 = in d1_gaps; 0 = silently added to clarified_elements |
| Status updates documented (before→after with reason)? | 2 | 2 = all; 1 = partial; 0 = no |

**Iterate trigger:** F1.2 < 2 (smuggled elements = silent corruption of D1)

**D6 notes:** _Silently added element = Worker bypassed D1 control. Every new element must be in d1_gaps for TL review._

---

## F2: Definition Depth (13 points)

### F2.1 Key terms at Level 3+ (8 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Key terms (elements with role=unknown or constraint) at Level 3+? | 4 | 4 = all key at 3+; 2 = ≥50%; 0 = most at Level 1-2 |
| Depth level explicitly stated for each clarified element? | 2 | 2 = yes; 0 = no |
| Elements at Level <3 — flagged as insufficient? | 2 | 2 = yes; 0 = accepted without flag |

**Iterate trigger:** F2.1 < 6 (shallow definitions on HLE = D3 cannot select correct framework)

**D6 notes:** _Level 1-2 definition = Worker knows the word but not the mechanism. "Star = bright dot" vs "Star = H→He fusion equilibrium". For HLE need mechanism._

### F2.2 Scope defined (5 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| scope_in and scope_out defined for key elements? | 3 | 3 = both for all key; 1 = only scope_in; 0 = no |
| Can element be distinguished from SIMILAR concept? | 2 | 2 = distinction power clear; 0 = definition doesn't distinguish X from similar Y |

**Iterate trigger:** F2.2 < 3 (without scope = equivocation risk)

**D6 notes:** _Q2 copper: "copper carbonate" scope_in = CuCO3, scope_out = Cu2(OH)2CO3. Without scope → equivocation → overthinking._

---

## F3: Rule Verification (13 points)

### F3.1 Rules verified (7 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Each D1 rule verified (stated_verified/implied_verified/implied_unverified/needs_computation)? | 3 | 3 = all; 1 = partial; 0 = no |
| Implied rules checked — actually applicable in THIS context? | 2 | 2 = checked; 0 = accepted as-is |
| Conditions and edge_cases specified? | 2 | 2 = for each rule; 1 = partial; 0 = no |

**Iterate trigger:** F3.1 < 5 (unverified rules = building on sand)

**D6 notes:** _Implied rule with verification="implied_unverified" = potential bomb. Each such rule → question for D4: "Does this rule ACTUALLY hold here?"_

### F3.2 Precise statements (6 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Each rule has precise_statement (more exact than D1)? | 3 | 3 = yes; 1 = partial; 0 = copy-paste from D1 |
| Applicability conditions (domain, range, exceptions) specified? | 3 | 3 = conditions explicit; 1 = partial; 0 = no |

**Iterate trigger:** F3.2 < 3 (copy-paste rules = D2 added no value)

**D6 notes:** _If precise_statement = D1 original → D2 didn't clarify the rule. "Balanced equation" → "Balanced equation: conservation of mass and charge, stoichiometric coefficients are smallest integers" = real clarification._

---

## F4: Proof Chain Protocol (18 points)

### F4.1 Proof chains present (6 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Every derivation/proof in D2 structured as proof chain? | 3 | 3 = all; 1 = some; 0 = free-text proofs |
| Each step has statement + justification + assumes + status? | 3 | 3 = complete structure; 1 = partial; 0 = no |

**Iterate trigger:** F4.1 < 6 (free-text proof = impossible to audit assumptions)

**D6 notes:** _Proof without explicit assumptions = "trust me". TL cannot check what is ASSUMED vs PROVEN. FeCl3 case: "By charge balance, MCl2" — one step without assumptions → wrong answer at 100%._

### F4.2 Assumption statuses correct (6 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Each assumption classified (PROVEN/IMPORTED/ASSUMED/CONDITIONAL)? | 3 | 3 = all classified; 1 = partial; 0 = no |
| PROVEN only for what is literally stated in question text or derived from D1 ERR? | 3 | 3 = strict; 0 = PROVEN applied to domain knowledge or inference |

**Iterate trigger:** F4.2 < 6 (misclassified assumptions = false confidence in conclusions)

**D6 notes:** _PROVEN = "where in the question text does it say this?" If Worker answers domain knowledge → that's IMPORTED, not PROVEN. FeCl3: "displacement reaction" was ASSUMED, not PROVEN._

### F4.3 Conclusion strength and if_wrong (6 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| conclusion_strength determined by weakest step? | 2 | 2 = yes; 0 = conclusion stronger than warranted |
| if_wrong field present and specific? | 2 | 2 = specific alternative; 0 = absent or generic |
| CONDITIONAL conclusions explicitly marked as such? | 2 | 2 = yes; 0 = CONDITIONAL presented as certain |

**Iterate trigger:** F4.3 < 4 (missing if_wrong = Worker hasn't considered failure mode)

**D6 notes:** _if_wrong is THE most important field. "If A1 is false, chloride could be MCl3" = opens D3 to consider alternative. Without it → D3 has only one path._

---

## F5: D1 Flag Resolution (16 points)

### F5.1 All D1 flags addressed (6 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Each D1 flag has entry in d1_flag_resolution? | 3 | 3 = all; 1 = partial; 0 = flags ignored |
| Resolution status (resolved/open) + basis specified? | 3 | 3 = yes; 0 = no |

**Iterate trigger:** F5.1 < 6 (ignored D1 flags = wasted D1 work)

**D6 notes:** _D1 flags are the most valuable D1 output. Ignoring them = ignoring the sentinel. Q3: D1 flagged directionality → D2 "resolved" → WRONG._

### F5.2 CONDITIONAL proofs don't close flags (6 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| If flag resolved — basis is PROVEN (all steps from question text)? | 3 | 3 = all resolved flags have PROVEN basis; 0 = any flag closed by CONDITIONAL |
| If basis = CONDITIONAL → flag explicitly stays OPEN? | 3 | 3 = yes, OPEN with note; 0 = closed despite CONDITIONAL |

**Iterate trigger:** F5.2 < 6 (ALWAYS — CONDITIONAL closure = the #1 error pattern in our data)

**D6 notes:** _THIS IS THE CRITICAL CHECK. Q3 atom tracking: flag closed by CONDITIONAL proof = pipeline went blind. Q1 FeCl3: proof CONDITIONAL but treated as certain. If ANY flag closed by CONDITIONAL → REOPEN and ITERATE._

### F5.3 Open flags forwarded (4 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Open flags listed as active constraints for D3-D5? | 2 | 2 = explicitly forwarded; 0 = mentioned but not forwarded |
| Impact of each open flag on downstream stated? | 2 | 2 = "if FLAG_X resolves as A → answer Y; if B → answer Z"; 0 = no impact stated |

**Iterate trigger:** F5.3 < 2 (flags not forwarded = lost)

**D6 notes:** _Open flag without downstream impact statement = nobody knows why it matters. State the CONSEQUENCE of each resolution direction._

---

## F6: Ambiguity Protocol (14 points)

### F6.1 Enumerate → Test → Branch/Commit (8 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| For each D1 ambiguity: ALL viable readings enumerated? | 3 | 3 = yes; 1 = some; 0 = jumped to one reading |
| Each reading tested against context? | 3 | 3 = yes with specific reasoning; 1 = generic test; 0 = no |
| Decision: COMMIT with reason why alternative is WRONG, or BRANCH with open_hypotheses? | 2 | 2 = proper decision; 0 = silent resolution |

**Iterate trigger:** F6.1 < 6 (premature closure = D2 failure mode)

**D6 notes:** _"Since obviously X..." = premature closure. "X because alternative Y violates L1 in that..." = proper COMMIT. "Both X and Y viable, branching" = proper BRANCH._

### F6.2 Branching quality (6 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| If BRANCH: each hypothesis has id/interpretation/basis/implications/test? | 3 | 3 = complete; 1 = partial; 0 = listed but no structure; N/A = 3 |
| If COMMIT: stated why alternative is WRONG (not just "less natural")? | 3 | 3 = specific reason; 1 = "more natural"; 0 = no reason; N/A = 3 |

**Iterate trigger:** F6.2 < 3 (weak branch/commit = ambiguity not actually resolved)

**D6 notes:** _COMMIT with "more natural" is NOT sufficient. Natural ≠ correct. Q3: "shared atoms" reading was "more natural" but WRONG. Need: "alternative violates [specific principle]"._

---

## F7: Hidden Assumptions (12 points)

### F7.1 Assumption register (7 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| hidden_assumptions array non-empty? | 2 | 2 = yes with specifics; 0 = empty |
| Each assumption classified (from proof chains or independently found)? | 3 | 3 = all classified; 1 = listed but unclassified; 0 = no |
| "What would change if this assumption is wrong?" stated? | 2 | 2 = consequence for each; 0 = no consequence |

**Iterate trigger:** F7.1 < 5 (no hidden assumptions on HLE = almost certainly missing something)

**D6 notes:** _Every HLE question has hidden assumptions. "No hidden assumptions found" on HLE = Worker isn't looking hard enough. Probe: "Name one thing you're assuming that the question doesn't state."_

### F7.2 Hypothesis space completeness (5 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Does hypothesis set cover ALL structurally distinct possibilities? | 3 | 3 = yes; 1 = main cases; 0 = single hypothesis |
| Checked: same entity in different states? Degenerate cases? Negation? | 2 | 2 = explicitly checked; 0 = no |

**Iterate trigger:** F7.2 < 3 (incomplete hypothesis space = blind to correct answer)

**D6 notes:** _FeCl3 case: Worker assumed A ≠ M. But A = M with different oxidation states = comproportionation = correct answer. Missing structural category = missing the answer._

---

## F8: Failure Mode Check (5 points)

### F8.1 Failure modes verified (5 points)

| Question | Points | Criterion |
|----------|:------:|-----------|
| Equivocation check: terms used identically throughout? | 1 | 1 = checked; 0 = not |
| Premature closure check: flagged ambiguities properly handled? | 1 | 1 = checked; 0 = not |
| Circularity check: no definition refers to itself? | 1 | 1 = checked; 0 = not |
| Depth mismatch: depth matches task complexity? | 1 | 1 = checked; 0 = not |
| conditional_flag_closure: no D1 flags closed by CONDITIONAL? | 1 | 1 = checked; 0 = not |

**Iterate trigger:** F8.1 < 3 (≥3 unchecked failure modes = safety net missing)

**D6 notes:** _Failure mode check = last line of defense. If equivocation detected → iterate with "Term X used as Y in D1 but as Z in D2 — which is correct?"_

---

## D2 Summary Table

| ID | Sub-element | Max | Iterate if < |
|----|-------------|:---:|:------------:|
| **F1 ERR Consumption (9)** | | | |
| F1.1 | D1 ERR consumed | 5 | **5** |
| F1.2 | D1 gaps flagged | 4 | **2** |
| **F2 Definition Depth (13)** | | | |
| F2.1 | Key terms Level 3+ | 8 | **6** |
| F2.2 | Scope defined | 5 | **3** |
| **F3 Rule Verification (13)** | | | |
| F3.1 | Rules verified | 7 | **5** |
| F3.2 | Precise statements | 6 | **3** |
| **F4 Proof Chain (18)** | | | |
| F4.1 | Proof chains present | 6 | **6** |
| F4.2 | Assumption statuses correct | 6 | **6** |
| F4.3 | Conclusion strength + if_wrong | 6 | **4** |
| **F5 Flag Resolution (16)** | | | |
| F5.1 | All D1 flags addressed | 6 | **6** |
| F5.2 | CONDITIONAL don't close flags | 6 | **6** |
| F5.3 | Open flags forwarded | 4 | **2** |
| **F6 Ambiguity Protocol (14)** | | | |
| F6.1 | Enumerate→Test→Branch/Commit | 8 | **6** |
| F6.2 | Branching quality | 6 | **3** |
| **F7 Hidden Assumptions (12)** | | | |
| F7.1 | Assumption register | 7 | **5** |
| F7.2 | Hypothesis space completeness | 5 | **3** |
| **F8 Failure Modes (5)** | | | |
| F8.1 | Failure modes verified | 5 | **3** |
| | **TOTAL** | **100** | |

**Rules:**
- **16 of 18** sub-elements have strict iterate thresholds
- **F5.2** (CONDITIONAL flag closure) is the single most critical check — responsible for both Q1 and Q3 errors
- **F4** (Proof Chain Protocol) has the highest weight (18) — unstructured proofs are the root cause of overconfidence
- **D6 notes** for each sub-element are written into conspectus during scoring

---

# D3 FRAMEWORK SELECTION SCORECARD (100 points)

**Source:** `skills/d3-framework.md` (L2 Objectivity, Dual Criterion, Theory Chain, Alternatives, Branch Propagation)

**Error data context:**
- Marble Q: Single framework (symmetry) selected without alternatives → answer locked to h(0)=1/2; 3:1 asymmetry never examined
- Fe+FeCl₃: Framework "simple displacement" selected, comproportionation never considered as alternative
- Continuum: Framework assumed cl(int(A)) connected without branching

## Functions and Weights

| # | Function | Rel. Weight | 100-pt Weight | Rationale |
|---|----------|-------------|---------------|-----------|
| F1 | Framework selection (named, dual criterion) | 8 | **16** | Core task of D3 — naming the framework and justifying via Dual Criterion |
| F2 | L2 Objectivity test | 6.5 | **13** | If solver is not ready to accept ANY answer, framework is biased |
| F3 | Theory Chain (step-by-step derivation) | 12 | **24** | Highest weight — the chain connecting framework to answer structure IS D3's primary product |
| F4 | Alternatives considered | 8 | **16** | Marble error: no alternatives = no cross-verification in D4 |
| F5 | D4 Instructions (criteria + branches) | 9 | **18** | D3 produces instructions for D4 — if poor, D4 runs blind |
| F6 | Branch propagation (D2 hypotheses) | 6.5 | **13** | Fe+FeCl₃ error: D2 branch collapsed silently in D3 |
| | **TOTAL** | 50 | **100** | |

## F1: Framework Selection (16 points)

### F1.1 Framework named + Dual Criterion stated (6 points)

| Points | Criterion |
|--------|-----------|
| 0 | No framework named or just vague "analysis" |
| 2 | Framework named but no Dual Criterion justification |
| 4 | Framework named + one of (Structural / Epistemic) criterion stated |
| 6 | Framework named + BOTH Structural AND Epistemic criteria explicitly stated |

**Iterate threshold:** < 4 (framework without justification is guesswork)

**D6 note:** "Is the framework selection EARNED by Dual Criterion, or was it the first thing that came to mind?"

### F1.2 Complexity level identified (4 points)

| Points | Criterion |
|--------|-----------|
| 0 | No complexity assessment |
| 2 | Complexity acknowledged but no level assigned |
| 4 | Explicit complexity level identified (L1-L4 per d3 instruction) |

**Iterate threshold:** < 2

**D6 note:** "Does the complexity level match the actual structure of the problem? Over-simplification = D4 blind spots."

### F1.3 Criteria for D4 defined (6 points)

| Points | Criterion |
|--------|-----------|
| 0 | No criteria for D4 evaluation |
| 2 | Vague criteria ("check if it works") |
| 4 | Specific criteria listed but incomplete (< 3 criteria) |
| 6 | Complete criteria set (≥ 3 specific, testable criteria for D4 comparison) |

**Iterate threshold:** < 4 (D4 needs concrete criteria to operate)

**D6 note:** "If D4 receives these criteria, can it produce a verdict for EVERY element? Or are some elements uncovered?"

## F2: L2 Objectivity Test (13 points)

### F2.1 Objectivity test performed (8 points)

| Points | Criterion |
|--------|-----------|
| 0 | No objectivity test |
| 2 | Test mentioned but not actually performed |
| 4 | Test performed: "Am I ready to accept ANY answer?" — but no alternatives listed |
| 6 | Test performed with at least 1 alternative answer the solver is willing to accept |
| 8 | Test performed with explicit statement of what evidence would make solver CHANGE the framework |

**Iterate threshold:** < 4 (unverified objectivity = anchoring risk)

**D6 note:** "What evidence would DISPROVE this framework? If you cannot name it, you are not objective — you are committed."

### F2.2 Hierarchy of objectivity (5 points)

| Points | Criterion |
|--------|-----------|
| 0 | No hierarchy consideration |
| 2 | Subject-Object distinction acknowledged |
| 5 | Full L2 hierarchy: observation level identified, what is Subject vs Object in THIS analysis clearly stated |

**Iterate threshold:** — (non-critical, informational)

**D6 note:** "Is the solver confusing their model of the problem with the problem itself?"

## F3: Theory Chain (24 points)

### F3.1 Theory chain present and complete (8 points)

| Points | Criterion |
|--------|-----------|
| 0 | No theory chain |
| 2 | Informal narrative of how framework connects to answer |
| 4 | Numbered steps but gaps in logical connection |
| 6 | Complete chain: each step follows from previous, no gaps |
| 8 | Complete chain + each step tagged with justification source (domain knowledge / axiom / D2 output) |

**Iterate threshold:** < 6 (incomplete theory chain = unjustified framework)

**D6 note:** "Can you trace from Step 1 to final prediction without invoking unstated premises? If any step requires 'and obviously...' — that's a gap."

### F3.2 Assumptions explicitly listed (8 points)

| Points | Criterion |
|--------|-----------|
| 0 | No assumptions listed |
| 2 | Some assumptions mentioned inline |
| 4 | Assumptions collected in one place but not categorized |
| 6 | Assumptions categorized: PROVEN (from D1/D2) / IMPORTED (domain) / ASSUMED |
| 8 | Categorized + each IMPORTED/ASSUMED has "if_wrong" consequence stated |

**Iterate threshold:** < 6 (uncategorized assumptions = hidden failure modes)

**D6 note:** "Each ASSUMED step is a branch point. If it were false, what answer would follow? This IS the alternative path."

### F3.3 Theoretical prediction stated (8 points)

| Points | Criterion |
|--------|-----------|
| 0 | No prediction |
| 2 | Vague prediction ("framework should give us the answer") |
| 4 | Specific prediction of answer FORM (e.g., "answer will be a point group symbol") |
| 6 | Prediction of answer form + constraints (e.g., "must be a subgroup of D2d") |
| 8 | Prediction of form + constraints + at least one TESTABLE prediction D4 can verify |

**Iterate threshold:** < 4 (D3 must produce something D4 can test)

**D6 note:** "Does the prediction make a FALSIFIABLE claim? If D4 can only CONFIRM but never DENY, the framework is unfalsifiable."

## F4: Alternatives Considered (16 points)

### F4.1 Alternative frameworks listed (10 points)

| Points | Criterion |
|--------|-----------|
| 0 | No alternatives considered |
| 3 | One alternative mentioned but dismissed without analysis |
| 5 | One alternative with reason for rejection |
| 7 | Two+ alternatives with reasons for rejection |
| 10 | Two+ alternatives + explicit comparison criterion for why selected framework is preferred |

**Iterate threshold:** < 5 (Marble error: zero alternatives = answer locked to single method)

**D6 note:** "If THIS framework fails in D4, what is Plan B? If you cannot name one, you have no fallback — paradigm shift will be blind."

### F4.2 Framework limitations stated (6 points)

| Points | Criterion |
|--------|-----------|
| 0 | No limitations |
| 2 | Vague acknowledgment ("may not cover all cases") |
| 4 | Specific limitation identified with domain reference |
| 6 | Specific limitation + what evidence in D4 would trigger switching to alternative |

**Iterate threshold:** < 2

**D6 note:** "What class of problems does this framework handle BADLY? Is the current problem in that class?"

## F5: D4 Instructions (18 points)

### F5.1 Explicit instructions for D4 (10 points)

| Points | Criterion |
|--------|-----------|
| 0 | No D4 instructions |
| 3 | Generic instruction ("verify the answer") |
| 5 | Specific instructions with 1-2 checks listed |
| 7 | Specific instructions with 3+ checks including at least one numerical/computational test |
| 10 | Full d4_instructions block: criteria list + specific computations + expected results + what-to-do-if-mismatch |

**Iterate threshold:** < 5 (D4 without instructions = unguided search)

**D6 note:** "If D4 Worker reads ONLY these instructions (no other context), can they perform a meaningful verification? Instructions must be self-contained."

### F5.2 Branch instructions for D4 (8 points)

| Points | Criterion |
|--------|-----------|
| 0 | No branch handling |
| 2 | Mentions "if alternative..." vaguely |
| 4 | For each open hypothesis: what D4 should compute under EACH branch |
| 6 | Branch-specific computations + comparison metric to choose between branches |
| 8 | Full branch protocol: each hypothesis gets independent D4 verification + convergence/divergence criterion |

**Iterate threshold:** < 4 (if D2 had open hypotheses that reached D3)

**D6 note:** "Are branches getting PARALLEL treatment or is one branch getting all the attention? Unequal treatment = silent hypothesis collapse."

## F6: Branch Propagation (13 points)

### F6.1 D2 hypotheses consumed (7 points)

| Points | Criterion |
|--------|-----------|
| 0 | D2 hypotheses ignored |
| 2 | D2 hypotheses mentioned but not integrated into framework |
| 4 | Each D2 hypothesis addressed — some resolved with justification, others propagated |
| 7 | Each D2 hypothesis explicitly: RESOLVED (with PROVEN basis) or PROPAGATED (framework handles both) or BRANCHED (separate framework per hypothesis) |

**Iterate threshold:** < 4 (Fe+FeCl₃ error: D2 branch collapsed in D3 without justification)

**D6 note:** "For each 'resolved' hypothesis: is the resolution PROVEN or CONDITIONAL? CONDITIONAL resolutions must propagate, not resolve."

### F6.2 No silent collapse (6 points)

| Points | Criterion |
|--------|-----------|
| 0 | D2 had open hypotheses and D3 output shows only one path without explanation |
| 3 | D3 acknowledges multiple paths but works only one in detail |
| 6 | ALL open hypotheses from D2 are either explicitly resolved (PROVEN basis) or carried as parallel tracks |

**Iterate threshold:** < 3 (silent collapse = the exact error pattern from Fe+FeCl₃ and Continuum)

**D6 note:** "Count the hypotheses entering D3 vs. leaving D3. If fewer leave, WHERE did each one die and was the death PROVEN?"

## Summary Table

| Sub-element | Description | Max | Iterate < |
|-------------|-------------|-----|-----------|
| **F1 Framework selection (16)** | | | |
| F1.1 | Named + Dual Criterion | 6 | **4** |
| F1.2 | Complexity level | 4 | **2** |
| F1.3 | Criteria for D4 | 6 | **4** |
| **F2 L2 Objectivity (13)** | | | |
| F2.1 | Objectivity test | 8 | **4** |
| F2.2 | Hierarchy of objectivity | 5 | — |
| **F3 Theory Chain (24)** | | | |
| F3.1 | Chain present + complete | 8 | **6** |
| F3.2 | Assumptions listed | 8 | **6** |
| F3.3 | Theoretical prediction | 8 | **4** |
| **F4 Alternatives (16)** | | | |
| F4.1 | Alternative frameworks | 10 | **5** |
| F4.2 | Limitations stated | 6 | **2** |
| **F5 D4 Instructions (18)** | | | |
| F5.1 | Explicit instructions | 10 | **5** |
| F5.2 | Branch instructions | 8 | **4** |
| **F6 Branch propagation (13)** | | | |
| F6.1 | D2 hypotheses consumed | 7 | **4** |
| F6.2 | No silent collapse | 6 | **3** |
| | **TOTAL** | **100** | |

**Rules:**
- **12 of 14** sub-elements have strict iterate thresholds
- **F3** (Theory Chain) has the highest weight (24) — the theory chain IS D3's primary product, unstructured framework selection causes downstream failure
- **F6** (Branch propagation) is the primary guard against the Fe+FeCl₃ pattern — D2 hypotheses must not die silently in D3
- **F4.1** (Alternatives) directly addresses the Marble error — zero alternatives = answer locked to single method
- **Zero-Gate:** If F1.1 = 0 AND F3.1 = 0 (no framework named AND no theory chain) → D3 score = 0

---

# D4 COMPARISON SCORECARD (100 points)

**Source:** `skills/d4-compare.md` (Aristotle's Rules, L4 Sufficient Reason, Empirical Claims, Cross-Verification)

**Error data context:**
- Fe+FeCl₃: D4 computed 3.68% mass balance error — should be 0.00% for stoichiometry. Accepted as "rounding." The error meant the structural model was WRONG.
- Point group Q1: Unverified empirical claim ("meso isomer preferred") selected wrong isomer. Source: none.
- Marble: Single method (first-step analysis with symmetry), no cross-verification. Answer 1/2 never challenged.
- Continuum: Assumed cl(int(A)) connected — empirical claim imported without proof.

## Functions and Weights

| # | Function | Rel. Weight | 100-pt Weight | Rationale |
|---|----------|-------------|---------------|-----------|
| F1 | Criteria coverage (systematicity) | 7 | **14** | D3 criteria must be applied to ALL elements, not just convenient ones |
| F2 | Computation/derivation trace | 9 | **18** | D4 is where the work happens — trace must be complete and verifiable |
| F3 | Aristotle's Three Rules | 4 | **8** | Guards against comparing apples to oranges |
| F4 | Empirical claims audit (L4) | 10 | **20** | Highest weight — unverified empirical claims caused Q1, Continuum errors |
| F5 | Disconfirming evidence | 8 | **16** | Fe+FeCl₃: 3.68% error was DISCONFIRMING evidence, rationalized away |
| F6 | Cross-verification | 7 | **14** | Marble: single method = no safety net |
| F7 | ERR status updates | 3 | **5** | Tracking what changed — less critical but necessary |
| F8 | Failure mode check | 2.5 | **5** | Meta-check for systematic biases |
| | **TOTAL** | 50.5 | **100** | |

## F1: Criteria Coverage (14 points)

### F1.1 Every criterion applied to every relevant element (8 points)

| Points | Criterion |
|--------|-----------|
| 0 | No systematic coverage — random elements checked |
| 2 | Some criteria applied to some elements |
| 4 | All criteria applied but to subset of elements |
| 6 | All criteria applied to all elements, but superficially (1-2 sentences each) |
| 8 | All criteria × all elements, each with substantive analysis |

**Iterate threshold:** < 4 (selective comparison = biased comparison)

**D6 note:** "Which element-criterion pair got the LEAST attention? That's where the error is hiding."

### F1.2 MC options fully tested (6 points)

| Points | Criterion |
|--------|-----------|
| 0 | Only "correct" answer examined (N/A for non-MC: auto 6) |
| 2 | Correct answer + 1 alternative tested |
| 4 | All options tested but some with cursory analysis |
| 6 | Every MC option tested with equal rigor — status: eliminated/viable/confirmed with reason |

**Iterate threshold:** < 4 (if MC question)

**D6 note:** "Did you spend 5x effort on the 'obvious' answer vs. alternatives? Equal rigor = honest comparison."

## F2: Computation/Derivation Trace (18 points)

### F2.1 Step-by-step computation shown (10 points)

| Points | Criterion |
|--------|-----------|
| 0 | No computation shown — just final answer |
| 3 | Partial trace with gaps ("by simplification...") |
| 5 | Most steps shown but some skipped |
| 7 | Complete trace — every algebraic/logical step explicit |
| 10 | Complete trace + intermediate results named and referenceable |

**Iterate threshold:** < 5 (for computation/proof tasks; N/A for classification/explanation)

**D6 note:** "Can a reader verify each step independently? If any step requires 'trust me' — that's a gap."

### F2.2 Numerical verification attempted (8 points)

| Points | Criterion |
|--------|-----------|
| 0 | No numerical check |
| 3 | Partial verification (checked one intermediate value) |
| 5 | End result verified by substitution or dimensional analysis |
| 8 | Independent numerical computation (Python/calculator) used to verify analytical result |

**Iterate threshold:** < 3 (for quantitative tasks)

**D6 note:** "Analytical errors survive symbolic manipulation. Numbers don't lie — plug in and check."

## F3: Aristotle's Three Rules (8 points)

### F3.1 Three rules verified (8 points)

| Points | Criterion |
|--------|-----------|
| 0 | No Aristotle check |
| 3 | One rule checked |
| 5 | Two rules checked |
| 7 | All three checked (same relation, same criterion, same state) |
| 8 | All three checked + any violations identified and addressed |

**Iterate threshold:** < 5

**D6 note:** "Are you comparing peak performance of one approach to average performance of another? That's a same-state violation."

## F4: Empirical Claims Audit (20 points)

### F4.1 Every empirical claim sourced (10 points)

| Points | Criterion |
|--------|-----------|
| 0 | Empirical claims made without any sourcing |
| 3 | Some claims sourced, some asserted as "known" |
| 5 | All claims tagged with source type (from_question / domain_knowledge / unverified) |
| 7 | All claims sourced + domain_knowledge claims specify WHAT knowledge |
| 10 | All claims sourced + unverified claims have impact_if_wrong traced |

**Iterate threshold:** < 5 (Point group Q1: unsourced "meso preferred" killed the answer)

**D6 note:** "For each 'domain_knowledge' source: would a specialist in this field AGREE this is consensus? Or is it one interpretation among several?"

### F4.2 Empirical dependency flagged (10 points)

| Points | Criterion |
|--------|-----------|
| 0 | Answer depends on unverified empirical claims but no flag |
| 3 | Dependency acknowledged but no confidence impact noted |
| 5 | Dependency flagged + confidence cap noted for D5 |
| 7 | Dependency flagged + cap noted + alternative outcomes if claim wrong |
| 10 | Full empirical audit: all claims sourced, dependencies traced, caps set, alternatives documented |

**Iterate threshold:** < 5 (the ENTIRE confidence system depends on honest empirical flagging)

**D6 note:** "If this empirical claim were reversed, would the answer change? If YES — that is the vulnerability, not the reasoning."

## F5: Disconfirming Evidence (16 points)

### F5.1 Active search for disconfirming evidence (10 points)

| Points | Criterion |
|--------|-----------|
| 0 | No disconfirming evidence sought |
| 3 | Token mention ("no contradictions found") |
| 5 | Specific disconfirming evidence identified and analyzed |
| 7 | Multiple pieces of disconfirming evidence + assessment of each |
| 10 | Systematic adversarial search: "What evidence would prove me WRONG?" — with specific tests |

**Iterate threshold:** < 5 (Fe+FeCl₃: 3.68% error WAS disconfirming evidence, ignored)

**D6 note:** "The 3.68% error was the answer screaming at you. What is this problem's equivalent? What number doesn't fit?"

### F5.2 Numerical mismatch treated as signal (6 points)

| Points | Criterion |
|--------|-----------|
| 0 | Numerical mismatch present but rationalized ("acceptable rounding") |
| 2 | Mismatch noted but not investigated |
| 4 | Mismatch investigated — source of error identified |
| 6 | Mismatch triggers model re-examination: "This suggests the structural model is wrong" |

**Iterate threshold:** < 2 (for exact-answer tasks: stoichiometry, combinatorics, integer sequences)

**D6 note:** "In EXACT-answer domains, ANY nonzero error = wrong model, not wrong arithmetic. 3.68% is not rounding — it's a different reaction."

## F6: Cross-Verification (14 points)

### F6.1 Alternative method attempted (8 points)

| Points | Criterion |
|--------|-----------|
| 0 | Single method only |
| 2 | Mentions "could also try..." without doing it |
| 4 | Partial alternative method (started but not completed) |
| 6 | Complete alternative method — result compared with primary |
| 8 | Complete alternative method + agreement/disagreement explicitly documented |

**Iterate threshold:** < 4 (Marble error: single method locked answer)

**D6 note:** "A second method that AGREES is evidence. A second method that DISAGREES is a gift — it reveals the error."

### F6.2 Edge cases / boundary checks (6 points)

| Points | Criterion |
|--------|-----------|
| 0 | No edge cases checked |
| 2 | One edge case checked |
| 4 | Multiple edge cases + degenerate cases checked |
| 6 | Edge cases + limit behavior + symmetry check performed |

**Iterate threshold:** < 2

**D6 note:** "Does the formula work at n=0? At n→∞? At the boundary? If not, it's wrong everywhere."

## F7: ERR Status Updates (5 points)

### F7.1 Status changes tracked (5 points)

| Points | Criterion |
|--------|-----------|
| 0 | No status tracking |
| 2 | Some elements updated |
| 5 | Every element has before/after status: unknown→known, uncommitted→constrained, etc. |

**Iterate threshold:** — (informational, not critical)

**D6 note:** "What is STILL unknown after D4? Those unknowns become uncertainty in D5."

## F8: Failure Mode Check (5 points)

### F8.1 Systematic bias check (5 points)

| Points | Criterion |
|--------|-----------|
| 0 | No bias check |
| 2 | One failure mode checked |
| 5 | Selective comparison + false equivalence + confirmation bias all checked |

**Iterate threshold:** — (informational)

**D6 note:** "If you found ZERO failure modes, you probably didn't look hard enough."

## Summary Table

| Sub-element | Description | Max | Iterate < |
|-------------|-------------|-----|-----------|
| **F1 Criteria coverage (14)** | | | |
| F1.1 | Every criterion × every element | 8 | **4** |
| F1.2 | MC options fully tested | 6 | **4** |
| **F2 Computation trace (18)** | | | |
| F2.1 | Step-by-step shown | 10 | **5** |
| F2.2 | Numerical verification | 8 | **3** |
| **F3 Aristotle's Rules (8)** | | | |
| F3.1 | Three rules verified | 8 | **5** |
| **F4 Empirical claims (20)** | | | |
| F4.1 | Every claim sourced | 10 | **5** |
| F4.2 | Dependency flagged | 10 | **5** |
| **F5 Disconfirming evidence (16)** | | | |
| F5.1 | Active adversarial search | 10 | **5** |
| F5.2 | Mismatch = signal | 6 | **2** |
| **F6 Cross-verification (14)** | | | |
| F6.1 | Alternative method | 8 | **4** |
| F6.2 | Edge/boundary checks | 6 | **2** |
| **F7 ERR status updates (5)** | | | |
| F7.1 | Status changes tracked | 5 | — |
| **F8 Failure mode check (5)** | | | |
| F8.1 | Systematic bias check | 5 | — |
| | **TOTAL** | **100** | |

**Rules:**
- **10 of 13** sub-elements have strict iterate thresholds
- **F4** (Empirical claims) has the highest weight (20) — unverified empirical claims are THE primary source of overconfidence in the error data
- **F5** (Disconfirming evidence) is the guard against the Fe+FeCl₃ pattern: numerical mismatch = wrong model
- **F6** (Cross-verification) guards against Marble pattern: single method = no safety net
- **Zero-Gate:** If F2.1 = 0 AND F4.1 = 0 (no computation trace AND no empirical sourcing) → D4 score = 0

---

# D5 INFERENCE SCORECARD (100 points)

**Source:** `skills/d5-infer.md` (L5 Direction, Certainty Marking, Cross-Verification, Honesty Requirements, Empirical Caps)

**Error data context:**
- Point group Q1: Certainty 85% on wrong answer — had S4 in hand, chose D2 instead. L5 reversal: picked answer first, rationalized.
- Atom tracking Q3: Certainty 97% with active D1 flag still unresolved — no honest marking.
- Marble: Certainty claimed high despite single method — no cross-verification applied.
- Fe+FeCl₃: Correct answer never considered because D2 proof locked the model — injected premise propagated unchallenged.

## Functions and Weights

| # | Function | Rel. Weight | 100-pt Weight | Rationale |
|---|----------|-------------|---------------|-----------|
| F1 | Inference chain (explicit, traceable) | 10 | **20** | The inference chain IS D5's product — must be auditable |
| F2 | L5 Direction check | 7 | **14** | Guards against rationalization — conclusion FROM evidence, not evidence FOR conclusion |
| F3 | Certainty marking (honest) | 6 | **12** | Q1 (85% wrong), Q3 (97% wrong) — overconfidence is THE error |
| F4 | Four Honesty Requirements | 7 | **14** | Correspondence, marking, withhold, accept — systematic honesty audit |
| F5 | Cross-verification | 10 | **20** | Highest weight — Marble error: single method = undetectable error |
| F6 | Empirical dependency caps applied | 5 | **10** | Q1: binary empirical choice without data = should cap at 60% |
| F7 | Premise traceability (no injected premises) | 5 | **10** | Fe+FeCl₃: D2 false proof became an injected premise in D5 |
| | **TOTAL** | 50 | **100** | |

## F1: Inference Chain (20 points)

### F1.1 Chain present and explicit (10 points)

| Points | Criterion |
|--------|-----------|
| 0 | No inference chain — just states answer |
| 3 | Informal narrative ("since X and Y, the answer is Z") |
| 5 | Numbered steps but some inferential gaps |
| 7 | Complete chain: P1 + P2 + Rule → intermediate → ... → Conclusion, no gaps |
| 10 | Complete chain + every premise tagged with source (D4 finding ID / D2 rule / D3 framework) |

**Iterate threshold:** < 5 (untraced inference = unjustified conclusion)

**D6 note:** "Can you remove ANY step without breaking the chain? If yes, it's a real dependency. If no, the step may be decorative, not logical."

### F1.2 Chain completeness (10 points)

| Points | Criterion |
|--------|-----------|
| 0 | Major logical gaps — conclusion doesn't follow from premises |
| 3 | Some steps justified, but at least one non-sequitur |
| 5 | All steps justified, but some justifications are weak ("obviously...") |
| 7 | All steps justified with specific reasoning, no "obviously" |
| 10 | All steps justified + the chain is MINIMAL — no unnecessary premises, no circular dependencies |

**Iterate threshold:** < 5

**D6 note:** "Does the chain contain any step that says 'clearly' or 'obviously'? Those words hide inferential gaps."

## F2: L5 Direction Check (14 points)

### F2.1 Direction check performed (8 points)

| Points | Criterion |
|--------|-----------|
| 0 | No direction check |
| 2 | Mentioned but not actually performed |
| 4 | Performed: "premises → conclusion" direction confirmed |
| 6 | Performed + explicit statement of what evidence LED to this conclusion |
| 8 | Performed + red team: "Could I have started with this answer and selected evidence for it?" — answered honestly |

**Iterate threshold:** < 4 (L5 reversal = rationalization, the most dangerous D5 failure)

**D6 note:** "If someone showed you ONLY the answer and asked you to find supporting evidence, would you find exactly the evidence you cited? If yes — you may have reasoned backwards."

### F2.2 Structural constraints respected (6 points)

| Points | Criterion |
|--------|-----------|
| 0 | Structural constraints from D2/D4 overridden without justification |
| 2 | Constraints acknowledged but reinterpreted |
| 4 | Constraints respected — no reinterpretation |
| 6 | Constraints respected + if challenged, done via escape valve (D1/D2 return, not reinterpretation) |

**Iterate threshold:** < 4 (Q3 Atom tracking: D5 overrode L5 ordering with linguistic argument)

**D6 note:** "Is there any structural constraint from D2 that you're 'softening' in D5? L5 ordering cannot be softened — it can only be wrong at its source."

## F3: Certainty Marking (12 points)

### F3.1 Certainty type correct (6 points)

| Points | Criterion |
|--------|-----------|
| 0 | No certainty type stated |
| 2 | Certainty type stated but mismatched (e.g., "necessary" without complete proof) |
| 4 | Correct type (necessary only if deductive proof, probabilistic for most HLE) |
| 6 | Correct type + explicit justification of why THIS type (not a different one) |

**Iterate threshold:** < 4

**D6 note:** "'Necessary' means denial produces contradiction. Can you write the contradiction? If not, it's probabilistic."

### F3.2 Confidence level calibrated (6 points)

| Points | Criterion |
|--------|-----------|
| 0 | No confidence stated or wildly miscalibrated (95%+ with open issues) |
| 2 | Confidence stated but not justified |
| 4 | Confidence stated + justified by evidence strength and coverage |
| 6 | Confidence stated + justified + explicitly reduced for: open flags, unverified empirical claims, single method, D4 gaps |

**Iterate threshold:** < 4 (Q1: 85% wrong, Q3: 97% wrong — calibration is THE problem)

**D6 note:** "List every reason your confidence should be LOWER. If the list has 3+ items, your stated confidence is too high."

## F4: Four Honesty Requirements (14 points)

### F4.1 Correspondence (4 points)

| Points | Criterion |
|--------|-----------|
| 0 | Conclusion says more than evidence supports |
| 2 | Conclusion approximately matches evidence |
| 4 | Conclusion EXACTLY matches evidence — no overreach, no underreach |

**Iterate threshold:** < 2

**D6 note:** "Does the conclusion claim precision that the evidence doesn't support? (e.g., exact value when D4 gave approximation)"

### F4.2 Marking (3 points)

| Points | Criterion |
|--------|-----------|
| 0 | Certainty type not marked or mismarked |
| 3 | Certainty type marked correctly and consistently |

**Iterate threshold:** < 3 (binary: either marked or not)

### F4.3 Withhold (4 points)

| Points | Criterion |
|--------|-----------|
| 0 | Conclusion extends beyond evidence (hidden generalization) |
| 2 | Some restraint but still minor overreach |
| 4 | Conclusion strictly limited to what evidence supports — no extrapolation |

**Iterate threshold:** < 2

**D6 note:** "What does the conclusion NOT claim? Explicit withholding is a sign of intellectual honesty."

### F4.4 Accept (3 points)

| Points | Criterion |
|--------|-----------|
| 0 | Earned conclusion rejected because "it can't be right" |
| 3 | All earned conclusions accepted, including uncomfortable ones |

**Iterate threshold:** < 3 (binary: either accepts earned conclusions or doesn't)

**D6 note:** "If the math says 4 and intuition says 5 — go with the math. Then check the math."

## F5: Cross-Verification (20 points)

### F5.1 Sanity checks performed (6 points)

| Points | Criterion |
|--------|-----------|
| 0 | No sanity checks |
| 2 | One check (e.g., range only) |
| 4 | Three+ checks from: range, limit, symmetry, dimensional, magnitude |
| 6 | All applicable checks performed + suspicious results flagged |

**Iterate threshold:** < 4 (sanity checks are cheap and catch gross errors)

**D6 note:** "Symmetry check: if the answer is ≈1/2 for an asymmetric problem, WHY? Suspicious symmetry = possible error."

### F5.2 Alternative method attempted (8 points)

| Points | Criterion |
|--------|-----------|
| 0 | No alternative method |
| 2 | Alternative mentioned but not executed |
| 4 | Alternative partially executed |
| 6 | Alternative fully executed, result compared |
| 8 | Alternative fully executed + agreement/disagreement documented + confidence adjusted |

**Iterate threshold:** < 4 (Marble error: single method = no safety net)

**D6 note:** "NOT 'redo carefully' — DIFFERENT method entirely. Generating functions vs. direct counting. Coordinates vs. synthetic geometry."

### F5.3 Disagreement handling (6 points)

| Points | Criterion |
|--------|-----------|
| 0 | Two methods disagree and one is silently dropped |
| 2 | Disagreement noted but not investigated |
| 4 | Disagreement investigated, source of error identified |
| 6 | Disagreement fully resolved: error found in one method, or BOTH answers reported with confidence cap |

**Iterate threshold:** < 4 (if methods disagree)

**D6 note:** "If two methods agree — that's evidence (uncapped). If they disagree — that's a gift revealing an error (cap 50%)."

## F6: Empirical Dependency Caps (10 points)

### F6.1 Caps correctly applied (6 points)

| Points | Criterion |
|--------|-----------|
| 0 | D4 flagged empirical dependency but D5 ignores it (no cap) |
| 2 | Cap mentioned but wrong value |
| 4 | Correct cap applied per D5 instruction table |
| 6 | Correct cap + cap rationale stated + confidence reflects the cap |

**Iterate threshold:** < 4 (if D4 flagged empirical dependency)

**D6 note:** "Q1 Point group: binary empirical choice → cap at 60%. Any confidence above 60% for an unverified binary choice is overconfidence."

### F6.2 Open flags reduce confidence (4 points)

| Points | Criterion |
|--------|-----------|
| 0 | Open D1/D2 flags present but confidence not reduced |
| 2 | Open flags acknowledged in narrative but no quantitative reduction |
| 4 | Each open flag explicitly reduces confidence by stated amount |

**Iterate threshold:** < 2 (Q3: 97% with active D1 flag = system failure)

**D6 note:** "Count open flags. Each one is an unresolved risk. Confidence cannot be 90%+ with active flags."

## F7: Premise Traceability (10 points)

### F7.1 Every premise from D1-D4 (6 points)

| Points | Criterion |
|--------|-----------|
| 0 | Multiple premises without D1-D4 source |
| 2 | Most premises traced, 1-2 untraced |
| 4 | All premises traced to specific D4 findings |
| 6 | All premises traced + tagged with D-domain source (D4 finding #X, D2 rule #Y) |

**Iterate threshold:** < 4

**D6 note:** "Any premise that appears 'out of nowhere' is an injected premise — it may be correct, but it's unverified."

### F7.2 No injected premises (4 points)

| Points | Criterion |
|--------|-----------|
| 0 | Injected premises present and unacknowledged |
| 2 | Injected premises acknowledged and flagged |
| 4 | Zero injected premises — everything traceable to D1-D4 |

**Iterate threshold:** < 2

**D6 note:** "Fe+FeCl₃: the 'proof' that M is divalent was an injected premise from D2. It felt like established fact by D5. Was it?"

## Summary Table

| Sub-element | Description | Max | Iterate < |
|-------------|-------------|-----|-----------|
| **F1 Inference chain (20)** | | | |
| F1.1 | Chain present + explicit | 10 | **5** |
| F1.2 | Chain completeness | 10 | **5** |
| **F2 L5 Direction (14)** | | | |
| F2.1 | Direction check performed | 8 | **4** |
| F2.2 | Structural constraints respected | 6 | **4** |
| **F3 Certainty marking (12)** | | | |
| F3.1 | Certainty type correct | 6 | **4** |
| F3.2 | Confidence calibrated | 6 | **4** |
| **F4 Honesty requirements (14)** | | | |
| F4.1 | Correspondence | 4 | **2** |
| F4.2 | Marking | 3 | **3** |
| F4.3 | Withhold | 4 | **2** |
| F4.4 | Accept | 3 | **3** |
| **F5 Cross-verification (20)** | | | |
| F5.1 | Sanity checks | 6 | **4** |
| F5.2 | Alternative method | 8 | **4** |
| F5.3 | Disagreement handling | 6 | **4** |
| **F6 Empirical caps (10)** | | | |
| F6.1 | Caps correctly applied | 6 | **4** |
| F6.2 | Open flags reduce confidence | 4 | **2** |
| **F7 Premise traceability (10)** | | | |
| F7.1 | Every premise from D1-D4 | 6 | **4** |
| F7.2 | No injected premises | 4 | **2** |
| | **TOTAL** | **100** | |

**Rules:**
- **17 of 17** sub-elements have strict iterate thresholds — D5 is the final gate, everything matters
- **F5** (Cross-verification) and **F1** (Inference chain) share highest weight (20 each) — traceable reasoning + independent verification are the two pillars
- **F6** guards against the systematic overconfidence seen in ALL error cases (85%, 97%, 90% on wrong answers)
- **F4.4** (Accept) is a specific guard against the "it can't be right" reflex — if the math says 4, go with 4
- **Zero-Gate:** If F1.1 = 0 AND F2.1 = 0 (no inference chain AND no direction check) → D5 score = 0

---

# Aggregation Formula

**Principle: The chain is as strong as its weakest link.**

```
C_final = min(D1_score, D2_score, D3_score, D4_score, D5_score, TL_score)
```

A single weak domain collapses the entire score. This is intentional:
- A brilliant D4 cannot compensate for a D2 that closed a flag with a CONDITIONAL proof
- A perfect D5 inference chain is worthless if D1 missed a key element
- High TL quality means nothing if D3 selected the wrong framework

Hard cap overrides applied after min-aggregation (see section below).

# Hard Cap Overrides

Hard caps are **structural overrides** applied AFTER the weighted aggregation. They represent conditions where no amount of good reasoning in other domains can compensate for a specific vulnerability.

## Cap Table

| # | Condition | Cap | Rationale | Error Source |
|---|-----------|-----|-----------|-------------|
| HC1 | D4 empirical dependency: binary choice, unverified | **60%** | Binary empirical choice without data = coin flip + reasoning | Q1 Point group |
| HC2 | D4 empirical dependency: multi-way choice, unverified | **75%** | More options = less likely to be wrong by chance, but still guessing | — |
| HC3 | D5 two methods disagree | **50%** | At least one method is wrong — which one? | Marble |
| HC4 | D5 single method, no cross-verification feasible | **75%** | No independent check = hidden error possible | Marble |
| HC5 | D5 sanity check fails | **60%** | Gross error detected | — |
| HC6 | D1/D2 flag still OPEN at D5 | **max(C_final − 15 × N_flags, 40%)** | Each open flag = unresolved risk | Q3 Atom tracking |
| HC7 | D2 proof chain CONDITIONAL used to close D1 flag | **60%** | Flag closed by weak proof = phantom resolution | Fe+FeCl₃, Continuum |
| HC8 | D4 numerical mismatch in exact-answer domain | **40%** | Nonzero error in stoichiometry/combinatorics = wrong model | Fe+FeCl₃ |
| HC9 | D3 zero alternatives considered | **70%** | No fallback framework = no paradigm shift possible | Marble |
| HC10 | D5 injected premise (untraced to D1-D4) present | **65%** | Unverified external premise = uncontrolled risk | Fe+FeCl₃ |

## Application Rules

1. **Multiple caps stack by MINIMUM**: if HC1 (60%) and HC4 (75%) both apply → final cap = 60%
2. **Caps are applied AFTER min-aggregation**: C_raw = min(all domains) → C_final = min(C_raw, applicable caps)
3. **Caps are LOGGED**: every applied cap must be recorded with its condition and resulting value
4. **Caps cannot be overridden** by high domain scores — they represent structural vulnerabilities

## Full Scoring Pipeline

```
Step 1: Score each domain (D1-D5, TL) using checklists → D1_raw ... D5_raw, TL_raw (0-100 each)
Step 2: Per-domain iterate check — if any sub-element < threshold → iterate that domain
Step 3: Per-domain Zero-Gate — if gate conditions met → D_score = 0
Step 4: Aggregate: C_raw = min(D1, D2, D3, D4, D5, TL)
Step 5: Identify all applicable Hard Caps → C_cap = min(all applicable caps)
Step 6: C_final = min(C_raw, C_cap)
Step 7: Log: C_final, all domain scores, weakest domain, all applied caps, all D6 notes
```

## Domain Zero-Gates (Summary)

| Domain | Zero-Gate Condition | Effect |
|--------|-------------------|--------|
| D1 | F1.1 + F1.2 + F1.3 all = 0 (no ERR at all) | D1_score = 0 |
| D2 | F1.1 = 0 AND F2.1 = 0 (no ERR consumption AND no definitions) | D2_score = 0 |
| D3 | F1.1 = 0 AND F3.1 = 0 (no framework named AND no theory chain) | D3_score = 0 |
| D4 | F2.1 = 0 AND F4.1 = 0 (no computation AND no empirical sourcing) | D4_score = 0 |
| D5 | F1.1 = 0 AND F2.1 = 0 (no inference chain AND no direction check) | D5_score = 0 |

## Confidence Interpretation Bands

| C_final | Interpretation | Action |
|---------|---------------|--------|
| 90-100 | Very high confidence | Answer likely correct; still verify with caps |
| 75-89 | High confidence | Good answer; note any open caps |
| 60-74 | Moderate confidence | Answer plausible but vulnerabilities present |
| 40-59 | Low confidence | Significant unresolved issues; consider iterate or paradigm shift |
| 0-39 | Very low / structural failure | Do not submit; fundamental re-examination needed |

---

# TL/D6 META-OPERATOR SCORECARD (100 points)

**Source:** `skills/analyze-v2.md` (TL role), `skills/d6-ask.md` (questioning), `skills/d6-reflect.md` (reflection)

**Nature:** TL/D6 is NOT a domain — it is the meta-operator that MANAGES the pipeline and EVALUATES domain outputs. This scorecard evaluates the quality of TL's management, not domain content. TL score ENTERS the C_final aggregation as an equal participant in `min()` — because a weak TL means weak verification of ALL domains, and the system is only as strong as its weakest element.

**Error data context:**
- Fe+FeCl₃: TL gave D2 proof 100% confidence without decomposing proof steps → didn't catch CONDITIONAL status
- Marble: TL pre-solved h(0)=1/2 in D3 reflect → Worker confirmation-biased all verification
- Q3 Atom: TL accepted D2's flag resolution without checking CONDITIONAL → flag lost
- All cases: TL failed to route iterate to the correct domain (D4/D5 re-ran, but error was in D2/D3)

## Functions and Weights

| # | Function | Rel. Weight | 100-pt Weight | Rationale |
|---|----------|-------------|---------------|-----------|
| F1 | Question Analysis (Phase 0) | 6 | **12** | Foundation — wrong decomposition = wrong pipeline |
| F2 | Per-domain verification quality | 12.5 | **25** | Highest — TL's core job is verifying Worker output |
| F3 | Anti-pre-solving discipline | 7.5 | **15** | Marble error: TL contamination → Worker confirmation bias |
| F4 | Conspectus quality | 6.5 | **13** | Source of truth — wrong conspectus = wrong downstream |
| F5 | Convergence control | 10 | **20** | Routing iterate to wrong domain = wasted iteration |
| F6 | Final answer quality | 7.5 | **15** | Answer must be EARNED, confidence must be CALIBRATED |
| | **TOTAL** | 50 | **100** | |

## F1: Question Analysis — Phase 0 (12 points)

### F1.1 Question structure identified (6 points)

| Points | Criterion |
|--------|-----------|
| 0 | No question analysis — jumped straight to D1 |
| 2 | Gefragte identified but befragte/erfragte missing |
| 4 | All three identified + classification (goal, complexity, task_type) |
| 6 | All three + classification + your_components (independent structural view for D1 comparison) |

**Iterate threshold:** < 4

**D6 note:** "Does the erfragte specify the EXACT FORM of the answer? If not, Worker may answer a different question."

### F1.2 Sub-question decomposition quality (6 points)

| Points | Criterion |
|--------|-----------|
| 0 | No decomposition — single monolithic question to Worker |
| 2 | Some sub-questions but vague routing |
| 4 | Sub-questions with domain routing + serves_root stated |
| 6 | Complete decomposition: sub-questions pass composition test (all answered → root answered) + attention directives |

**Iterate threshold:** < 2

**D6 note:** "Composition test: if ALL sub-questions answered perfectly, is the root answered? If not, a sub-question is missing."

## F2: Per-Domain Verification Quality (25 points)

### F2.1 Readiness criteria checked per domain (10 points)

| Points | Criterion |
|--------|-----------|
| 0 | No readiness check — output accepted without verification |
| 3 | Checked 1-2 domains, skipped others |
| 5 | All domains checked but superficially (generic "looks good") |
| 7 | All domains checked against specific criteria from analyze-v2 verification table |
| 10 | All domains checked + specific issues identified + iterate triggered where needed |

**Iterate threshold:** < 5 (TL that doesn't verify = pipeline without quality control)

**D6 note:** "Did you check D4 computation against D3 criteria? Did you verify D5 chain traces back to D4? Or did you rubber-stamp?"

### F2.2 Proof chain audit at D2 (8 points)

| Points | Criterion |
|--------|-----------|
| 0 | D2 proof accepted without decomposition (Fe+FeCl₃ pattern) |
| 2 | Proof acknowledged but not decomposed into steps |
| 4 | Proof decomposed: steps identified with assumption types |
| 6 | Steps identified + CONDITIONAL/ASSUMED assumptions flagged + conclusion strength assessed |
| 8 | Full audit: decomposed + flagged + conclusion_strength correct + if_wrong traced + D1 flag impact assessed |

**Iterate threshold:** < 4 (the Fe+FeCl₃ error started here — TL accepting unaudited proof)

**D6 note:** "Is this proof PROVEN or CONDITIONAL? If you cannot answer immediately, you haven't audited it."

### F2.3 D1 flag resolution audit (7 points)

| Points | Criterion |
|--------|-----------|
| 0 | D1 flags not tracked through pipeline |
| 2 | Flags mentioned in conspectus but resolution not checked |
| 4 | Each flag checked: resolved (with basis) or open |
| 7 | Each flag checked + CONDITIONAL resolutions kept OPEN + open flags forwarded as constraints to D3-D5 |

**Iterate threshold:** < 4 (Q3 Atom: flag closed by CONDITIONAL proof = pipeline went blind)

**D6 note:** "Count flags entering D2 vs. leaving D2. If any died, HOW? PROVEN death or CONDITIONAL death?"

## F3: Anti-Pre-Solving Discipline (15 points)

### F3.1 No candidate answers in D1-D3 reflects (10 points)

| Points | Criterion |
|--------|-----------|
| 0 | TL stated candidate answer or numerical result in D1-D3 reflect (Marble pattern) |
| 3 | TL hinted at answer direction ("this looks like it should be X") |
| 5 | TL discussed approach without stating candidate answer |
| 7 | TL used only questions and meta-cognitive instructions |
| 10 | TL used only questions + explicitly caught and removed any self-computation |

**Iterate threshold:** < 5 (TL pre-solving = Worker confirmation bias in D4-D5)

**D6 note:** "Scan your D1-D3 reflect messages: do they contain ANY specific numerical value, formula evaluation, or resolved interpretation? If yes, Worker will inherit it as anchor."

### F3.2 Instructions are questions, not solutions (5 points)

| Points | Criterion |
|--------|-----------|
| 0 | Instructions contain "the answer is..." or "this means..." |
| 2 | Instructions mostly questions but some directive statements |
| 5 | All instructions are questions or meta-cognitive directives ("verify X", "check whether Y") |

**Iterate threshold:** < 2

**D6 note:** "'Worker, verify that h(0)=1/2' = pre-solving. 'Worker, compute h(0) from the recurrence' = proper instruction."

## F4: Conspectus Quality (13 points)

### F4.1 Updated after every domain output (5 points)

| Points | Criterion |
|--------|-----------|
| 0 | Conspectus not maintained or rarely updated |
| 2 | Updated after some domains, gaps in others |
| 5 | Updated after EVERY domain output — no exceptions |

**Iterate threshold:** < 3

**D6 note:** "Conspectus is the source of truth. If it's stale, downstream domains get stale context."

### F4.2 Domain summaries accurate and concise (5 points)

| Points | Criterion |
|--------|-----------|
| 0 | Summaries missing or inaccurate |
| 2 | Summaries present but incomplete (key findings missing) |
| 3 | Summaries accurate — key findings, elements, confidence captured |
| 5 | Accurate + concise (< 200 words per domain) + flags and open issues tracked |

**Iterate threshold:** < 2

**D6 note:** "Does the conspectus capture what D2 actually concluded, or what you think D2 should have concluded?"

### F4.3 Open issues tracked (3 points)

| Points | Criterion |
|--------|-----------|
| 0 | No open issues section |
| 1 | Open issues exist but stale / not updated |
| 3 | Open issues actively maintained — added, resolved, forwarded as needed |

**Iterate threshold:** — (informational)

**D6 note:** "Open issues at pipeline end = unresolved risks. Each reduces confidence."

## F5: Convergence Control (20 points)

### F5.1 Iterate decisions correct (10 points)

| Points | Criterion |
|--------|-----------|
| 0 | Never iterated despite quality issues (rubber-stamped all outputs) |
| 3 | Iterated but inconsistently — some poor outputs passed |
| 5 | Iterated when domain scorecard showed sub-threshold elements |
| 7 | Iterated correctly + stated specific reason (which sub-element failed) |
| 10 | Iterated correctly + reason stated + iterate improved the output (not a wasted cycle) |

**Iterate threshold:** < 5

**D6 note:** "Did you iterate on the RIGHT thing? 'Output seems incomplete' ≠ diagnosis. 'F4.1 scored 3/10 because empirical claims unsourced' = diagnosis."

### F5.2 Routing to correct domain (5 points)

| Points | Criterion |
|--------|-----------|
| 0 | Routed iterate to wrong domain (Marble pattern: error in D2/D3, re-ran D4/D5) |
| 2 | Routing approximately correct but not optimal |
| 5 | Reverse diagnostic performed: traced error to EARLIEST broken domain, iterated there |

**Iterate threshold:** < 2 (Marble: TL re-ran D4/D5 but error was in D2/D3 symmetry model)

**D6 note:** "D5 wrong → check D4 → check D3 → check D2 → check D1. Fix the EARLIEST broken domain."

### F5.3 Paradigm shift management (5 points)

| Points | Criterion |
|--------|-----------|
| 0 | Stalled (2+ iterations without progress) but no paradigm shift attempted |
| 2 | Paradigm shift attempted but poorly targeted |
| 5 | Paradigm shift correctly triggered: stall detected, constraint "different from previous" applied, D3-D5 re-run |

**Iterate threshold:** — (N/A if no stall occurred — auto 5)

**D6 note:** "If confidence plateaued for 2+ iterations, did you try a different framework? Or did you keep iterating the same approach?"

## F6: Final Answer Quality (15 points)

### F6.1 Answer earned by evidence chain (8 points)

| Points | Criterion |
|--------|-----------|
| 0 | Answer stated without reference to pipeline outputs |
| 3 | Answer references D5 conclusion but not the chain |
| 5 | Answer traces through D4→D5 with key evidence cited |
| 8 | Answer fully justified: D1 elements → D2 clarifications → D3 framework → D4 evidence → D5 inference → final answer |

**Iterate threshold:** < 5

**D6 note:** "Can you trace the answer back to D1? If any link is missing, the answer isn't earned — it's asserted."

### F6.2 Confidence calibrated via scorecard (7 points)

| Points | Criterion |
|--------|-----------|
| 0 | Confidence is subjective ("feels about 85%") — no scorecard |
| 2 | Some scorecard elements checked |
| 4 | Full scorecard applied: D1-D5 scores computed, hard caps checked |
| 7 | Full scorecard + hard caps + caps logged + C_final computation shown + interpretation band stated |

**Iterate threshold:** < 4 (the ENTIRE purpose of this scorecard system is to replace subjective confidence)

**D6 note:** "If C_final = 85 but you 'feel' 95 — trust the scorecard. If C_final = 60 but you 'feel' 85 — trust the scorecard. The scorecard is the instrument; your feeling is the bias."

## Summary Table

| Sub-element | Description | Max | Iterate < |
|-------------|-------------|-----|-----------|
| **F1 Question Analysis (12)** | | | |
| F1.1 | Question structure identified | 6 | **4** |
| F1.2 | Sub-question decomposition | 6 | **2** |
| **F2 Per-domain verification (25)** | | | |
| F2.1 | Readiness criteria checked | 10 | **5** |
| F2.2 | Proof chain audit at D2 | 8 | **4** |
| F2.3 | D1 flag resolution audit | 7 | **4** |
| **F3 Anti-pre-solving (15)** | | | |
| F3.1 | No candidate answers in D1-D3 | 10 | **5** |
| F3.2 | Questions not solutions | 5 | **2** |
| **F4 Conspectus quality (13)** | | | |
| F4.1 | Updated after every output | 5 | **3** |
| F4.2 | Summaries accurate | 5 | **2** |
| F4.3 | Open issues tracked | 3 | — |
| **F5 Convergence control (20)** | | | |
| F5.1 | Iterate decisions correct | 10 | **5** |
| F5.2 | Routing to correct domain | 5 | **2** |
| F5.3 | Paradigm shift management | 5 | — |
| **F6 Final answer (15)** | | | |
| F6.1 | Answer earned by evidence | 8 | **5** |
| F6.2 | Confidence via scorecard | 7 | **4** |
| | **TOTAL** | **100** | |

**Rules:**
- **12 of 14** sub-elements have strict iterate thresholds
- **F2** (Per-domain verification) has the highest weight (25) — TL's core job is quality control of Worker outputs
- **F3.1** (Anti-pre-solving) directly addresses the Marble pattern: TL stated answer → Worker confirmation-biased
- **F2.2** (Proof chain audit) and **F2.3** (Flag audit) directly address Fe+FeCl₃ and Q3 patterns
- **F5.2** (Routing) addresses the iterate-to-wrong-domain pattern
- **TL score enters C_final via min()** — weak TL = weak verification of ALL domains
- **Zero-Gate:** If F2.1 = 0 AND F6.1 = 0 (no verification AND no earned answer) → TL score = 0
