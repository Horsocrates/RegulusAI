"""
Lab AI Analyst — analyzes failed question results to identify root causes.

Uses Anthropic SDK to call Claude for failure analysis.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from regulus.api.models.lab import Analysis, LabNewDB


ANALYST_PROMPT_PATH = (
    Path(__file__).parent.parent / "instructions" / "default" / "analyst.md"
)

COST_PER_INPUT_TOKEN = 3.0 / 1_000_000   # Claude Sonnet 4.5
COST_PER_OUTPUT_TOKEN = 15.0 / 1_000_000


class LabAnalyst:
    """Analyzes question results to determine why the model failed."""

    def __init__(
        self,
        db: LabNewDB,
        model: str = "claude-sonnet-4-5-20250929",
        api_key: Optional[str] = None,
    ):
        self.db = db
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._system_prompt: Optional[str] = None

    def _get_system_prompt(self) -> str:
        if self._system_prompt is None:
            self._system_prompt = ANALYST_PROMPT_PATH.read_text(encoding="utf-8")
        return self._system_prompt

    async def analyze_result(self, question_result_id: str) -> Analysis:
        """Run AI analysis on a question result. Returns the Analysis record."""
        from anthropic import AsyncAnthropic

        # 1. Get question result
        qr = self.db.get_question_result(question_result_id)
        if not qr:
            raise ValueError(f"Question result {question_result_id} not found")

        # 2. Check for existing completed analysis
        existing = self.db.get_analysis_for_result(question_result_id)
        if existing and existing.status == "completed":
            return existing

        # 3. Create analysis record (status=running)
        analysis = Analysis(
            question_result_id=question_result_id,
            status="running",
            model_used=self.model,
        )
        analysis = self.db.create_analysis(analysis)

        try:
            # 4. Build user prompt
            agent_outputs_str = ""
            if qr.agent_outputs:
                agent_outputs_str = json.dumps(qr.agent_outputs, indent=2)[:4000]

            user_prompt = (
                f"## Question\n{qr.input_text}\n\n"
                f"## Model Answer\n{qr.final_answer or '(no answer)'}\n\n"
                f"## Verdict: {qr.judgment_verdict or 'unknown'}\n\n"
                f"## Judgment Explanation\n{qr.judgment_explanation or '(none)'}\n\n"
            )
            if agent_outputs_str:
                user_prompt += f"## Agent Outputs (truncated)\n{agent_outputs_str}\n"

            # 5. Call Anthropic API
            client = AsyncAnthropic(api_key=self.api_key)
            start = time.time()
            response = await client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=self._get_system_prompt(),
                messages=[{"role": "user", "content": user_prompt}],
            )
            elapsed = time.time() - start

            raw_text = response.content[0].text
            tokens_in = response.usage.input_tokens
            tokens_out = response.usage.output_tokens
            cost = tokens_in * COST_PER_INPUT_TOKEN + tokens_out * COST_PER_OUTPUT_TOKEN

            # 6. Parse JSON response
            parsed = json.loads(raw_text)

            analysis.status = "completed"
            analysis.failure_category = parsed.get("failure_category", "other")
            analysis.root_cause = parsed.get("root_cause", "")
            analysis.summary = parsed.get("summary", "")
            analysis.recommendations = parsed.get("recommendations", [])
            analysis.raw_output = raw_text
            analysis.tokens_in = tokens_in
            analysis.tokens_out = tokens_out
            analysis.cost = round(cost, 6)
            analysis.completed_at = datetime.now(timezone.utc).isoformat()

        except Exception as e:
            analysis.status = "error"
            analysis.error_message = str(e)[:500]

        # 7. Update DB
        self.db.update_analysis(analysis)
        return analysis
