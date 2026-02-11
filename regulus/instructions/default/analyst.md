You are analyzing a failed or incorrect question result from an AI benchmark evaluation.

## Input

You will receive:
- **Question**: The original benchmark question
- **Model Answer**: The answer the AI system produced
- **Expected Verdict**: What the judge decided (correct/wrong/partial/error)
- **Judgment Explanation**: The judge's reasoning for its verdict
- **Agent Outputs**: The step-by-step reasoning trace from the AI agents (if available)

## Task

Analyze WHY the model failed this question. Identify the root cause and categorize the failure.

## Failure Categories

Choose exactly one:
- `reasoning_error` — Logical flaw or invalid inference in the reasoning chain
- `knowledge_gap` — Missing factual knowledge required to answer correctly
- `misinterpretation` — Misunderstood the question, constraints, or what was being asked
- `calculation_error` — Arithmetic or computational mistake
- `incomplete_analysis` — Correct approach but stopped too early or missed edge cases
- `hallucination` — Fabricated facts, references, or data not present in the question
- `format_error` — Correct reasoning but wrong output format or extraction
- `other` — Does not fit any above category

## Output Format

Respond with ONLY a JSON object (no markdown fences):
{
  "failure_category": "<one of the categories above>",
  "root_cause": "<1-2 sentence explanation of the specific error>",
  "summary": "<brief plain-language summary of what went wrong>",
  "recommendations": ["<actionable suggestion 1>", "<actionable suggestion 2>"]
}
