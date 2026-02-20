"""
HLE Judge -- uses o3-mini to evaluate model answers.
Follows official HLE evaluation protocol.

All answer-containing files live in .judge_only/ to prevent contamination.
This script reads answers and writes verdicts ONLY within .judge_only/.

Usage:
  python tests/HLE/judge.py --batch batch_001 --participant p2
  python tests/HLE/judge.py --batch batch_001 --participant p1
"""

import json
import argparse
import os

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

JUDGE_MODEL = "o3-mini-2025-01-31"

JUDGE_PROMPT = """Judge whether the following [response] to [question] is correct or not based on the precise and unambiguous [correct_answer] below.

Do not be excessively strict -- if the response contains the correct answer in a different but equivalent format (e.g., decimal vs fraction, different notation, reordered but equivalent expression), it should be judged correct. However, the answer must be substantively correct, not just close.

[question]: {question}
[response]: {response}
[correct_answer]: {correct_answer}

Respond with JSON:
{{
  "extracted_final_answer": "The final exact answer extracted from the response. Put 'None' if no exact final answer.",
  "reasoning": "Explain why correct or incorrect, focusing on meaningful differences.",
  "correct": true or false,
  "confidence": 0.0 to 1.0
}}"""


def judge_one(question: str, response: str, correct_answer: str, client: OpenAI) -> dict:
    """Judge a single question-response pair."""
    prompt = JUDGE_PROMPT.format(
        question=question,
        response=response,
        correct_answer=correct_answer,
    )

    result = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_completion_tokens=4096,
    )

    return json.loads(result.choices[0].message.content)


def main():
    parser = argparse.ArgumentParser(description="HLE Judge")
    parser.add_argument("--batch", required=True, help="Batch name (e.g. batch_001)")
    parser.add_argument("--participant", required=True, help="Participant (p1 or p2)")
    parser.add_argument("--judge-model", default=JUDGE_MODEL, help="Judge model to use")
    args = parser.parse_args()

    base = os.path.dirname(os.path.abspath(__file__))
    judge_dir = os.path.join(base, ".judge_only")

    # Results: .judge_only/{participant}_{batch}.json
    results_path = os.path.join(judge_dir, f"{args.participant}_{args.batch}.json")
    # Answers: .judge_only/answers/{batch}_answers.json
    answers_path = os.path.join(judge_dir, "answers", f"{args.batch}_answers.json")
    # Questions: questions/{batch}.json (safe — no answers)
    questions_path = os.path.join(base, "questions", f"{args.batch}.json")
    # Output: .judge_only/verdicts/{participant}_{batch}_verdict.json
    verdicts_dir = os.path.join(judge_dir, "verdicts")
    output_path = os.path.join(verdicts_dir, f"{args.participant}_{args.batch}_verdict.json")

    for path, label in [(results_path, "Results"), (answers_path, "Answers"), (questions_path, "Questions")]:
        if not os.path.exists(path):
            print(f"ERROR: {label} file not found: {path}")
            return

    # Load files (explicit UTF-8 for math symbols)
    with open(results_path, encoding="utf-8") as f:
        results_list = json.load(f)
    results = {r["question_id"]: r for r in results_list}

    with open(answers_path, encoding="utf-8") as f:
        answers_list = json.load(f)
    answers = {a["id"]: a["answer"] for a in answers_list}

    with open(questions_path, encoding="utf-8") as f:
        questions_list = json.load(f)
    questions = {q["id"]: q["question"] for q in questions_list}

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    print(f"Judging {args.participant} on {args.batch} ({len(results)} questions)")

    verdicts = []
    correct_count = 0
    total = 0

    for qid, result in results.items():
        if qid not in answers:
            print(f"WARNING: No ground truth for {qid}")
            continue

        response_text = result.get("answer", result.get("final_answer", ""))
        explanation = result.get("explanation", "")
        if explanation:
            response_text = f"{explanation}\n\nFinal answer: {response_text}"

        verdict = judge_one(
            question=questions.get(qid, ""),
            response=response_text,
            correct_answer=answers[qid],
            client=client,
        )
        verdict["question_id"] = qid
        verdict["participant"] = result.get("participant", "unknown")
        verdicts.append(verdict)

        if verdict["correct"]:
            correct_count += 1
        total += 1

        status = "+" if verdict["correct"] else "x"
        extracted = verdict.get("extracted_final_answer", "?")[:40]
        expected = answers[qid][:40]
        safe_extracted = extracted.encode('ascii', 'replace').decode('ascii')
        safe_expected = expected.encode('ascii', 'replace').decode('ascii')
        print(f"  {status} {qid[:8]}  model={safe_extracted}  expected={safe_expected}")

    acc = correct_count / total * 100 if total > 0 else 0
    print(f"\nResult: {correct_count}/{total} ({acc:.1f}%)")

    output = {
        "judge_model": args.judge_model,
        "total": total,
        "correct": correct_count,
        "accuracy": correct_count / total if total > 0 else 0,
        "verdicts": verdicts,
    }

    os.makedirs(verdicts_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Verdicts saved to {output_path}")


if __name__ == "__main__":
    main()
