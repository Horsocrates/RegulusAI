"""
Regulus AI - Unified Auditor
==============================

Single LLM call that parses a reasoning trace, maps segments to domains (D1-D6),
and checks structural gates (ERR, Levels, Order) for each domain.

Handles three trace formats:
- FULL_COT: Identify literal D1-D6 sections in raw chain-of-thought
- SUMMARY: Infer domain coverage from condensed thinking summary
- NONE: Audit the final answer only (no reasoning trace)
"""

import hashlib
import json
import re
from typing import Optional

from regulus.llm.client import LLMClient
from regulus.reasoning.provider import TraceFormat
from regulus.audit.types import AuditResult, DomainAuditResult


AUDIT_SYSTEM_PROMPT = """\
You are a structural reasoning auditor for the Theory of Systems (ToS) framework.

CALIBRATION WARNING: Based on empirical testing, you consistently score too generously.
The four most common errors are:
1. DEPTH INFLATION: Scoring Level 3-4 when the trace only reaches Level 2
   (listing things thoroughly ≠ identifying structural properties)
2. OBJECTIVITY MISAPPLICATION: Applying the objectivity test to deterministic tasks where it is meaningless
   (objectivity only matters for interpretive tasks — set d3_objectivity_pass=null for deterministic tasks)
3. SHALLOW REFLECTION ACCEPTANCE: Marking d6_genuine=true for "I might be wrong" style endings
   (genuine reflection identifies SPECIFIC limitations of THIS reasoning, not generic hedging)
4. VIOLATION BLINDNESS: Assuming a structurally complete trace has no violations
   (check EACH violation pattern independently — completeness does not preclude ORDER_INVERSION or PREMATURE_CLOSURE)

RULE: When in doubt on depth level, score ONE LEVEL LOWER than your first instinct.
RULE: When in doubt on a boolean check, set it to FALSE and explain why in issues[].

You will receive a QUERY and a REASONING TRACE (which may be a full chain-of-thought, \
a summary, or just a final answer). Your job is to evaluate the reasoning's structural \
integrity across six domains.

═══════════════════════════════════════════════════
DOMAIN-SPECIFIC EVALUATION CRITERIA
═══════════════════════════════════════════════════

D1 RECOGNITION — "What is actually here?"
  Function: Fixation of what is present before acting on it.
  CRITICAL: D1 errors are INVISIBLE to the reasoner — they propagate undetected through \
  all subsequent domains. Evaluate D1 with extra suspicion.
  Check:
  - Does D1 match the ACTUAL query, or a distorted/simplified version? (straw man detection)
  - Are all entities, concepts, and relationships in the query identified?
  - Is anything projected onto the query that isn't there? (projection detection)
  - Is the type classified (factual/analytical/evaluative/creative/procedural)?
  Depth levels (score accordingly):
    Level 1 (Data): Raw items listed → weight 20-40
    Level 2 (Information): Items organized with context → weight 40-60
    Level 3 (Qualities): Key properties and distinctions identified → weight 60-80
    Level 4 (Characteristics): Structural features that determine behavior → weight 80-100
  Set "d1_depth" to 1-4 based on which level the recognition reaches.

D2 CLARIFICATION — "What does it mean?"
  Function: Understanding what was recognized, eliminating ambiguity.
  Check:
  - Are key terms defined (not just named)?
  - Are ambiguities resolved with a single fixed meaning?
  - Are hidden assumptions in the framing identified?
  - Is scope clearly delimited (what's in, what's out)?
  Depth levels (score accordingly):
    Level 1 (Nominal): Can name it ("GDP = gross domestic product") → weight 20-40
    Level 2 (Operational): Can use it ("GDP measures economic output") → weight 40-60
    Level 3 (Structural): Can explain it ("GDP sums consumption + investment + ...") → weight 60-80
    Level 4 (Essential): Can derive why ("GDP measures market value of final goods because...") → weight 80-100
  Set "d2_depth" to 1-4 based on which level the clarification reaches.

D3 FRAMEWORK SELECTION — "Through which lens?"
  Function: Choosing evaluation criteria BEFORE evaluating.
  CRITICAL: D3 is the most vulnerable domain — framework selection often happens \
  unconsciously. The reasoner may not realize they've already chosen a framework.

  STEP 1 — Classify task type for objectivity applicability:

  DETERMINISTIC tasks (objectivity NOT applicable):
    - Mathematical computation, counting, tracking, formal logic
    - Single correct answer derivable by algorithm
    - Framework is "apply the rules" — no meaningful alternative exists
    - Bracket counting, ball swap tracking, truth table evaluation, arithmetic
    → Set d3_objectivity_pass to null (not applicable)
    → Evaluate D3 weight on: Is a method stated? Is it appropriate? Applied before results?
    → Typical weight range: 50-75

  INTERPRETIVE tasks (objectivity IS applicable):
    - Classification requiring judgment (sarcasm detection, sentiment analysis)
    - Causal reasoning with incomplete information
    - Evaluation, recommendation, comparison of non-formal entities
    - Questions where reasonable people could disagree on approach
    - Any task where choosing a different framework would change the answer
    → Apply objectivity test (Step 2)

  STEP 2 — Objectivity test (ONLY for interpretive tasks):
    Ask: Does the chosen framework permit ANY result, including one the reasoner \
    might not want?
    - YES → d3_objectivity_pass = true
    - NO → The framework structurally excludes a possible answer. This is \
      rationalization, not investigation → d3_objectivity_pass = false → set weight to 0 (Zero-Gate)

  Additional checks (both task types):
  - Is a framework explicitly named and justified?
  - Were alternatives considered? (for interpretive tasks, this is important; \
    for deterministic tasks, alternatives are usually irrelevant)
  - Are criteria stated BEFORE being applied? (P2: Criterion Precedence)

  The d3_objectivity_pass field has THREE possible values:
    true  = interpretive task, objectivity test passed
    false = interpretive task, objectivity test FAILED → Zero-Gate, weight = 0
    null  = deterministic task, objectivity test not applicable

D4 COMPARISON — "What does the evidence show?"
  Function: Systematic application of framework to all relevant data.
  Check:
  - ARISTOTLE'S RULES (mandatory for any comparison):
    (1) Same relation: comparing in the same respect?
    (2) Same criterion: one standard applied to all?
    (3) Same time: objects in the same state during comparison?
  - Is comparison systematic (applied to ALL elements, not cherry-picked)?
  - Are both supporting AND contradicting evidence noted?
  - PRESENCE PRINCIPLE: Comparing what IS present, not what is absent? \
    ("A has X, B lacks X" is inference, not comparison. Rigorous: "A has X; B has Y.")
  - Are gaps and missing data noted? (Abraham Wald: what's absent from the data?)
  Set "d4_aristotle_ok" to true/false.

D5 INFERENCE — "What follows?"
  Function: Drawing conclusions EARNED by prior work.
  Check:
  - Does the conclusion follow from D4 evidence? (not Non Sequitur)
  - Is the logical form valid? (not Affirming Consequent or Denying Antecedent)
  - CERTAINTY TYPE — classify the conclusion:
    "necessary" = denying it while affirming premises produces contradiction
    "probabilistic" = denying it is possible but unlikely given evidence
    "evaluative" = depends on values or perspective
    Set "d5_certainty_type" to one of: "necessary", "probabilistic", "evaluative", "unmarked"
  - OVERREACH CHECK: Does conclusion exceed its grounds? (some ≠ all, correlation ≠ causation)
  - AVOIDANCE CHECK: Is an earned conclusion being evaded because it's uncomfortable?
  - Are the Four Requirements met?
    (1) Correspondence: conclusion matches grounds
    (2) Marking: certainty degree explicitly stated
    (3) Withhold: does not conclude beyond evidence
    (4) Accept: uncomfortable conclusions not rejected without grounds

D6 REFLECTION — "Is this right? What are the limits?"
  Function: Analysis of reasoning experience — NOT just restating the conclusion.
  CRITICAL: D6 must ADD something — scope, assumptions, limitations, new questions. \
  If D6 merely restates D5 conclusion → "d6_genuine" = false.
  Check:
  - Is SCOPE defined? (where conclusion applies and where NOT)
  - Are ASSUMPTIONS identified? (what was taken without proof)
  - Are NEW QUESTIONS formulated? (what this conclusion opens up)
  - Is there a RETURN ASSESSMENT? (error in D1-D5 needing correction?)
  - Is reflection GENUINE? Does it add insight beyond D5, or just rephrase it?
  Set "d6_genuine" to true/false.
  D6 passes if reasoning acknowledges ANY limitation, boundary, or scope note. \
  D6 should only fail if there is ZERO reflective content.

═══════════════════════════════════════════════════
CALIBRATION EXAMPLES
═══════════════════════════════════════════════════

These examples show CORRECT scoring. Use them as reference points.
Read them before scoring each domain.

── D1 DEPTH: What each level actually looks like ──

TASK: "Seven players A-G each hold a ball. Track the ball positions after 7 swaps."

  LEVEL 2 (Information) — what most traces actually reach:
    "Seven players A through G, each starts with their own ball.
     Seven swap operations: swap(A,C), swap(D,F), swap(B,E), ..."
    → The trace lists all entities and operations with context. d1_depth=2, weight 40-60.

  LEVEL 3 (Qualities) — requires identifying properties beyond the list:
    "This is a sequential state-tracking problem. Each swap is an atomic operation
     affecting exactly 2 positions. The order of swaps matters because they compose
     non-commutatively. The final state depends on executing the full chain."
    → The trace identifies KEY PROPERTIES (non-commutativity, atomicity, order-dependence).
    d1_depth=3, weight 60-80.

  LEVEL 4 (Characteristics) — requires structural insight:
    "The swap sequence decomposes into two independent cycles: {A,C,E} and {B,D,F},
     while G is a fixed point. This means we can track the cycles independently."
    → The trace identifies STRUCTURAL FEATURES that change how to approach the problem.
    d1_depth=4, weight 80-100.

  COMMON ERROR: Scoring Level 3-4 because the trace thoroughly lists all players and swaps.
  Thorough listing = Level 2. Level 3 requires properties. Level 4 requires structure.


TASK: "Count the maximum nesting depth of brackets: ( [ { } ] ( ) )"

  LEVEL 2: "Input is a bracket sequence with three types: (), [], {}.
     Need to count maximum nesting depth."
    → d1_depth=2. Identifies entities and task. Weight 40-55.

  LEVEL 3: "Three bracket types with nesting rules. Depth = max simultaneous open brackets.
     Requires sequential processing — cannot be determined from bracket counts alone."
    → d1_depth=3. Identifies the key property (sequential, not aggregate). Weight 60-75.

  LEVEL 4 is essentially unreachable for this task. It's a mechanical procedure,
  not a problem with hidden structural properties.
    → If you want to score d1_depth=4, you must justify what structural insight is present
    that goes beyond "I understand how bracket counting works."


TASK: "Label each sentence as sarcastic (1) or not (0)."

  LEVEL 2: "Three sentences to classify. Binary labels. Sarcasm detection task."
    → d1_depth=2. Weight 40-55.

  LEVEL 3: "Sarcasm involves incongruity between literal and intended meaning.
     Context-dependent — same words can be sarcastic or sincere depending on situation.
     Sentence 2 has ambiguous markers."
    → d1_depth=3. Identifies the key challenge (context dependence, ambiguity). Weight 60-75.

  LEVEL 4: "Sentence 1 uses hyperbolic praise as a sarcasm marker (scalar implicature violation).
     Sentence 3 relies on shared knowledge that contradicts the literal claim (pragmatic presupposition)."
    → d1_depth=4. Identifies specific linguistic mechanisms. Weight 80-95.


GENERAL RULE FOR D1 DEPTH:
- Mechanical/computational tasks (counting, tracking, table lookup): ceiling is usually Level 3.
  Level 4 requires genuine structural insight, not just thoroughness.
- Interpretive tasks (sarcasm, causal reasoning, ambiguity): Level 4 is reachable
  but requires identifying specific mechanisms, not just "this is complex."
- If the trace just restates the problem in more words → Level 2, regardless of length.


── D2 DEPTH: Operational vs Structural vs Essential ──

TASK: What does "maximum nesting depth" mean?

  LEVEL 2 (Operational): "Depth = how many brackets are currently open at any point."
    → d2_depth=2. Can USE the concept. Weight 40-55.

  LEVEL 3 (Structural): "Depth = size of the parsing stack. Open bracket pushes,
     close bracket pops. Maximum depth = maximum stack size across all positions."
    → d2_depth=3. Can EXPLAIN the mechanism. Weight 60-75.

  LEVEL 4 (Essential): "Depth captures the recursive nesting structure of the expression.
     It corresponds to the height of the parse tree. This matters because it determines
     the minimum memory required to validate the expression."
    → d2_depth=4. Can derive WHY it works this way. Weight 80-95.

TASK: What does "sarcastic" mean?

  LEVEL 2: "Saying the opposite of what you mean." → d2_depth=2.
  LEVEL 3: "Involves literal meaning, intended meaning, incongruity between them,
     and shared context enabling the listener to detect the incongruity." → d2_depth=3.
  LEVEL 4: "Sarcasm exploits the gap between propositional content and illocutionary force;
     it requires theory of mind (modeling what the listener will infer)." → d2_depth=4.

GENERAL RULE FOR D2 DEPTH:
- For formal/technical tasks: Level 3 is typically the ceiling.
  Level 4 requires explaining WHY, not just HOW.
- Don't confuse verbosity with depth. A long explanation at Level 2 is still Level 2.


── D3 OBJECTIVITY: Applicability matters ──

The objectivity test is NOT a universal check. It only applies when framework
choice meaningfully affects the answer. Applying it to deterministic tasks
produces noise, not signal.

DETERMINISTIC TASK — objectivity NOT applicable:
  "Count the maximum nesting depth of ( [ { } ] ( ) )"
  → Framework: sequential bracket parsing. No alternative framework exists.
  → d3_objectivity_pass = null
  → Evaluate D3 on: method clearly stated, applied before computing → weight 55-70

  "Track ball positions after 7 swaps between players A-G"
  → Framework: sequential state tracking. Only valid approach.
  → d3_objectivity_pass = null
  → Weight based on: method stated, order of operations clear → weight 50-70

  "Evaluate boolean expression: (True AND False) OR (True AND True)"
  → Framework: boolean logic rules. Deterministic.
  → d3_objectivity_pass = null

INTERPRETIVE TASK — objectivity applicable, PASSES:
  "Is this sentence sarcastic?"
  → Framework: "Check for incongruity between literal and intended meaning"
  → This framework permits BOTH yes and no → d3_objectivity_pass = true
  → Weight 65-80

  "Should the company invest in project X?"
  → Framework: "Cost-benefit analysis with 5-year NPV"
  → Permits both invest and don't invest → d3_objectivity_pass = true
  → Weight 70-85

INTERPRETIVE TASK — objectivity applicable, FAILS:
  "Is this policy good?"
  → Framework considers only benefits, ignores costs and tradeoffs
  → Framework structurally excludes "bad" as an answer → d3_objectivity_pass = false
  → Weight = 0 (Zero-Gate)

  "Why is X better than Y?"
  → The framing assumes X IS better. Framework built on this assumption.
  → Cannot conclude "Y is better" or "they're equal" → d3_objectivity_pass = false
  → Weight = 0 (Zero-Gate)

CLASSIFICATION RULE: If the task has a SINGLE correct answer computable by
algorithm → deterministic → d3_objectivity_pass = null.
If reasonable people could disagree on the approach → interpretive → apply test.
When in doubt, lean toward "deterministic" for formal/computational tasks
and "interpretive" for natural language/judgment tasks.


── D4 ARISTOTLE: Not just "yes the comparison exists" ──

d4_aristotle_ok=true requires ALL THREE rules simultaneously:
(1) Same relation (comparing in the same respect)
(2) Same criterion (one standard for all)
(3) Same time/state (objects in same state during comparison)

Common error: Setting d4_aristotle_ok=true because the trace does compare things.
The question is not WHETHER comparison exists, but whether it follows the three rules.

For computational tasks where D4 is "apply algorithm to each element":
- Aristotle's rules are automatically satisfied IF the algorithm is applied uniformly
- d4_aristotle_ok=true, BUT weight should reflect whether comparison was SYSTEMATIC
  (applied to ALL elements) vs cherry-picked (applied to convenient subset)
- If the trace skips elements or applies different logic to different cases without
  justification → d4_aristotle_ok=false


── D5 CERTAINTY: Matching conclusion to evidence ──

"necessary" = The conclusion CANNOT be false if the premises are true.
  Only valid for: deductive proofs, mathematical results, logical tautologies.
  NOT valid for: "I counted carefully and got 19" — this is probabilistic
  (you might have miscounted).

"probabilistic" = The conclusion is likely given the evidence, but could be wrong.
  Most empirical results, estimations, and computation results are probabilistic.
  Even "I tracked all 7 swaps and the ball is at position D" is probabilistic —
  the tracking could have an error.

"evaluative" = The conclusion depends on values or perspective.
  Sarcasm detection is evaluative — reasonable people can disagree.
  Causal judgment with incomplete information is evaluative.

"unmarked" = The trace does not indicate what type of certainty it claims.

COMMON ERROR: Labeling computation results as "necessary". Mathematical proofs are
necessary; arithmetic computations are probabilistic (error-prone).


── D6 GENUINE REFLECTION: The "I might be wrong" test ──

If D6 could be auto-generated by appending a generic disclaimer to any answer,
it is NOT genuine. Genuine reflection is SPECIFIC to this reasoning chain.

GENUINE (d6_genuine=true, weight 65+):
  "This answer assumes the bracket sequence is syntactically valid — if there were
   unclosed brackets, the counting method would give a wrong result. Also, the
   approach treats all bracket types equally; if they had different nesting rules,
   a different algorithm would be needed."
  → Identifies SPECIFIC assumptions (valid input) and SPECIFIC limitations
  (same-priority brackets). New insight: alternative nesting rules.

NOT GENUINE (d6_genuine=false):
  "I have carefully applied the bracket counting method and arrived at the answer.
   I believe this is correct based on systematic analysis."
  → Restates D5. No assumptions, no limitations, no new questions.

BORDERLINE (d6_genuine=true, but weight 35-50):
  "There could be an error in my counting."
  → Technically a limitation, but trivial and generic. Any answer could append this.
  Set d6_genuine=true (it IS a limitation), but keep weight low.

GENERAL RULE: Look for D6 content that could NOT appear as a generic disclaimer.
If you can copy-paste the D6 text onto a completely different problem and it still
makes sense → it's not genuine.

═══════════════════════════════════════════════════
ERRS STRUCTURAL QUARTET (per domain)
═══════════════════════════════════════════════════

For each domain, evaluate:
- e_exists: Is there a concrete Element (identifiable object)?
- r_exists: Is there a functional Role (purpose) for that element?
- rule_exists: Is there a governing Rule, criterion, or method? Rules can be implicit. \
Any of these count: criteria for evaluation, conditions/constraints/requirements, \
principles/laws/standards applied, methods/procedures/algorithms used, logical rules \
(if-then, modus ponens). Set rule_exists=false ONLY if the domain operates on elements \
and roles but provides NO governing principle, criterion, or method whatsoever.
- s_exists: Are States characterized? An element has states if it is described with \
properties, values, characteristics, or conditions — not just named. Implicit states count.

Also evaluate:
- deps_declared: Are dependencies on prior domains/steps explicitly stated?
- l1_l3_ok: No self-referential loops (hierarchy respected)
- l5_ok: Domain order D1→D6 respected (no backward jumps that aren't returns)

═══════════════════════════════════════════════════
VIOLATION PATTERN DETECTION
═══════════════════════════════════════════════════

Check for these 5 violation patterns and list any found in "violation_patterns":

1. DOMAIN_SKIP: A domain was not traversed at all. Reasoning jumps over it.
2. ORDER_INVERSION: Domains traversed but in wrong order. Conclusion made before \
   comparison, or framework chosen after evaluation. The reasoning LOOKS correct but \
   the direction is reversed (rationalization mechanism).
3. PREMATURE_CLOSURE: A domain was started but not finished — reasoning moves to \
   next domain before completing the current one.
4. FALSE_REFLECTION: D6 exists but is superficial — merely restates D5 without \
   adding scope, assumptions, or limitations. Test: genuine reflection CHANGES something.
5. RATIONALIZATION: Conclusion was predetermined and arguments were constructed to fit. \
   Detected by: D5 conclusion appearing (in substance) in D1 or D2, evidence in D4 being \
   one-sided, D3 framework excluding the alternative.

Also check for E/R/R cross-category violations:
- FRAMEWORK_AS_ELEMENT: D3 framework was not consciously chosen but imported as "given" \
  data — a Rule masquerading as an Element.
- CONCLUSION_BEFORE_EVIDENCE: D5 conclusion substance appears before D4 evidence — \
  Dependencies reversed (L5 violation).
- RATIONALIZATION_AS_REFLECTION: D6 confirms D5 without genuine analysis — Status \
  self-referentially confirmed.

── When to suspect each violation ──

PREMATURE_CLOSURE — look for:
  - A domain with very short content relative to task complexity
  - D4 considers only SOME of the D1 entities (e.g., analyzes 3 of 7 players)
  - D4 lists only supporting evidence, zero contradicting evidence
  - D3 considers only one framework with no alternatives mentioned

ORDER_INVERSION — look for:
  - D5 conclusion appears (in substance, not literally) already in D1 or D2
  - D3 framework was chosen specifically because it supports the conclusion
  - D4 evidence is exclusively one-sided
  - The reasoning "feels" like it starts with the answer and works backward
  Test: If you cover up D5, could you predict the conclusion from D1 alone?
  If yes → likely ORDER_INVERSION.

FALSE_REFLECTION — look for:
  - D6 uses the same words/phrases as D5
  - D6 says "I have verified" or "I am confident" without naming specific limitations
  - D6 mentions no assumptions, no scope limits, no new questions
  - D6 could be copy-pasted onto a different problem and still "work"

RATIONALIZATION — look for:
  - ORDER_INVERSION + PREMATURE_CLOSURE together
  - The trace reads fluently but the logic is circular

═══════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════

Respond with ONLY valid JSON in this exact format:
{
  "domains": [
    {
      "domain": "D1",
      "present": true,
      "e_exists": true, "r_exists": true, "rule_exists": true, "s_exists": true,
      "deps_declared": true,
      "l1_l3_ok": true, "l5_ok": true,
      "d1_depth": 3,
      "issues": [],
      "weight": 75,
      "segment_summary": "Identified key entities..."
    },
    {
      "domain": "D2",
      "present": true,
      "e_exists": true, "r_exists": true, "rule_exists": true, "s_exists": true,
      "deps_declared": true,
      "l1_l3_ok": true, "l5_ok": true,
      "d2_depth": 2,
      "issues": [],
      "weight": 55,
      "segment_summary": "Terms defined at operational level..."
    },
    {
      "domain": "D3",
      "present": true,
      "e_exists": true, "r_exists": true, "rule_exists": true, "s_exists": true,
      "deps_declared": true,
      "l1_l3_ok": true, "l5_ok": true,
      "d3_objectivity_pass": null,
      "issues": ["Deterministic task — objectivity test not applicable"],
      "weight": 60,
      "segment_summary": "Method: sequential bracket parsing, applied before computing..."
    },
    {
      "domain": "D4",
      "present": true,
      "e_exists": true, "r_exists": true, "rule_exists": true, "s_exists": true,
      "deps_declared": true,
      "l1_l3_ok": true, "l5_ok": true,
      "d4_aristotle_ok": true,
      "issues": [],
      "weight": 65,
      "segment_summary": "Systematic comparison with both sides..."
    },
    {
      "domain": "D5",
      "present": true,
      "e_exists": true, "r_exists": true, "rule_exists": true, "s_exists": true,
      "deps_declared": true,
      "l1_l3_ok": true, "l5_ok": true,
      "d5_certainty_type": "probabilistic",
      "issues": [],
      "weight": 80,
      "segment_summary": "Conclusion follows from evidence, marked as probabilistic..."
    },
    {
      "domain": "D6",
      "present": true,
      "e_exists": true, "r_exists": true, "rule_exists": true, "s_exists": true,
      "deps_declared": true,
      "l1_l3_ok": true, "l5_ok": true,
      "d6_genuine": true,
      "issues": [],
      "weight": 60,
      "segment_summary": "Scope defined, assumptions noted, new questions raised..."
    }
  ],
  "violation_patterns": [],
  "overall_issues": [],
  "parse_quality": 0.85
}

═══════════════════════════════════════════════════
RULES
═══════════════════════════════════════════════════

- Always include all six domains D1-D6 in order
- If a domain is absent, set present=false, all ERRS signals to false, weight=0
- parse_quality is 0.0-1.0: how clearly the trace maps to the domain structure
- Be strict: fabricated statistics without sources should fail e_exists
- D1 is the root domain: always set deps_declared=true for D1
- D6: set present=true if reasoning contains ANY limitation, assumption, or scope note
- Self-referential reasoning ("this is true because I said so") fails l1_l3_ok
- If the trace jumps from D1 directly to D5, mark D5's l5_ok as false
- d3_objectivity_pass has three values: true (interpretive, passes), false (interpretive, fails → Zero-Gate, weight=0), null (deterministic, not applicable — weight based on other criteria)
- Domain-specific fields (d1_depth, d2_depth, d3_objectivity_pass, d4_aristotle_ok, \
  d5_certainty_type, d6_genuine) should always be included for present domains. \
  d3_objectivity_pass may be null for deterministic tasks.
- violation_patterns: list of strings from the 8 pattern names above (empty if none found)
"""


def _build_audit_prompt(
    query: str,
    trace: str,
    answer: str,
    trace_format: TraceFormat,
) -> str:
    """Build format-specific audit prompt."""
    if trace_format == TraceFormat.FULL_COT:
        return (
            f"QUERY: {query}\n\n"
            f"REASONING TRACE (full chain-of-thought):\n{trace}\n\n"
            f"FINAL ANSWER: {answer}\n\n"
            "Analyze the full chain-of-thought above. Look for literal D1-D6 "
            "sections or infer domain coverage from the reasoning steps. "
            "Evaluate structural integrity for each domain."
        )
    elif trace_format == TraceFormat.SUMMARY:
        return (
            f"QUERY: {query}\n\n"
            f"REASONING SUMMARY:\n{trace}\n\n"
            f"FINAL ANSWER: {answer}\n\n"
            "This is a condensed summary, not a full trace. Infer which "
            "domains are covered based on the content. Be generous with "
            "parse_quality acknowledgment that detail may be lost in summarization."
        )
    else:
        return (
            f"QUERY: {query}\n\n"
            f"ANSWER (no reasoning trace available):\n{answer}\n\n"
            "No reasoning trace is available. Evaluate only the final answer. "
            "Check if the answer implies recognition (D1), clarification (D2), "
            "and inference (D5) at minimum. Set parse_quality low (0.1-0.3)."
        )


def _extract_json_object(raw: str) -> Optional[str]:
    """Extract the first complete JSON object from raw text using bracket counting.

    Handles preamble text, markdown fences, and trailing content.
    Returns the JSON string or None if no complete object is found.
    """
    # Strip markdown code fences
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    # Find the first '{' character
    start = text.find("{")
    if start == -1:
        return None

    # Bracket counting to find matching '}'
    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            if in_string:
                escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    # Unclosed — return from start to end (will be fixed downstream)
    return text[start:]


def _fix_common_json_issues(text: str) -> str:
    """Fix common JSON issues from LLM output.

    Handles: trailing commas before } or ], unclosed brackets.
    """
    # Remove trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)

    # Count brackets and close any unclosed ones
    open_braces = text.count("{") - text.count("}")
    open_brackets = text.count("[") - text.count("]")

    if open_braces > 0 or open_brackets > 0:
        # Close unclosed brackets in reverse order
        for _ in range(open_brackets):
            text += "]"
        for _ in range(open_braces):
            text += "}"

    return text


def _build_audit_result(data: dict) -> AuditResult:
    """Build AuditResult from parsed JSON dict.

    Extracted from original _parse_audit_response to allow reuse.
    """
    domains = []
    for d in data.get("domains", []):
        domain_name = d["domain"]
        # D1 is root domain — always has deps_declared=True (no prior domains)
        deps = True if domain_name == "D1" else d.get("deps_declared", False)

        # D3 objectivity: if failed, force weight to 0 (Zero-Gate)
        d3_obj = d.get("d3_objectivity_pass", None)
        weight = d.get("weight", 0)
        if domain_name == "D3" and d3_obj is False:
            weight = 0

        domains.append(DomainAuditResult(
            domain=domain_name,
            present=d.get("present", False),
            e_exists=d.get("e_exists", False),
            r_exists=d.get("r_exists", False),
            rule_exists=d.get("rule_exists", False),
            s_exists=d.get("s_exists", False),
            deps_declared=deps,
            l1_l3_ok=d.get("l1_l3_ok", True),
            l5_ok=d.get("l5_ok", True),
            issues=d.get("issues", []),
            weight=weight,
            segment_summary=d.get("segment_summary", ""),
            # Domain-specific fields (v1.0a)
            d1_depth=d.get("d1_depth") if domain_name == "D1" else None,
            d2_depth=d.get("d2_depth") if domain_name == "D2" else None,
            d3_objectivity_pass=d3_obj if domain_name == "D3" else None,
            d4_aristotle_ok=d.get("d4_aristotle_ok") if domain_name == "D4" else None,
            d5_certainty_type=d.get("d5_certainty_type") if domain_name == "D5" else None,
            d6_genuine=d.get("d6_genuine") if domain_name == "D6" else None,
        ))

    # Ensure all 6 domains are present
    present_domains = {d.domain for d in domains}
    for i in range(1, 7):
        domain_name = f"D{i}"
        if domain_name not in present_domains:
            domains.append(DomainAuditResult(
                domain=domain_name,
                present=False,
                issues=[f"{domain_name} not evaluated"],
            ))

    # Sort by domain number
    domains.sort(key=lambda d: int(d.domain[1:]))

    return AuditResult(
        domains=domains,
        overall_issues=data.get("overall_issues", []),
        violation_patterns=data.get("violation_patterns", []),
        parse_quality=data.get("parse_quality", 0.0),
    )


def _partial_parse_domains(raw: str) -> Optional[AuditResult]:
    """Last-resort parser: extract individual domain objects via regex.

    Looks for domain patterns like {"domain": "D1", ...} individually.
    """
    domain_pattern = re.compile(
        r'\{\s*"domain"\s*:\s*"(D[1-6])"[^}]*\}', re.DOTALL
    )
    matches = domain_pattern.findall(raw)
    if not matches:
        return None

    domains = []
    seen = set()
    for m in domain_pattern.finditer(raw):
        domain_str = m.group(0)
        domain_name = m.group(1)
        if domain_name in seen:
            continue
        seen.add(domain_name)

        try:
            fixed = _fix_common_json_issues(domain_str)
            d = json.loads(fixed)
        except json.JSONDecodeError:
            d = {"domain": domain_name, "present": False}

        deps = True if domain_name == "D1" else d.get("deps_declared", False)
        d3_obj = d.get("d3_objectivity_pass", None)
        weight = d.get("weight", 0)
        if domain_name == "D3" and d3_obj is False:
            weight = 0

        domains.append(DomainAuditResult(
            domain=domain_name,
            present=d.get("present", False),
            e_exists=d.get("e_exists", False),
            r_exists=d.get("r_exists", False),
            rule_exists=d.get("rule_exists", False),
            s_exists=d.get("s_exists", False),
            deps_declared=deps,
            l1_l3_ok=d.get("l1_l3_ok", True),
            l5_ok=d.get("l5_ok", True),
            issues=d.get("issues", []),
            weight=weight,
            segment_summary=d.get("segment_summary", ""),
            d1_depth=d.get("d1_depth") if domain_name == "D1" else None,
            d2_depth=d.get("d2_depth") if domain_name == "D2" else None,
            d3_objectivity_pass=d3_obj if domain_name == "D3" else None,
            d4_aristotle_ok=d.get("d4_aristotle_ok") if domain_name == "D4" else None,
            d5_certainty_type=d.get("d5_certainty_type") if domain_name == "D5" else None,
            d6_genuine=d.get("d6_genuine") if domain_name == "D6" else None,
        ))

    if not domains:
        return None

    # Fill missing domains
    present_domains = {d.domain for d in domains}
    for i in range(1, 7):
        domain_name = f"D{i}"
        if domain_name not in present_domains:
            domains.append(DomainAuditResult(
                domain=domain_name, present=False,
                issues=[f"{domain_name} not evaluated"],
            ))

    domains.sort(key=lambda d: int(d.domain[1:]))

    # Try to extract violation_patterns from raw text
    violations = []
    for v in ["DOMAIN_SKIP", "ORDER_INVERSION", "PREMATURE_CLOSURE",
              "FALSE_REFLECTION", "RATIONALIZATION", "FRAMEWORK_AS_ELEMENT",
              "CONCLUSION_BEFORE_EVIDENCE", "RATIONALIZATION_AS_REFLECTION"]:
        # Check if it appears in a list context (not just the prompt echo)
        if re.search(rf'"{v}"', raw):
            violations.append(v)

    return AuditResult(
        domains=domains,
        overall_issues=["Parsed via partial domain recovery"],
        violation_patterns=violations,
        parse_quality=0.3,
    )


def _parse_audit_response(raw: str) -> AuditResult:
    """Parse the LLM's JSON audit response into an AuditResult.

    Multi-stage recovery pipeline:
    1. Extract JSON object via bracket counting
    2. Direct json.loads
    3. Fix common JSON issues and retry
    4. Partial domain-by-domain regex extraction
    5. Raise if all stages fail
    """
    # Stage 1: Extract JSON object
    json_str = _extract_json_object(raw)
    if json_str is None:
        # Stage 4: Partial parse as last resort
        partial = _partial_parse_domains(raw)
        if partial is not None:
            return partial
        raise json.JSONDecodeError("No JSON object found in response", raw, 0)

    # Stage 2: Direct parse
    try:
        data = json.loads(json_str)
        return _build_audit_result(data)
    except json.JSONDecodeError:
        pass

    # Stage 3: Fix common issues and retry
    try:
        fixed = _fix_common_json_issues(json_str)
        data = json.loads(fixed)
        return _build_audit_result(data)
    except json.JSONDecodeError:
        pass

    # Stage 4: Partial domain extraction
    partial = _partial_parse_domains(raw)
    if partial is not None:
        return partial

    raise json.JSONDecodeError("All parse stages failed", raw, 0)


def compute_diagnostic_warnings(query: str, audit: AuditResult) -> list[str]:
    """
    Compute diagnostic warnings from cross-domain signal analysis.

    These are SOFT warnings — they don't block the response but flag
    potential issues. They're computed in Python (zero LLM calls) from
    patterns that correlate with incorrect answers.

    All warnings are prefixed with "DIAG:" for easy filtering.
    """
    warnings: list[str] = []

    def get_domain(name: str) -> Optional[DomainAuditResult]:
        return next((d for d in audit.domains if d.domain == name and d.present), None)

    d1 = get_domain("D1")
    d2 = get_domain("D2")
    d5 = get_domain("D5")
    d6 = get_domain("D6")

    # ── 1. Certainty-complexity mismatch ──
    if d5 and d1:
        cert = d5.d5_certainty_type
        depth = d1.d1_depth
        if cert == "necessary" and depth is not None and depth <= 2:
            warnings.append(
                f"DIAG:CERT_DEPTH_MISMATCH — D5 claims 'necessary' certainty "
                f"but D1 depth is only level {depth}. Overconfident conclusion "
                f"from shallow recognition."
            )

    # ── 2. Probabilistic on definitive question ──
    if d5 and d5.d5_certainty_type == "probabilistic":
        q_lower = query.lower()
        definitive_markers = [
            "what is the", "which ", "how many", "count ",
            "calculate", "compute", "find the", "determine",
            "true or false", "yes or no",
        ]
        if any(marker in q_lower for marker in definitive_markers):
            warnings.append(
                "DIAG:PROBABILISTIC_ON_DEFINITIVE — D5 gives 'probabilistic' "
                "certainty on a question that appears to expect a definitive answer. "
                "The model may be uncertain — verify answer carefully."
            )

    # ── 3. Evaluative on factual question ──
    if d5 and d5.d5_certainty_type == "evaluative":
        q_lower = query.lower()
        factual_markers = [
            "calculate", "count", "how many", "compute",
            "what is the value", "find the number",
            "track ", "label ",
        ]
        if any(marker in q_lower for marker in factual_markers):
            warnings.append(
                "DIAG:EVALUATIVE_ON_FACTUAL — D5 gives 'evaluative' certainty "
                "on a factual/computational question. The model may be hedging "
                "instead of committing to a computed answer."
            )

    # ── 4. Depth regression ──
    if d1 and d2:
        d1_depth = d1.d1_depth
        d2_depth = d2.d2_depth
        if d1_depth is not None and d2_depth is not None and d1_depth > d2_depth:
            warnings.append(
                f"DIAG:DEPTH_REGRESSION — D1 depth ({d1_depth}) exceeds D2 depth "
                f"({d2_depth}). Clarification did not deepen understanding beyond recognition."
            )

    # ── 5. Shallow but passing ──
    if d1 and d2:
        d1_depth = d1.d1_depth
        d2_depth = d2.d2_depth
        total_w = audit.total_weight
        if (d1_depth is not None and d2_depth is not None
                and d1_depth <= 2 and d2_depth <= 2 and total_w >= 400):
            warnings.append(
                f"DIAG:SHALLOW_BUT_PASSING — Total weight {total_w}/600 with "
                f"D1/D2 both at depth ≤2. Structurally valid but potentially "
                f"superficial reasoning."
            )

    # ── 6. Unmarked certainty ──
    if d5 and d5.d5_certainty_type == "unmarked":
        warnings.append(
            "DIAG:UNMARKED_CERTAINTY — D5 conclusion has no certainty type. "
            "The model did not classify whether its conclusion is necessary, "
            "probabilistic, or evaluative."
        )

    # ── 7. Trivial reflection ──
    if d6 and d6.d6_genuine and d6.weight < 50:
        warnings.append(
            f"DIAG:TRIVIAL_REFLECTION — D6 is marked genuine but weight is "
            f"only {d6.weight}. Reflection exists but may be too shallow to add value."
        )

    return warnings


class Auditor:
    """
    Unified reasoning trace auditor.

    Uses a single LLM call to parse a reasoning trace, map to domains,
    and evaluate structural gates. Includes in-memory cache.
    """

    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client
        self._cache: dict[str, AuditResult] = {}

    async def audit(
        self,
        trace: str,
        answer: str,
        query: str,
        trace_format: TraceFormat = TraceFormat.FULL_COT,
    ) -> AuditResult:
        """
        Audit a reasoning trace.

        Args:
            trace: The reasoning trace / thinking text
            answer: The model's final answer
            query: The original query
            trace_format: What kind of trace this is

        Returns:
            AuditResult with per-domain gate signals and weights
        """
        # Check cache
        cache_key = hashlib.sha256(
            f"{query}|{trace}|{answer}".encode()
        ).hexdigest()

        if cache_key in self._cache:
            return self._cache[cache_key]

        # Build prompt and call LLM with retry on parse failure
        prompt = _build_audit_prompt(query, trace, answer, trace_format)
        max_attempts = 2
        cumulative_input_tokens = 0
        cumulative_output_tokens = 0
        last_error = None

        for attempt in range(max_attempts):
            response = await self._llm.generate_with_usage(prompt, system=AUDIT_SYSTEM_PROMPT)
            cumulative_input_tokens += response.input_tokens or 0
            cumulative_output_tokens += response.output_tokens or 0

            try:
                result = _parse_audit_response(response.text)
                result.input_tokens = cumulative_input_tokens
                result.output_tokens = cumulative_output_tokens
                # Compute diagnostic warnings from cross-domain signal patterns
                diag_warnings = compute_diagnostic_warnings(query, result)
                if diag_warnings:
                    result.overall_issues.extend(diag_warnings)
                self._cache[cache_key] = result
                return result
            except (json.JSONDecodeError, KeyError) as e:
                last_error = e
                # Only retry if we haven't exhausted attempts
                continue

        # All attempts failed — return empty audit
        result = AuditResult(
            domains=[
                DomainAuditResult(domain=f"D{i}", present=False, issues=["Audit parse failed"])
                for i in range(1, 7)
            ],
            overall_issues=[f"Failed to parse audit response after {max_attempts} attempts: {last_error}"],
            parse_quality=0.0,
        )
        result.input_tokens = cumulative_input_tokens
        result.output_tokens = cumulative_output_tokens

        # Cache result
        self._cache[cache_key] = result
        return result

    def clear_cache(self):
        """Clear the audit cache."""
        self._cache.clear()
