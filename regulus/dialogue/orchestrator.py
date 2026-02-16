"""
Regulus AI - Dialogue Orchestrator
====================================

Core two-agent pipeline: Team Lead (meta-cognition, D6) and Worker
(domain reasoning, D1-D5) conduct a continuous multi-turn dialogue.

The orchestrator manages:
- Phase 0: TL ASK (question analysis, erfragte, root question)
- Phases 1-5: Domain loop D1→D5 (Worker executes, TL reflects)
- Convergence control (verdict-based flow: pass/iterate/paradigm_shift)
- Worker replacement (fresh context with conspectus handoff)
- Audit trail (JSONL logging, state persistence)

Returns MASResponse for compatibility with lab executor.
"""

import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from regulus.dialogue.agent import Agent, AgentConfig
from regulus.dialogue.channel import DialogueChannel
from regulus.dialogue.conspectus import Conspectus
from regulus.dialogue.prompts import (
    DEFAULT_PROFILE,
    build_team_lead_system_prompt,
    build_worker_system_prompt,
    find_skills_dir,
)
from regulus.dialogue.state import RunState
from regulus.mas.types import MASResponse


# Domain sequence for the Worker
DOMAINS = ["D1", "D2", "D3", "D4", "D5"]

# Token threshold for worker replacement
WORKER_TOKEN_LIMIT = 100_000


class DialogueOrchestrator:
    """Two-agent dialogue pipeline orchestrator.

    Team Lead (meta-cognition, D6-ASK + D6-REFLECT) and Worker
    (domain reasoning, D1-D5) engage in structured multi-turn dialogue.
    The orchestrator bridges them, managing convergence and worker lifecycle.
    """

    def __init__(
        self,
        profile_config: Optional[dict] = None,
        skills_dir: Optional[Path] = None,
        runs_dir: Optional[Path] = None,
        api_key: Optional[str] = None,
        on_domain_start: Optional[Callable] = None,
        on_domain_complete: Optional[Callable] = None,
        on_correction: Optional[Callable] = None,
    ):
        self.profile = profile_config or DEFAULT_PROFILE
        self.skills_dir = skills_dir or find_skills_dir()
        self.runs_dir = runs_dir or Path("data/dialogue_runs")
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._api_key = api_key

        self._on_domain_start = on_domain_start
        self._on_domain_complete = on_domain_complete
        self._on_correction = on_correction

    async def process_query(self, query: str) -> MASResponse:
        """Run the full two-agent dialogue pipeline.

        Returns MASResponse for compatibility with lab executor.
        """
        start_time = time.time()
        run_id = f"dlg_{uuid.uuid4().hex[:12]}"
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Initialize state, conspectus, and dialogue channel
        state = RunState(run_id=run_id, question=query, status="running")
        state.init_domains()
        conspectus = Conspectus(original_question=query)
        channel = DialogueChannel(run_dir)

        try:
            # Build agents
            tl_agent = self._create_team_lead()
            worker_agent = self._create_worker()

            # Phase 0: TL ASK — question analysis
            self._emit_domain_start("D6-ASK", "Question Analysis")
            tl_ask_prompt = (
                f"MODE: ask\n"
                f"CONTEXT: initial\n\n"
                f"Question:\n{query}"
            )
            channel.log("orchestrator", "team_lead", "ask", tl_ask_prompt)
            tl_response = await tl_agent.send(tl_ask_prompt)
            channel.log("team_lead", "orchestrator", "ask_response", tl_response)

            # Update conspectus from TL response
            conspectus.update_from_tl_response(tl_response)
            worker_instruction = _extract_xml(tl_response, "worker_instruction")

            self._emit_domain_complete("D6-ASK", {
                "root_question": conspectus.root_question,
                "erfragte": conspectus.erfragte,
            })

            # Update token state
            state.tokens.team_lead_input = tl_agent.total_input_tokens
            state.tokens.team_lead_output = tl_agent.total_output_tokens
            state.tokens.cache_creation_tokens = (
                tl_agent.cache_creation_tokens + worker_agent.cache_creation_tokens
            )
            state.tokens.cache_read_tokens = (
                tl_agent.cache_read_tokens + worker_agent.cache_read_tokens
            )

            # Phase 1-5: Domain loop
            domain_idx = 0
            while domain_idx < len(DOMAINS):
                domain = DOMAINS[domain_idx]

                # Check convergence before each domain
                should_stop, stop_reason = state.should_stop(self.profile)
                if should_stop:
                    channel.log(
                        "orchestrator", "system", "convergence_stop",
                        f"Stopping: {stop_reason}",
                    )
                    break

                # Maybe replace worker (token limit or preemptive)
                worker_agent = await self._maybe_replace_worker(
                    worker_agent, conspectus, channel, state, domain_idx,
                )

                # Worker executes domain
                self._emit_domain_start(domain, f"Domain {domain}")
                state.update_domain(domain, "running")

                instruction = (
                    worker_instruction
                    if worker_instruction
                    else f"Execute domain {domain} for the question."
                )
                worker_prompt = (
                    f"DOMAIN: {domain}\n\n"
                    f"Instruction from Team Lead:\n{instruction}\n\n"
                    f"Original question:\n{query}"
                )
                channel.log(
                    "orchestrator", "worker", "domain_instruction",
                    worker_prompt, domain=domain,
                )

                worker_response = await worker_agent.send(worker_prompt)
                channel.log(
                    "worker", "orchestrator", "domain_output",
                    worker_response, domain=domain,
                )

                # Update worker token tracking
                state.tokens.worker_input = worker_agent.total_input_tokens
                state.tokens.worker_output = worker_agent.total_output_tokens

                # TL REFLECT on worker output
                reflect_depth = "quick" if domain in ("D1", "D2") else "full"
                tl_reflect_prompt = (
                    f"MODE: reflect\n"
                    f"DEPTH: {reflect_depth}\n"
                    f"DOMAIN: {domain}\n\n"
                    f"Worker output:\n{worker_response}\n\n"
                    f"Current conspectus:\n{conspectus.to_markdown()}"
                )
                channel.log(
                    "orchestrator", "team_lead", "reflect",
                    tl_reflect_prompt, domain=domain,
                )

                tl_response = await tl_agent.send(tl_reflect_prompt)
                channel.log(
                    "team_lead", "orchestrator", "reflect_response",
                    tl_response, domain=domain,
                )

                # Update TL token tracking
                state.tokens.team_lead_input = tl_agent.total_input_tokens
                state.tokens.team_lead_output = tl_agent.total_output_tokens
                state.tokens.cache_creation_tokens = (
                    tl_agent.cache_creation_tokens
                    + worker_agent.cache_creation_tokens
                )
                state.tokens.cache_read_tokens = (
                    tl_agent.cache_read_tokens
                    + worker_agent.cache_read_tokens
                )

                # Parse TL verdict and update state
                conspectus.update_from_tl_response(tl_response)
                verdict = _extract_xml(tl_response, "verdict").strip().lower()
                worker_instruction = _extract_xml(tl_response, "worker_instruction")
                confidence = _extract_confidence(tl_response)

                # Update domain state
                state.update_domain(domain, "complete", confidence=confidence)
                state.record_iteration(confidence or 0)

                self._emit_domain_complete(domain, {
                    "verdict": verdict,
                    "confidence": confidence,
                })

                # Verdict-based flow control
                if verdict == "pass":
                    domain_idx += 1
                elif verdict == "iterate":
                    # Re-run the same domain
                    self._emit_correction(domain, state.convergence.iteration, verdict)
                    state.update_domain(domain, "running")
                    # domain_idx stays the same
                elif verdict == "paradigm_shift":
                    # Check if paradigm shifts allowed
                    max_shifts = self.profile.get("convergence", {}).get(
                        "max_paradigm_shifts", 1
                    )
                    if state.convergence.paradigm_shifts_used < max_shifts:
                        state.convergence.paradigm_shifts_used += 1
                        state.convergence.paradigm_history.append(
                            f"Shift at {domain}, iteration {state.convergence.iteration}"
                        )
                        self._emit_correction(domain, state.convergence.iteration, verdict)
                        # Reset to D3
                        domain_idx = DOMAINS.index("D3")
                    else:
                        # No more shifts allowed, continue forward
                        domain_idx += 1
                elif verdict in ("threshold_reached", "plateau", "fundamentally_uncertain"):
                    # Early termination
                    channel.log(
                        "orchestrator", "system", "early_stop",
                        f"Early stop: {verdict}",
                    )
                    break
                else:
                    # Unknown verdict — treat as pass
                    domain_idx += 1

            # Persist conspectus and state
            conspectus.save(run_dir)
            state.status = "completed"
            state.save(run_dir)

            # Build final answer from last TL response or conspectus
            answer = _extract_final_answer(tl_response, conspectus)

            elapsed = time.time() - start_time

            # Build and persist reasoning passport
            passport = self._build_passport(
                run_dir, state, conspectus, answer, elapsed,
            )
            (run_dir / "passport.json").write_text(
                json.dumps(passport, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # Build audit summary
            domain_confidences = {}
            for d, ds in state.domains.items():
                if ds.confidence is not None:
                    domain_confidences[d] = ds.confidence

            audit_summary = {
                "pipeline": "dialogue",
                "run_id": run_id,
                "domains_completed": sum(
                    1 for ds in state.domains.values() if ds.status == "complete"
                ),
                "domain_confidences": domain_confidences,
                "convergence_iterations": state.convergence.iteration,
                "paradigm_shifts": state.convergence.paradigm_shifts_used,
                "workers_spawned": state.workers.total_spawned,
                "tl_messages": tl_agent.message_count,
                "worker_messages": worker_agent.message_count,
                "cache_read_tokens": state.tokens.cache_read_tokens,
                "cache_creation_tokens": state.tokens.cache_creation_tokens,
            }

            return MASResponse(
                query=query,
                answer=answer,
                valid=True,
                complexity="dialogue",
                components_count=1,
                task_table_json="",
                audit_summary=audit_summary,
                corrections=state.convergence.paradigm_shifts_used,
                time_seconds=elapsed,
                input_tokens=state.tokens.team_lead_input + state.tokens.worker_input,
                output_tokens=state.tokens.team_lead_output + state.tokens.worker_output,
            )

        except Exception as e:
            state.status = "failed"
            state.save(run_dir)
            channel.log("orchestrator", "system", "error", str(e))
            raise
        finally:
            channel.close()

    # ------------------------------------------------------------------
    # Agent factory
    # ------------------------------------------------------------------

    def _create_team_lead(self) -> Agent:
        """Create a Team Lead agent with D6-ASK/REFLECT skills."""
        system_prompt = build_team_lead_system_prompt(
            self.skills_dir, self.profile,
        )
        config = AgentConfig(
            name="TeamLead",
            model="claude-opus-4-6",
            system_prompt=system_prompt,
            max_output_tokens=64000,
            thinking_budget=10000,
            interleaved_thinking=True,
        )
        return Agent(config, api_key=self._api_key)

    def _create_worker(self) -> Agent:
        """Create a fresh Worker agent with D1-D5 skills."""
        system_prompt = build_worker_system_prompt(self.skills_dir)
        config = AgentConfig(
            name="Worker",
            model="claude-opus-4-6",
            system_prompt=system_prompt,
            max_output_tokens=64000,
            thinking_budget=16000,
            interleaved_thinking=True,
        )
        return Agent(config, api_key=self._api_key)

    # ------------------------------------------------------------------
    # Worker replacement
    # ------------------------------------------------------------------

    async def _maybe_replace_worker(
        self,
        worker: Agent,
        conspectus: Conspectus,
        channel: DialogueChannel,
        state: RunState,
        domain_idx: int,
    ) -> Agent:
        """Replace the Worker if it's approaching token limits.

        Conditions for replacement:
        1. Worker total tokens > WORKER_TOKEN_LIMIT
        2. Preemptive replacement after N domains (configurable)

        The new Worker receives the conspectus as context handoff.
        """
        worker_tokens = worker.total_input_tokens + worker.total_output_tokens
        preemptive = self.profile.get("worker", {}).get("preemptive_replacement", True)
        preemptive_after = self.profile.get("worker", {}).get(
            "preemptive_after_domains", 4
        )

        should_replace = (
            worker_tokens > WORKER_TOKEN_LIMIT
            or (preemptive and domain_idx >= preemptive_after)
        )

        if not should_replace or worker.message_count == 0:
            return worker

        # Spawn fresh worker
        channel.log(
            "orchestrator", "system", "worker_replacement",
            f"Replacing worker (tokens={worker_tokens}, domains={domain_idx})",
        )
        state.workers.total_spawned += 1
        state.workers.current_instance += 1

        new_worker = self._create_worker()

        # Handoff: send conspectus as first message
        handoff_msg = (
            "You are continuing a reasoning task. A previous Worker completed "
            "earlier domains. The Team Lead's conspectus below summarizes all "
            "progress so far.\n\n"
            f"CONSPECTUS:\n{conspectus.to_markdown()}\n\n"
            "Acknowledge and await your next domain instruction."
        )
        channel.log("orchestrator", "worker", "handoff", handoff_msg)
        ack = await new_worker.send(handoff_msg)
        channel.log("worker", "orchestrator", "handoff_ack", ack)

        return new_worker

    # ------------------------------------------------------------------
    # Reasoning Passport
    # ------------------------------------------------------------------

    def _build_passport(
        self,
        run_dir: Path,
        state: RunState,
        conspectus: Conspectus,
        answer: str,
        elapsed: float,
    ) -> dict:
        """Assemble a full reasoning passport from the dialogue log.

        The passport is a structured archive of the COMPLETE reasoning trace
        for post-mortem analysis, failure investigation, and training data export.
        """
        # Read dialogue log
        dialogue: list[dict] = []
        log_path = run_dir / "dialogue.jsonl"
        if log_path.exists():
            for line in log_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    dialogue.append(json.loads(line))

        # Extract classification from TL ask response
        classification: dict = {}
        for msg in dialogue:
            if msg.get("type") == "ask_response":
                content = msg.get("content", "")
                # Try to parse JSON classification from TL output
                task_type_m = re.search(
                    r'"task_type"\s*:\s*"([^"]+)"', content
                )
                skill_type_m = re.search(
                    r'"skill_type"\s*:\s*"([^"]+)"', content
                )
                complexity_m = re.search(
                    r'"complexity"\s*:\s*"([^"]+)"', content
                )
                skill_conf_m = re.search(
                    r'"skill_confidence"\s*:\s*(\d+)', content
                )
                classification = {
                    "complexity": complexity_m.group(1) if complexity_m else "unknown",
                    "task_type": task_type_m.group(1) if task_type_m else "unknown",
                    "skill_type": skill_type_m.group(1) if skill_type_m else "unknown",
                    "skill_confidence": (
                        int(skill_conf_m.group(1)) if skill_conf_m else None
                    ),
                }
                break

        # Extract per-domain full outputs and TL reflections
        domains_data: dict[str, dict] = {}
        for msg in dialogue:
            msg_type = msg.get("type", "")
            domain = msg.get("domain", "")
            if not domain:
                continue

            if msg_type == "domain_output":
                # Worker output for this domain
                if domain not in domains_data:
                    domains_data[domain] = {
                        "full_output": msg.get("content", ""),
                        "iterations": 0,
                    }
                else:
                    # This is a redo/iteration
                    domains_data[domain]["iterations"] += 1
                    domains_data[domain].setdefault("iteration_log", [])
                    domains_data[domain]["iteration_log"].append({
                        "output": msg.get("content", ""),
                        "trigger": domain,
                    })

            elif msg_type == "reflect_response":
                # TL reflection for this domain
                if domain in domains_data:
                    content = msg.get("content", "")
                    verdict = _extract_xml(content, "verdict").strip().lower()
                    conf = _extract_confidence(content)
                    domains_data[domain]["tl_verdict"] = verdict
                    domains_data[domain]["confidence"] = conf
                    # Truncate reflection to 500 chars for passport
                    domains_data[domain]["tl_reflection"] = content[:500]

        # Merge confidence from state into domain data
        for d, ds in state.domains.items():
            if d in domains_data and ds.confidence is not None:
                domains_data[d]["confidence"] = ds.confidence

        # Final confidence from last history entry
        final_confidence = (
            state.convergence.confidence_history[-1]
            if state.convergence.confidence_history
            else None
        )

        # Determine final verdict
        final_verdict = "completed"
        if state.convergence.confidence_history:
            threshold = self.profile.get("convergence", {}).get(
                "confidence_threshold", 85,
            )
            if final_confidence and final_confidence >= threshold:
                final_verdict = "threshold_reached"
            elif state.convergence.stall_count >= self.profile.get(
                "convergence", {},
            ).get("stall_limit", 2):
                final_verdict = "plateau"

        # Read conspectus markdown
        conspectus_md = ""
        conspectus_path = run_dir / "conspectus.md"
        if conspectus_path.exists():
            conspectus_md = conspectus_path.read_text(encoding="utf-8")

        from dataclasses import asdict

        return {
            "version": "1.0",
            "run_id": state.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "question": {
                "text": state.question,
            },
            "classification": classification,
            "result": {
                "answer": answer,
                "confidence": final_confidence,
                "verdict": final_verdict,
                "correct": None,  # filled by judge later
            },
            "profile": state.profile,
            "domains": domains_data,
            "convergence": {
                "total_iterations": state.convergence.iteration,
                "confidence_history": state.convergence.confidence_history,
                "paradigm_shifts": state.convergence.paradigm_shifts_used,
                "paradigm_history": state.convergence.paradigm_history,
            },
            "conspectus_final": conspectus_md,
            "resources": {
                "workers_spawned": state.workers.total_spawned,
                "total_tokens": asdict(state.tokens),
                "time_seconds": round(elapsed, 1),
            },
        }

    # ------------------------------------------------------------------
    # Callback helpers
    # ------------------------------------------------------------------

    def _emit_domain_start(self, domain: str, name: str) -> None:
        if self._on_domain_start:
            self._on_domain_start(domain, name)

    def _emit_domain_complete(self, domain: str, data: dict) -> None:
        if self._on_domain_complete:
            self._on_domain_complete(domain, data)

    def _emit_correction(
        self, domain: str, attempt: int, verdict: str,
    ) -> None:
        if self._on_correction:
            self._on_correction(domain, attempt, verdict, f"TL verdict: {verdict}")


# ---------------------------------------------------------------------------
# XML / text extraction helpers
# ---------------------------------------------------------------------------

def _extract_xml(text: str, tag: str) -> str:
    """Extract content between <tag>...</tag>. Returns empty string if absent."""
    pattern = re.compile(rf"<{tag}>(.*?)</{tag}>", re.DOTALL | re.IGNORECASE)
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _extract_confidence(text: str) -> Optional[int]:
    """Extract a confidence percentage from TL response text."""
    # Try verdict-adjacent confidence first
    m = re.search(r"[Cc]onfidence[:\s]*(\d+)%?", text)
    if m:
        return int(m.group(1))
    # Try from conspectus convergence state
    m = re.search(r"overall[:\s]*(\d+)%?", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _extract_final_answer(tl_response: str, conspectus: Conspectus) -> str:
    """Extract the final answer from the last TL response.

    Priority:
    1. <answer>...</answer> block in TL response
    2. <worker_instruction> if it contains a final answer
    3. Concatenation of domain summaries from conspectus
    """
    # Try explicit answer block
    answer = _extract_xml(tl_response, "answer")
    if answer:
        return answer

    # Try worker_instruction (TL sometimes puts the final answer there)
    instruction = _extract_xml(tl_response, "worker_instruction")
    if instruction and len(instruction) > 50:
        return instruction

    # Fallback: build from conspectus domain summaries
    if conspectus.domain_summaries:
        parts = []
        for domain in sorted(conspectus.domain_summaries.keys()):
            ds = conspectus.domain_summaries[domain]
            parts.append(f"[{domain}] {ds.summary}")
        return "\n\n".join(parts)

    return "No answer produced."
