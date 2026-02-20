"""
Run P3 (Agent D1-D6 Pipeline) on HLE questions.

Architecture:
  Main Agent (Team Lead + D6) = Opus 4.6 Thinking
  D1, D2, D3 workers = Sonnet (structural domains)
  D4, D5 workers = Opus 4.6 Thinking (heavy computation)

  Pipeline:
    1. Plan (Opus thinking)
    2. D1 worker (Sonnet) → gate (Opus thinking verifies) → pass/retry
    3. D2 worker (Sonnet) → gate (Opus thinking verifies) → pass/retry
    4. D3 worker (Sonnet) → gate (Opus thinking verifies) → pass/retry
    5. D4 worker (Opus thinking) → gate (Opus thinking verifies) → pass/retry
    6. D5 worker (Opus thinking) → gate (Opus thinking verifies) → pass/retry
    7. D6 reflection + assembly (Opus thinking — Main Agent itself)

Domain prompts loaded from .claude/commands/*.md
Results go to .judge_only/p3_{batch}.json

Usage:
  python tests/HLE/run_p3_agent.py --batch batch_004
  python tests/HLE/run_p3_agent.py --batch batch_004 --no-thinking  # disable thinking for faster/cheaper runs
"""

import json
import re
import time
import os
import sys
import argparse
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

import anthropic

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
COMMANDS_DIR = os.path.join(PROJECT_ROOT, ".claude", "commands")

OPUS = "claude-opus-4-6"
SONNET = "claude-sonnet-4-20250514"

DOMAIN_FILES = {
    "d1": "d1-recognize.md",
    "d2": "d2-clarify.md",
    "d3": "d3-framework.md",
    "d4": "d4-compare.md",
    "d5": "d5-infer.md",
    "d6": "d6-reflect.md",
}

# Which model for each domain worker
DOMAIN_MODELS = {
    "d1": SONNET,
    "d2": SONNET,
    "d3": SONNET,
    "d4": OPUS,    # heavy computation
    "d5": OPUS,    # drawing conclusions
}

# Thinking budget per role (0 = no thinking, use regular call)
THINKING_BUDGET = {
    "plan":        4000,   # Team Lead initial analysis
    "verify":      2000,   # Team Lead gate checks
    "d1":          0,      # Sonnet — no thinking
    "d2":          0,      # Sonnet — no thinking
    "d3":          0,      # Sonnet — no thinking
    "d4":          10000,  # heavy computation, needs deep thinking
    "d5":          6000,   # conclusion drawing
    "d6_assembly": 10000,  # reflection + final answer
}

DOMAIN_INPUTS = {
    "d1": [],
    "d2": ["d1"],
    "d3": ["d2"],
    "d4": ["d2", "d3"],
    "d5": ["d4"],
}

DOMAIN_MAX_TOKENS = {
    "d1": 4096,
    "d2": 4096,
    "d3": 4096,
    "d4": 16000,   # more for thinking + output
    "d5": 8000,
}

VERIFY_CRITERIA = {
    "d1": (
        "Verify D1 (Recognition) output quality:\n"
        "1. Are ALL key components of the question identified?\n"
        "2. Does each component have a type (entity/relation/constraint/assumption)?\n"
        "3. Is depth level >= 3 for key components?\n"
        "4. Is the KEY CHALLENGE identified correctly?\n"
        "5. Did D1 stay in its lane (identify, not define or evaluate)?\n"
        "Compare with YOUR initial analysis — did D1 miss anything you saw?"
    ),
    "d2": (
        "Verify D2 (Clarification) output quality:\n"
        "1. Does every D1 component have a precise DEFINITION?\n"
        "2. Are ambiguities identified and resolved?\n"
        "3. Are hidden assumptions surfaced?\n"
        "4. Are domain-specific conventions noted where relevant?\n"
        "5. Is the CRITICAL CLARIFICATION meaningful (not generic)?"
    ),
    "d3": (
        "Verify D3 (Framework) output quality:\n"
        "1. Was framework chosen BEFORE any evaluation happened?\n"
        "2. Was at least one alternative considered and rejection explained?\n"
        "3. Does the framework PERMIT all possible answers (objectivity)?\n"
        "4. Are criteria clearly defined and measurable?\n"
        "5. Is the approach_plan concrete enough for D4 to follow?"
    ),
    "d4": (
        "Verify D4 (Comparison) output quality:\n"
        "1. Was EVERY D3 criterion applied to EVERY relevant component?\n"
        "2. Is evidence collected for AND against?\n"
        "3. Are gaps noted (missing information)?\n"
        "4. Are Aristotle's rules satisfied (same relation, criterion, state)?\n"
        "5. For calculations: are ALL steps shown explicitly?\n"
        "6. Is the computation_trace complete and correct?\n"
        "THIS IS THE MOST CRITICAL DOMAIN — check math/logic carefully."
    ),
    "d5": (
        "Verify D5 (Inference) output quality:\n"
        "1. Does the conclusion FOLLOW from D4 evidence (not invented)?\n"
        "2. Is certainty type correct (necessary/probabilistic/evaluative)?\n"
        "3. Overreach check: does conclusion go beyond evidence?\n"
        "4. Avoidance check: is an earned conclusion being evaded?\n"
        "5. Is the answer specific enough for HLE format?"
    ),
}


def load_prompt(filename):
    path = os.path.join(COMMANDS_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return f.read()


class AgentPipeline:
    def __init__(self, client, use_thinking=True):
        self.client = client
        self.use_thinking = use_thinking
        self.prompts = {k: load_prompt(v) for k, v in DOMAIN_FILES.items()}

    def _call(self, model, system, user_msg, max_tokens=8192, thinking_budget=0):
        """LLM call with optional extended thinking.
        Returns (text, thinking_text, input_tokens, output_tokens)."""
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user_msg}],
        }

        if self.use_thinking and thinking_budget > 0:
            # Extended thinking mode — temperature must not be set
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": thinking_budget,
            }
        else:
            kwargs["temperature"] = 0

        resp = self.client.messages.create(**kwargs)

        # Extract text and thinking from response blocks
        text = ""
        thinking_text = ""
        for block in resp.content:
            if block.type == "thinking":
                thinking_text = block.thinking
            elif block.type == "text":
                text = block.text

        return text, thinking_text, resp.usage.input_tokens, resp.usage.output_tokens

    def _build_context(self, question, outputs, domains_needed):
        parts = [f"QUESTION:\n{question}\n"]
        for d in domains_needed:
            if d in outputs:
                parts.append(f"--- {d.upper()} OUTPUT ---\n{outputs[d]}\n")
        return "\n".join(parts)

    def _team_lead_verify(self, domain, domain_output, question, plan, all_outputs):
        """Team Lead (Opus thinking) verifies a domain's output."""
        criteria = VERIFY_CRITERIA[domain]
        context_parts = [
            f"QUESTION:\n{question}\n",
            f"YOUR INITIAL PLAN:\n{plan}\n",
            f"--- {domain.upper()} OUTPUT TO VERIFY ---\n{domain_output}\n",
        ]
        for d in DOMAIN_INPUTS.get(domain, []):
            if d in all_outputs:
                context_parts.append(f"--- {d.upper()} OUTPUT (for reference) ---\n{all_outputs[d]}\n")

        verify_system = (
            "You are the Team Lead (L3 Meta-Operator) in Regulus. "
            "You are verifying a domain worker's output.\n\n"
            f"{criteria}\n\n"
            "Respond with EXACTLY this format:\n"
            "VERDICT: PASS or RETRY\n"
            "ISSUES: [list specific issues, or 'None' if PASS]\n"
            "FEEDBACK: [if RETRY: specific instructions for the worker to fix]\n\n"
            "Be strict but fair. PASS if output is good enough to proceed. "
            "RETRY only if there are concrete, fixable problems. "
            "Do NOT retry for minor style issues."
        )
        text, thinking, inp, out = self._call(
            OPUS, verify_system, "\n".join(context_parts),
            max_tokens=4096,  # 2000 thinking + 2096 response
            thinking_budget=THINKING_BUDGET["verify"],
        )
        passed = "VERDICT: PASS" in text.upper() or "VERDICT:PASS" in text.upper()
        return passed, text, thinking, inp + out

    def _run_domain_with_gate(self, domain, question, plan, outputs):
        """Run a domain worker, then Team Lead verifies. Retry once if needed."""
        needed = DOMAIN_INPUTS[domain]
        context = self._build_context(question, outputs, needed)
        system_prompt = self.prompts[domain]
        model = DOMAIN_MODELS[domain]
        thinking_budget = THINKING_BUDGET[domain]

        if domain == "d1":
            context = f"TEAM LEAD PLAN:\n{plan}\n\n{context}"

        # First attempt
        t0 = time.time()
        domain_text, domain_thinking, inp, out = self._call(
            model, system_prompt, context,
            max_tokens=DOMAIN_MAX_TOKENS[domain],
            thinking_budget=thinking_budget,
        )
        tokens_used = inp + out
        elapsed = time.time() - t0

        # Team Lead verification gate (always Opus thinking)
        passed, verify_text, verify_thinking, verify_tokens = self._team_lead_verify(
            domain, domain_text, question, plan, outputs
        )
        tokens_used += verify_tokens

        retried = False
        if not passed:
            # Retry with feedback
            retry_context = (
                f"{context}\n\n"
                f"--- YOUR PREVIOUS OUTPUT (REJECTED) ---\n{domain_text}\n\n"
                f"--- TEAM LEAD FEEDBACK ---\n{verify_text}\n\n"
                "Please redo your analysis addressing the Team Lead's feedback. "
                "Focus on the specific issues raised."
            )
            t0_retry = time.time()
            domain_text, domain_thinking, inp2, out2 = self._call(
                model, system_prompt, retry_context,
                max_tokens=DOMAIN_MAX_TOKENS[domain],
                thinking_budget=thinking_budget,
            )
            tokens_used += inp2 + out2
            elapsed += time.time() - t0_retry
            retried = True

        return {
            "text": domain_text,
            "thinking": domain_thinking,
            "verify_text": verify_text,
            "elapsed": elapsed,
            "tokens": tokens_used,
            "passed_first": passed,
            "retried": retried,
            "model": model,
        }

    def process_question(self, question_text, question_id):
        """Run full pipeline: plan → D1-D5 (with gates) → D6+assembly."""
        total_tokens = 0
        outputs = {}
        domain_times = {}
        gate_results = {}
        all_thinking = {}

        # Step 1: Team Lead initial plan (Opus thinking)
        plan_system = (
            "You are the Team Lead in Regulus, a structured reasoning system based on "
            "Theory of Systems. Analyze this question and create an initial plan.\n\n"
            "Output a JSON object with:\n"
            "- goal: what needs to be answered\n"
            "- complexity: easy/medium/hard\n"
            "- task_type: factual/analytical/evaluative/procedural\n"
            "- key_components: list of the main things in this question\n"
            "- plan: which domains need emphasis and why\n"
            "- potential_pitfalls: what could go wrong in reasoning\n\n"
            "Be thorough but concise. Output valid JSON only."
        )
        t0 = time.time()
        plan_text, plan_thinking, inp, out = self._call(
            OPUS, plan_system, question_text,
            max_tokens=8192,  # 4000 thinking + 4192 response
            thinking_budget=THINKING_BUDGET["plan"],
        )
        total_tokens += inp + out
        outputs["plan"] = plan_text
        all_thinking["plan"] = plan_thinking
        domain_times["plan"] = time.time() - t0
        print(f"plan({domain_times['plan']:.0f}s)", end=" ", flush=True)

        # Steps 2-6: D1 through D5, each with verification gate
        for domain in ["d1", "d2", "d3", "d4", "d5"]:
            result = self._run_domain_with_gate(
                domain, question_text, plan_text, outputs
            )
            total_tokens += result["tokens"]
            outputs[domain] = result["text"]
            all_thinking[domain] = result["thinking"]
            domain_times[domain] = round(result["elapsed"], 1)
            gate_results[domain] = {
                "passed_first": result["passed_first"],
                "retried": result["retried"],
                "model": result["model"],
            }

            # Status indicator: d1=Sonnet pass, D4R=Opus retry, etc.
            tag = domain
            model_tag = "S" if result["model"] == SONNET else "O"
            if result["retried"]:
                tag += "R"
            if not result["passed_first"]:
                tag = tag.upper()
            print(f"{tag}{model_tag}({result['elapsed']:.0f}s)", end=" ", flush=True)

        # Step 7: Main Agent does D6 (reflection) + assembly (Opus thinking)
        d6_system = (
            "You are the Team Lead in Regulus. You now perform D6 (Reflection) yourself "
            "and assemble the final answer.\n\n"
            "## D6 REFLECTION (do this first)\n"
            "Read ALL domain outputs D1-D5. Check:\n"
            "1. What SPECIFIC assumptions were made? (not generic disclaimers)\n"
            "2. Under what conditions does the D5 conclusion FAIL?\n"
            "3. Return assessment: look back at D1-D5 for errors.\n"
            "   - Did D1 miss components? Did D2 misdefine something?\n"
            "   - Did D3 pick the wrong framework? Did D4 compute correctly?\n"
            "   - Does D5's conclusion follow from D4's evidence?\n"
            "4. If you find errors, NOTE them and adjust.\n\n"
            "## FINAL ASSEMBLY (after reflection)\n"
            "Produce the final answer incorporating any corrections.\n\n"
            "Output format:\n"
            "REFLECTION: {your D6 analysis — specific issues found or 'No issues found'}\n"
            "CORRECTIONS: {any corrections to D5 answer, or 'None'}\n"
            "REASONING: {brief justification for final answer}\n"
            "CONFIDENCE: {0-100}%\n"
            "EXACT_ANSWER: {just the answer value — letter for MC, number for numerical, short text for open}\n\n"
            "Rules for EXACT_ANSWER:\n"
            "- Multiple choice: just the letter (e.g., EXACT_ANSWER: B)\n"
            "- Numerical: just the number (e.g., EXACT_ANSWER: 42)\n"
            "- Open-ended: shortest correct phrasing\n"
            "- No markdown, no quotes, no explanation on this line"
        )
        all_context = self._build_context(
            question_text, outputs,
            ["d1", "d2", "d3", "d4", "d5"],
        )
        all_context = f"YOUR INITIAL PLAN:\n{plan_text}\n\n{all_context}"

        t0 = time.time()
        d6_text, d6_thinking, inp, out = self._call(
            OPUS, d6_system, all_context,
            max_tokens=16000,  # 10000 thinking + 6000 response
            thinking_budget=THINKING_BUDGET["d6_assembly"],
        )
        total_tokens += inp + out
        outputs["d6_assembly"] = d6_text
        all_thinking["d6_assembly"] = d6_thinking
        domain_times["d6_assembly"] = time.time() - t0
        print(f"d6+asmO({domain_times['d6_assembly']:.0f}s)", end=" ", flush=True)

        return {
            "outputs": outputs,
            "thinking": all_thinking,
            "domain_times": domain_times,
            "gate_results": gate_results,
            "total_tokens": total_tokens,
        }


def extract_answer(text, answer_type):
    text = text.strip()

    m = re.search(r"EXACT_ANSWER:\s*(.+?)(?:\n|$)", text)
    if m:
        answer = m.group(1).strip().rstrip(".")
        if answer_type == "multipleChoice":
            letter = re.search(r"^([A-N])\b", answer)
            if letter:
                return letter.group(1)
        return answer

    m = re.search(r"\\boxed\{([^}]+)\}", text)
    if m:
        answer = m.group(1).strip()
        if answer_type == "multipleChoice":
            letter = re.search(r"^([A-N])\b", answer)
            if letter:
                return letter.group(1)
        return answer

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if answer_type == "multipleChoice":
        for line in reversed(lines):
            m = re.search(r"(?:answer|Answer)\s*(?:is|:)\s*\**([A-N])", line)
            if m:
                return m.group(1)
        for line in reversed(lines):
            m = re.search(r"\b([A-N])\b", line)
            if m:
                return m.group(1)

    return lines[-1].rstrip(".") if lines else ""


def extract_confidence(text):
    m = re.search(r"CONFIDENCE:\s*(\d+)%", text)
    return int(m.group(1)) if m else -1


def run_p3_batch(batch_name, use_thinking=True):
    base = os.path.dirname(os.path.abspath(__file__))
    q_path = os.path.join(base, "questions", f"{batch_name}.json")
    out_path = os.path.join(base, ".judge_only", f"p3_{batch_name}.json")
    workspace = os.path.join(base, "workspace", batch_name)

    if not os.path.exists(q_path):
        print(f"ERROR: Questions file not found: {q_path}")
        return

    with open(q_path, encoding="utf-8") as f:
        questions = json.load(f)

    for q in questions:
        if "answer" in q:
            print("ABORT: Question file contains 'answer' field -- contamination!")
            return

    thinking_label = "ON" if use_thinking else "OFF"
    print(f"Running P3 (Agent D1-D6 with gates) on {batch_name} ({len(questions)} questions)")
    print(f"Extended thinking: {thinking_label}")
    print(f"  D1, D2, D3 workers:        {SONNET}")
    print(f"  D4, D5 workers:            {OPUS} (thinking={thinking_label})")
    print(f"  Team Lead (plan+gate+D6):  {OPUS} (thinking={thinking_label})")
    print(f"Pipeline: plan -> [D1->gate] -> [D2->gate] -> [D3->gate] -> [D4->gate] -> [D5->gate] -> D6+assembly")
    print(f"Calls/q: 12 base + up to 5 retries")
    print()

    client = anthropic.Anthropic()
    pipeline = AgentPipeline(client, use_thinking=use_thinking)

    results = []
    os.makedirs(workspace, exist_ok=True)

    for i, q in enumerate(questions, 1):
        num = f"{i:02d}"
        subject = q.get("raw_subject", "?")[:25]
        print(f"  Q{num} {subject:25s} ", end="", flush=True)

        t0 = time.time()
        try:
            result_data = pipeline.process_question(q["question"], q["id"])
            elapsed = time.time() - t0

            d6_asm = result_data["outputs"].get("d6_assembly", "")
            extracted = extract_answer(d6_asm, q["answer_type"])
            confidence = extract_confidence(d6_asm)

            retries = sum(1 for g in result_data["gate_results"].values() if g["retried"])
            first_pass = sum(1 for g in result_data["gate_results"].values() if g["passed_first"])

            # Save workspace
            q_workspace = os.path.join(workspace, q["id"][:8])
            os.makedirs(q_workspace, exist_ok=True)
            for key, val in result_data["outputs"].items():
                with open(os.path.join(q_workspace, f"{key}.txt"), "w", encoding="utf-8") as wf:
                    wf.write(val)
            # Save thinking traces for debugging
            for key, val in result_data["thinking"].items():
                if val:
                    with open(os.path.join(q_workspace, f"{key}_thinking.txt"), "w", encoding="utf-8") as wf:
                        wf.write(val)
            with open(os.path.join(q_workspace, "gates.json"), "w", encoding="utf-8") as wf:
                json.dump(result_data["gate_results"], wf, indent=2)

            result = {
                "question_id": q["id"],
                "participant": "p3_agent_d1d6",
                "answer": extracted,
                "explanation": d6_asm,
                "confidence": confidence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tokens_used": result_data["total_tokens"],
                "time_seconds": round(elapsed, 1),
                "model": f"d1-d3={SONNET},d4-d5+lead={OPUS},thinking={thinking_label}",
                "agent_pipeline": {
                    "domains_run": 5,
                    "d6_by_lead": True,
                    "extended_thinking": use_thinking,
                    "domain_models": {d: DOMAIN_MODELS[d] for d in ["d1","d2","d3","d4","d5"]},
                    "domain_times": result_data["domain_times"],
                    "gate_results": result_data["gate_results"],
                    "retries": retries,
                    "first_pass_rate": f"{first_pass}/5",
                    "total_tokens": result_data["total_tokens"],
                },
                "contamination_check": {
                    "fresh_session": True,
                    "answer_file_read": False,
                },
            }
        except Exception as e:
            import traceback
            elapsed = time.time() - t0
            result = {
                "question_id": q["id"],
                "participant": "p3_agent_d1d6",
                "answer": f"ERROR: {e}",
                "explanation": traceback.format_exc(),
                "confidence": -1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tokens_used": 0,
                "time_seconds": round(elapsed, 1),
                "model": f"d1-d3={SONNET},d4-d5+lead={OPUS},thinking={thinking_label}",
                "agent_pipeline": {
                    "domains_run": 0,
                    "d6_by_lead": True,
                    "extended_thinking": use_thinking,
                    "domain_models": {},
                    "domain_times": {},
                    "gate_results": {},
                    "retries": 0,
                    "first_pass_rate": "0/5",
                    "total_tokens": 0,
                },
                "contamination_check": {
                    "fresh_session": True,
                    "answer_file_read": False,
                },
            }
            extracted = f"ERROR: {e}"

        results.append(result)
        safe = str(extracted)[:50].encode('ascii', 'replace').decode('ascii')
        print(f" -> '{safe}' [{elapsed:.0f}s]")

    # Save results
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Summary
    total_time = sum(r["time_seconds"] for r in results)
    total_tokens = sum(r["tokens_used"] for r in results)
    total_retries = sum(r["agent_pipeline"]["retries"] for r in results)
    errors = sum(1 for r in results if r["answer"].startswith("ERROR"))
    print(f"\nResults saved to {out_path}")
    print(f"Workspace saved to {workspace}")
    print(f"Questions: {len(results)}, errors: {errors}")
    print(f"Time: {total_time:.0f}s total, {total_time/len(results):.0f}s avg")
    print(f"Tokens: {total_tokens:,} total, {total_tokens//len(results):,} avg")
    print(f"Retries: {total_retries} total across all questions")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run P3 (Agent D1-D6 with gates) on HLE")
    parser.add_argument("--batch", required=True, help="Batch name (e.g. batch_004)")
    parser.add_argument("--no-thinking", action="store_true",
                        help="Disable extended thinking (faster/cheaper, lower quality)")
    args = parser.parse_args()

    run_p3_batch(args.batch, use_thinking=not args.no_thinking)
