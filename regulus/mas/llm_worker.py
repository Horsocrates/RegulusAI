"""
Regulus AI - LLM Domain Worker
================================

Real LLM-powered domain worker. Sends structured prompts to an LLM,
parses JSON responses, and returns typed domain outputs + DomainOutput
for the TaskTable.
"""

import json
import re
import time
from typing import Any

from regulus.llm.client import LLMClient, LLMResponse
from regulus.mas.types import DomainStatus
from regulus.mas.table import Component, DomainOutput
from regulus.mas.workers import DomainWorker
from regulus.mas.contracts import (
    DomainInput,
    D1Input, D1Output, D2Input, D2Output,
    D3Input, D3Output, D4Input, D4Output,
    D5Input, D5Output, D6Input, D6Output,
)
from regulus.mas.prompts import DOMAIN_PROMPTS


class WorkerError(Exception):
    """Error raised by a domain worker."""

    def __init__(self, domain: str, message: str, recoverable: bool = True):
        self.domain = domain
        self.recoverable = recoverable
        super().__init__(f"[{domain}] {message}")


class LLMWorker(DomainWorker):
    """
    Domain worker that uses an LLM to produce domain outputs.

    Each worker is bound to one domain and one LLM client.
    The worker_factory creates instances based on routing config.
    """

    def __init__(self, domain: str, llm_client: LLMClient, max_retries: int = 1):
        if domain not in DOMAIN_PROMPTS:
            raise ValueError(f"Unknown domain: {domain}. Expected D1-D6.")
        self._domain = domain
        self._llm = llm_client
        self._max_retries = max_retries
        self._prompt_module = DOMAIN_PROMPTS[domain]

    @property
    def domain_code(self) -> str:
        return self._domain

    async def process(
        self,
        component: Component,
        domain_input: DomainInput,
        model: str,
    ) -> DomainOutput:
        """
        Process a domain via LLM call. Returns DomainOutput for the TaskTable.
        Typed output is attached as ._typed_output for domain chaining.
        """
        system_prompt = self._prompt_module.SYSTEM_PROMPT
        user_prompt = self._build_user_prompt(domain_input)

        last_error = None
        for attempt in range(1 + self._max_retries):
            start = time.time()

            try:
                response = await self._llm.generate_with_usage(
                    user_prompt, system=system_prompt
                )

                raw_data = _parse_json_response(response.text)
                typed_output = self._build_typed_output(raw_data, response)
                elapsed = time.time() - start

                if attempt > 0:
                    typed_output.internal_log = (
                        f"[RETRY: Succeeded on attempt {attempt + 1}] "
                        + (typed_output.internal_log or "")
                    )

                # Build DomainOutput for TaskTable
                domain_output = self._build_domain_output(
                    typed_output, response, model, elapsed,
                )
                domain_output._typed_output = typed_output
                return domain_output

            except json.JSONDecodeError as e:
                last_error = e
                if attempt < self._max_retries:
                    continue
            except WorkerError:
                raise
            except Exception as e:
                raise WorkerError(
                    domain=self._domain,
                    message=f"LLM call failed: {e}",
                    recoverable=False,
                )

        raise WorkerError(
            domain=self._domain,
            message=f"JSON parse failed after {1 + self._max_retries} attempts: {last_error}",
            recoverable=True,
        )

    def _build_user_prompt(self, domain_input: DomainInput) -> str:
        """Build domain-specific user prompt from typed input."""
        query = domain_input.query
        goal = domain_input.goal or domain_input.query

        if self._domain == "D1":
            return self._prompt_module.build_user_prompt(
                query=query, goal=goal,
            )

        elif self._domain == "D2":
            return self._prompt_module.build_user_prompt(
                query=query, goal=goal,
                components_json=_to_json(getattr(domain_input, 'components', [])),
            )

        elif self._domain == "D3":
            return self._prompt_module.build_user_prompt(
                query=query, goal=goal,
                components_json=_to_json(getattr(domain_input, 'components', [])),
            )

        elif self._domain == "D4":
            return self._prompt_module.build_user_prompt(
                query=query, goal=goal,
                components_json=_to_json(getattr(domain_input, 'components', [])),
                framework_json=_to_json(getattr(domain_input, 'framework', {})),
            )

        elif self._domain == "D5":
            return self._prompt_module.build_user_prompt(
                query=query, goal=goal,
                comparisons_json=_to_json(getattr(domain_input, 'comparisons', [])),
                framework_json=_to_json(getattr(domain_input, 'framework', {})),
            )

        elif self._domain == "D6":
            return self._prompt_module.build_user_prompt(
                query=query, goal=goal,
                conclusion_json=_to_json(getattr(domain_input, 'conclusion', {})),
                full_table_summary=getattr(domain_input, 'table_summary', ""),
            )

        raise ValueError(f"Unhandled domain: {self._domain}")

    def _build_typed_output(self, data: dict, response: LLMResponse) -> Any:
        """Build typed domain output from parsed JSON."""
        internal_log = data.pop("internal_log", "")

        if self._domain == "D1":
            return D1Output(
                components=data.get("components", []),
                task_type=data.get("task_type", "analytical"),
                content=internal_log,
                internal_log=internal_log,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )

        elif self._domain == "D2":
            return D2Output(
                components=data.get("components", []),
                hidden_assumptions=data.get("hidden_assumptions", []),
                content=internal_log,
                internal_log=internal_log,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )

        elif self._domain == "D3":
            return D3Output(
                framework=data.get("framework", {}),
                objectivity=data.get("objectivity", {}),
                content=internal_log,
                internal_log=internal_log,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )

        elif self._domain == "D4":
            return D4Output(
                comparisons=data.get("comparisons", []),
                aristotle_check=data.get("aristotle_check", {}),
                coverage=data.get("coverage", {}),
                content=internal_log,
                internal_log=internal_log,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )

        elif self._domain == "D5":
            conclusion = data.get("conclusion", {})
            answer = conclusion.get("answer", "") if isinstance(conclusion, dict) else ""
            certainty = conclusion.get("certainty_type", "probabilistic") if isinstance(conclusion, dict) else ""
            return D5Output(
                conclusion=conclusion,
                answer=answer,
                certainty_type=certainty,
                logical_form=data.get("logical_form", ""),
                overreach_check=data.get("overreach_check", ""),
                avoidance_check=data.get("avoidance_check", ""),
                content=answer,
                internal_log=internal_log,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )

        elif self._domain == "D6":
            return D6Output(
                scope=data.get("scope", {}),
                assumptions=data.get("assumptions", []),
                limitations=data.get("limitations", []),
                new_questions=data.get("new_questions", []),
                return_assessment=data.get("return_assessment", {}),
                content=internal_log,
                internal_log=internal_log,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )

        raise ValueError(f"Unhandled domain: {self._domain}")

    def _build_domain_output(
        self, typed_output: Any, response: LLMResponse,
        model: str, elapsed: float,
    ) -> DomainOutput:
        """Convert typed output into DomainOutput for the TaskTable."""
        # D5 answer goes into content; others use internal_log
        content = getattr(typed_output, 'answer', '') or getattr(typed_output, 'content', '')

        return DomainOutput(
            domain=self._domain,
            status=DomainStatus.COMPLETED,
            content=content,
            weight=75,  # base weight for valid LLM response
            e_exists=True,
            r_exists=True,
            rule_exists=True,
            s_exists=True,
            deps_declared=True,
            l1_l3_ok=True,
            l5_ok=True,
            issues=[],
            model_used=model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            time_seconds=elapsed,
        )


def _parse_json_response(raw: str) -> dict:
    """Parse JSON from LLM response with robust recovery."""
    text = raw.strip()

    # Strip markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Extract first JSON object via bracket matching
    start = text.find("{")
    if start == -1:
        raise json.JSONDecodeError("No JSON object found", text[:200], 0)

    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(text)):
        c = text[i]
        if escape_next:
            escape_next = False
            continue
        if c == "\\":
            escape_next = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                extracted = text[start:i + 1]
                try:
                    return json.loads(extracted)
                except json.JSONDecodeError:
                    break

    # Fix trailing commas
    candidate = text[start:]
    candidate = re.sub(r',\s*}', '}', candidate)
    candidate = re.sub(r',\s*]', ']', candidate)
    return json.loads(candidate)


def _to_json(obj: Any) -> str:
    """Serialize an object to compact JSON for prompt inclusion."""
    if isinstance(obj, str):
        return obj
    if hasattr(obj, '__dict__'):
        return json.dumps(obj.__dict__, indent=2, ensure_ascii=False, default=str)
    return json.dumps(obj, indent=2, ensure_ascii=False, default=str)
