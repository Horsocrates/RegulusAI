# HLE (Humanity's Last Exam) — Regulus Testing

## Structure

```
tests/HLE/
  pilot_10/
    questions.json          10 text-only HLE questions (seed=42)
    regulus/q01-q10_result.json   Regulus D1-D6 pipeline results
    baseline/q01-q10_result.json  Raw Opus single-shot results
    comparison.json               Side-by-side comparison
  run_baseline.py           Run raw Opus on any question set
  compare.py                Generate comparison table
  README.md                 This file
```

## Running

```bash
# Run baseline on questions
python tests/HLE/run_baseline.py tests/HLE/pilot_10/questions.json tests/HLE/pilot_10/baseline

# Generate comparison
python tests/HLE/compare.py tests/HLE/pilot_10
```

## Question Format (questions.json)

```json
[
  {
    "id": "hex-id",
    "question": "full question text",
    "answer": "expected answer",
    "answer_type": "multipleChoice|exactMatch",
    "category": "Math|Physics|...",
    "raw_subject": "specific subject"
  }
]
```

## Result Format (regulus/q*_result.json)

```json
{
  "question_id": "...",
  "subject": "...",
  "answer_type": "...",
  "expected": "...",
  "regulus_answer": "...",
  "correct": true/false,
  "confidence": 0-100,
  "wall_time_minutes": N,
  "estimated_cost_usd": N.NN
}
```

## Baseline Format (baseline/q*_result.json)

```json
{
  "question_id": "...",
  "expected": "...",
  "baseline_answer": "...",
  "correct": true/false,
  "response_time_s": N.N,
  "input_tokens": N,
  "output_tokens": N,
  "model": "model-id",
  "full_response": "complete model output"
}
```

## Comparison Categories

- **LIFT**: Regulus correct, Baseline wrong (Regulus added value)
- **BOTH**: Both correct (no difference)
- **HURT**: Regulus wrong, Baseline correct (Regulus hurt)
- **NEITHER**: Both wrong (both failed)

## Pilot Results (2026-02-08)

Regulus 8/10 (80%) vs Baseline 0/10 (0%). Net LIFT: +8 questions.
