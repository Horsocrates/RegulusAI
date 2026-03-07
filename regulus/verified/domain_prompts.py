"""Load real domain prompts from .md files.

Each domain .md file contains:
- ROLE section: what the domain does
- INPUT section: what it receives
- PRINCIPLES section: invariants that must hold
- OUTPUT FORMAT section: exact JSON schema
- FAILURE MODES: what to watch for
- CHECKLIST: well-formedness requirements

We load these and build prompts that include:
1. The full domain instructions
2. The question
3. The previous domain's structured JSON output
4. The exact output format expected

Resolves HLE calibration gap: generic prompts -> real protocol prompts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class DomainPromptLoader:
    """Loads and assembles domain-specific prompts from .md files."""

    # Search order for domain files (v3 preferred, then v2, then v1)
    DOMAIN_FILES = {
        0: ["analyze-v2.md", "analyze.md"],                  # Team Lead
        1: ["d1-recognize-v3.md", "d1-recognize.md"],        # Recognition
        2: ["d2-clarify-v3.md", "d2-clarify.md"],            # Clarification
        3: ["d3-framework-v3.md", "d3-framework.md"],        # Framework
        4: ["d4-compare-v3.md", "d4-compare.md"],            # Comparison
        5: ["d5-infer-v3.md", "d5-infer.md"],                # Inference
        6: ["d6-reflect.md"],                                 # Reflection
        "ask": ["d6-ask.md"],                                 # D6-ASK
    }

    # Search directories (relative to repo root)
    SEARCH_DIRS = [
        ".claude/commands",
        "skills",
        "regulus/instructions/default",
    ]

    def __init__(self, repo_root: Optional[str] = None):
        """Load all domain prompt files.

        Args:
            repo_root: root of the repository. If None, auto-detect.
        """
        if repo_root is None:
            # Try to find repo root by looking for CLAUDE.md
            cwd = Path.cwd()
            for p in [cwd] + list(cwd.parents):
                if (p / "CLAUDE.md").exists():
                    repo_root = str(p)
                    break
            if repo_root is None:
                repo_root = str(cwd)

        self.repo_root = Path(repo_root)
        self.raw_prompts: dict[int | str, str] = {}
        self.loaded_files: dict[int | str, str] = {}

        for domain_key, filenames in self.DOMAIN_FILES.items():
            for search_dir in self.SEARCH_DIRS:
                found = False
                for filename in filenames:
                    path = self.repo_root / search_dir / filename
                    if path.exists():
                        self.raw_prompts[domain_key] = path.read_text(
                            encoding="utf-8"
                        )
                        self.loaded_files[domain_key] = str(path)
                        found = True
                        break
                if found:
                    break

    @property
    def loaded_count(self) -> int:
        """Number of domain files loaded."""
        return len(self.raw_prompts)

    @property
    def loaded_summary(self) -> dict[str, str]:
        """Map of domain -> loaded file path."""
        return {str(k): v for k, v in self.loaded_files.items()}

    def build_prompt(
        self,
        domain_num: int,
        question: str,
        prev_output: Optional[str] = None,
        ask_output: Optional[str] = None,
        tl_conspectus: Optional[str] = None,
    ) -> str:
        """Build complete prompt for a domain call.

        Args:
            domain_num: 1-5 for workers, 6 for REFLECT FULL
            question: the original question
            prev_output: JSON string of previous domain's output
            ask_output: JSON string of D6-ASK output (erfragte, sub-questions)
            tl_conspectus: Team Lead's running notes
        """
        parts = []

        # 1. Full domain instructions from .md file
        if domain_num in self.raw_prompts:
            parts.append(self.raw_prompts[domain_num])

        # 2. The question (with erfragte from D6-ASK if available)
        parts.append(f"\n## QUESTION\n\n{question}")

        if ask_output:
            parts.append(f"\n## D6-ASK ANALYSIS\n\n{ask_output}")

        # 3. Previous domain output (structured JSON)
        if prev_output:
            parts.append(
                f"\n## PREVIOUS DOMAIN OUTPUT (Reasoning Passport so far)\n\n"
                f"```json\n{prev_output}\n```"
            )

        # 4. Team Lead conspectus
        if tl_conspectus:
            parts.append(f"\n## TEAM LEAD CONSPECTUS\n\n{tl_conspectus}")

        # 5. Explicit instruction to produce JSON output
        parts.append(self._output_reminder(domain_num))

        return "\n\n---\n\n".join(parts)

    def build_ask_prompt(self, question: str) -> str:
        """Build D6-ASK prompt (pre-pipeline question decomposition)."""
        parts = []

        # Full d6-ask.md if available
        if "ask" in self.raw_prompts:
            parts.append(self.raw_prompts["ask"])

        parts.append(f"""
## INPUT

```json
{{
  "context": "initial",
  "question_text": {json.dumps(question)}
}}
```

## OUTPUT INSTRUCTION

Respond with ONLY this JSON (no extra text):
```json
{{
  "mode": "ask",
  "context": "initial",
  "question_structure": {{
    "gefragte": "subject matter — WHAT is being asked about",
    "befragte": "material to examine — WHERE to look",
    "erfragte": "what form the answer must take (e.g., 'single fraction p/q', 'integer', 'proof')"
  }},
  "root_question": "the ONE question to answer",
  "sub_questions": [
    {{
      "id": "Q1",
      "question": "precise question text",
      "type": "structural|clarifying|defining|framework|comparative|causal|compositional",
      "target_domain": 1,
      "serves_root": "how this contributes to root answer",
      "success_criteria": "testable criterion"
    }}
  ],
  "honesty": {{
    "is_open": true,
    "loaded_presuppositions": [],
    "bias_risk": "low|medium|high"
  }},
  "traps": ["trap 1", "trap 2"],
  "complexity": "trivial|simple|moderate|complex",
  "task_type": "computation|proof|classification|explanation|estimation",
  "composition_test": "If Q1..Qn answered, root answer composes by: [description]"
}}
```""")

        return "\n\n---\n\n".join(parts)

    def build_tl_prompt(
        self,
        question: str,
        domain_num: int,
        domain_output: str,
        all_outputs: list[dict],
        conspectus: str = "",
    ) -> str:
        """Build Team Lead verification prompt after a domain.

        The TL independently verifies domain output, doesn't solve.
        """
        parts = []

        # TL instructions from analyze.md
        if 0 in self.raw_prompts:
            # Extract just the verification section, not full orchestration
            parts.append(
                "You are the TEAM LEAD. Your job: VERIFY domain output, "
                "update conspectus, decide next step. You NEVER solve — "
                "you only check.\n\n"
                "Rules from analyze.md:\n"
                "- Compare domain components with your own independent view\n"
                "- Discrepancies = investigate further\n"
                "- Update conspectus with only KEY findings (<200 words)\n"
            )

        outputs_text = ""
        for d in all_outputs:
            outputs_text += (
                f"\n### D{d.get('domain', '?')} Output:\n"
                f"```json\n{json.dumps(d, indent=2, default=str)[:1500]}\n```\n"
            )

        parts.append(f"""## QUESTION
{question}

## DOMAIN OUTPUTS SO FAR
{outputs_text}

## CURRENT CONSPECTUS
{conspectus or "(empty)"}

## YOUR TASK
1. Verify D{domain_num} output meets readiness criteria:
   - D2→D3 ready? Sufficient recognition + clarification for framework?
   - D4→D5 ready? Comparison complete enough for inference?
2. Check ERR propagation (structure EXTENDED, not replaced?)
3. Check: does domain output use the correct schema from its instruction?
4. Update conspectus with single KEY finding from D{domain_num}
5. Decide: PASS | ITERATE (with specific fix) | ESCALATE (structural problem)

Respond with ONLY JSON:
```json
{{
  "tl_verification": {{
    "domain_checked": {domain_num},
    "readiness": true,
    "err_extended": true,
    "schema_correct": true,
    "issues": [],
    "conspectus_update": "key finding from D{domain_num}",
    "decision": "pass|iterate|escalate",
    "iterate_reason": ""
  }}
}}
```""")

        return "\n\n---\n\n".join(parts)

    def build_reflect_full_prompt(
        self,
        question: str,
        all_outputs: list[dict],
        ask_output: str,
        gates_summary: str = "",
    ) -> str:
        """Build D6-REFLECT FULL prompt (post-pipeline)."""
        parts = []

        # Full d6-reflect.md if available
        if 6 in self.raw_prompts:
            parts.append(self.raw_prompts[6])

        outputs_text = ""
        for d in all_outputs:
            outputs_text += (
                f"\n### D{d.get('domain', '?')}:\n"
                f"```json\n{json.dumps(d, indent=2, default=str)[:2000]}\n```\n"
            )

        parts.append(f"""## QUESTION
{question}

## D6-ASK
{ask_output}

## ALL DOMAIN OUTPUTS
{outputs_text}

## GATE RESULTS
{gates_summary or "(all passed)"}

## CRITICAL REMINDERS
- Every statement must ADD information — no fake reflection
- Cover Class I + at least 2 from Class II (Perceptive, Procedural, Perspectival, Fundamental)
- Run reverse diagnostics if ANYTHING feels wrong
- Verify ERR chain across all domains
- If conf >= 85% or certainty = necessary → Proof Boundary Audit is MANDATORY
- Limitations must be SPECIFIC to THIS problem (not "there might be errors")
- Compute confidence using min-aggregation: C_final = min(D1, D2, D3, D4, D5)
- Apply hard caps: HC4 (no cross-verification → cap 75%), HC9 (zero D3 alternatives → cap 70%)

## OUTPUT FORMAT
Respond with ONLY this JSON:
```json
{{
  "depth": "full",
  "class_i": "conclusive summary — what is the answer and why",
  "perceptive": "new insight gained during analysis (or null)",
  "procedural": "methodology assessment — what worked, what didn't (or null)",
  "perspectival": "viewpoint analysis — what perspective was taken (or null)",
  "fundamental": "foundational insight — deep principle at work (or null)",
  "err_chain": {{
    "elements_consistent": true,
    "dependencies_acyclic": true,
    "status_transitions_justified": true,
    "no_level_violations": true
  }},
  "domain_scores": {{
    "D1": 0-100,
    "D2": 0-100,
    "D3": 0-100,
    "D4": 0-100,
    "D5": 0-100
  }},
  "hard_caps_applied": [],
  "scope_fails_when": "specific limitation of THIS answer",
  "adjusted_confidence": 0-100,
  "adjustment_reason": "why this confidence — reference scorecard + caps",
  "return_type": "none|corrective|deepening|expanding",
  "target_domain": 0,
  "final_answer": "THE EXACT ANSWER"
}}
```""")

        return "\n\n---\n\n".join(parts)

    def _output_reminder(self, domain_num: int) -> str:
        """Remind LLM to output in the exact JSON format specified."""
        reminders = {
            1: (
                "## OUTPUT INSTRUCTION\n\n"
                "Respond with ONLY the JSON output as specified in the OUTPUT FORMAT section above.\n"
                "Include ALL required fields: OBJECT, TYPE, TASK, HIERARCHY, ELEMENTS, ROLES, RULES, "
                "STATUS, DEPENDENCIES, CONSTRAINTS, KEY_CHALLENGE, DEPTH_ACHIEVED, "
                "D1_WELL_FORMEDNESS, D1_CHECKLIST.\n"
                "Also include: confidence (0-100), answer (brief summary)."
            ),
            2: (
                "## OUTPUT INSTRUCTION\n\n"
                "Respond with ONLY the JSON output as specified in the OUTPUT FORMAT section above.\n"
                "Include ALL required fields: CLARIFIED_ELEMENTS, AMBIGUITIES_RESOLVED, "
                "RULES_VERIFIED, HIDDEN_CONTENT_SURFACED, STATUS_UPDATES, "
                "CRITICAL_CLARIFICATION, DEPTH_SUMMARY, D2_WELL_FORMEDNESS, D2_CHECKLIST.\n"
                "Also include: confidence (0-100), answer (clarified problem statement)."
            ),
            3: (
                "## OUTPUT INSTRUCTION\n\n"
                "Respond with ONLY the JSON output as specified in the OUTPUT FORMAT section above.\n"
                "Include ALL required fields: COMPLEXITY, FRAMEWORK (with Name, Criteria_for_D4), "
                "ALTERNATIVES_CONSIDERED, PRE_SELECTION_CHECK, HIERARCHY_CHECK, "
                "FRAMEWORK_LIMITATIONS, APPROACH_PLAN, D3_WELL_FORMEDNESS, D3_CHECKLIST.\n"
                "Also include: confidence (0-100), answer (framework and why)."
            ),
            4: (
                "## OUTPUT INSTRUCTION\n\n"
                "Respond with ONLY the JSON output as specified in the OUTPUT FORMAT section above.\n"
                "Include ALL required fields: COMPARABILITY_CHECK (with Aristotle_Rules), "
                "COMPARISONS, COMPUTATION_TRACE (MANDATORY for quantitative), "
                "STATUS_UPDATES, KEY_FINDINGS, CROSS_VERIFICATION, "
                "DISCONFIRMING_EVIDENCE, D4_WELL_FORMEDNESS, D4_CHECKLIST.\n"
                "CRITICAL: COMPUTATION_TRACE must show ALL intermediate steps.\n"
                "Also include: confidence (0-100), answer (computed result with work shown)."
            ),
            5: (
                "## OUTPUT INSTRUCTION\n\n"
                "Respond with ONLY the JSON output as specified in the OUTPUT FORMAT section above.\n"
                "Include ALL required fields: INFERENCE_TYPE, CHAIN (Foundation + Link + Conclusion), "
                "ANSWER, CERTAINTY (Type + Negation_test + Level + Language), "
                "L5_DIRECTION_CHECK, FOUR_REQUIREMENTS, ALTERNATIVES_CONSIDERED, "
                "REFUTABILITY, INJECTED_PREMISES, D5_WELL_FORMEDNESS, D5_CHECKLIST.\n"
                "CRITICAL: L5 direction MUST be premises→conclusion (never reversed).\n"
                "Also include: confidence (0-100)."
            ),
        }
        return reminders.get(domain_num, "Respond with structured JSON.")
