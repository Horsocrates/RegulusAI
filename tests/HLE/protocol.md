# REGULUS × HLE — Evaluation Protocol v1

**Date:** 2026-02-08
**Status:** MANDATORY — all HLE runs must follow this protocol
**Previous results:** Pilot 10 (clean: 8/10), Batch 20 Q01-Q13 (CONTAMINATED), Q14-Q20 (clean: 3/7)
**Clean total:** 11/17 = 65%

---

## 1. CONTAMINATION PREVENTION — IRON RULES

### Rule 1: Questions and Answers are ALWAYS in Separate Files

```
tests/HLE/questions/          <- Questions ONLY (no answers)
  batch_001.json              <- {id, question, answer_type, category, raw_subject}
  batch_002.json
  ...

tests/HLE/answers/            <- Answers ONLY (never loaded by test agent)
  batch_001_answers.json      <- {id, answer}
  batch_002_answers.json
  ...
```

**The test agent (Claude Code) NEVER reads files from tests/HLE/answers/**
**The judge script reads both to compare.**

### Rule 2: Question Files Have No Answer Field

```json
// CORRECT — questions file:
{"id": "abc123", "question": "What is...", "answer_type": "exact_match", "category": "Mathematics"}

// WRONG — this is contamination:
{"id": "abc123", "question": "What is...", "answer": "42", "answer_type": "exact_match"}
```

### Rule 3: Each Batch Starts a Fresh Session

Before starting a new batch of questions:
- Start a new Claude Code session (or use `claude --resume no`)
- Verify the context contains NO answer data from previous runs
- The `/analyze` command reads ONLY from `tests/HLE/questions/`

### Rule 4: Judge Runs Separately

The judge is a Python script (`tests/HLE/judge.py`) that:
1. Reads the model's answers from `tests/HLE/results/`
2. Reads ground truth from `tests/HLE/answers/`
3. Calls o3-mini to compare
4. Writes verdict to `tests/HLE/verdicts/`

The judge NEVER runs inside the test agent's session.

### Rule 5: Audit Trail

Every result file records:
```json
{
  "question_id": "abc123",
  "session_id": "claude-session-xyz",
  "timestamp": "2026-02-08T15:30:00Z",
  "contamination_check": {
    "answer_file_read": false,
    "fresh_session": true,
    "context_clean": true
  }
}
```

---

## 2. PARTICIPANTS

### P1: Raw Opus 4.6 (No Tools)
- Single API prompt, no pipeline, no tools, no code execution
- Official HLE prompt format
- Temperature 0, max 8192 tokens
- **Measures:** Raw LLM capability

### P2: Opus 4.6 with Tools (Ablation Control) — NEW
- Full tool access: code execution, web search, file I/O, calculators
- Free-form reasoning, NO D1-D6 domain structure
- Single Claude Code session, no subagents
- See `P2_TOOLS_INSTRUCTIONS.md` for details
- Output: `.judge_only/p2_opus_tools_batch_XXX.json` (participant: `p2_opus_tools`)
- **Measures:** Effect of tools alone (ablation — isolates tools vs structure)

### P3: Opus 4.6 Team + D1-D6 Agents (Full Pipeline)
- Team Lead orchestrates 5 domain subagents (D1-D5) + performs D6
- Full Theory of Systems pipeline per question
- See `RUN_INSTRUCTIONS.md` § P3 for strict protocol
- Output: `.judge_only/p3_batch_XXX.json` (participant: `p3_agent_d1d6`)
- **Measures:** Effect of tools + structured reasoning

### Comparison Matrix

| | P1 | P2 | P3 |
|---|---|---|---|
| Model | Opus 4.6 | Opus 4.6 | Opus 4.6 |
| Tools | No | Yes | Yes |
| D1-D6 Structure | No | No | Yes (agents) |
| Agents | No | No | Yes (5 domain + lead) |
| **Comparison** | baseline | P2 vs P1 = tools effect | P3 vs P2 = structure effect |

P2 serves as **ablation control** to isolate the structural vs tools effect:
- P2 - P1 = value added by tool access alone
- P3 - P2 = value added by D1-D6 domain decomposition on top of tools
- P3 - P1 = total value added by Regulus (tools + structure)

> **Note:** Old P2 (Regulus v2 prompt-based, no tools) is DEPRECATED and deleted.
> New P2 = "Opus 4.6 with tools, no D1-D6 structure."

---

## 3. JUDGE — o3-mini (official HLE protocol)

See judge.py for implementation.

---

## 4. FOLDER STRUCTURE

```
tests/HLE/
├── protocol.md                  <- This file
├── RUN_INSTRUCTIONS.md          <- Detailed run steps (P1, P2, P3)
├── P2_TOOLS_INSTRUCTIONS.md     <- P2 (tools ablation) specific instructions
├── questions/                   <- Questions ONLY (no answers)
├── .judge_only/                 <- RESTRICTED — results, verdicts, answers
│   ├── answers/                 <-   Ground truth (NEVER read by test agent)
│   ├── verdicts/                <-   Judge output (p1_*, p2_opus_tools_*, p3_*)
│   ├── p1_batch_*.json          <-   P1 raw Opus results
│   ├── p2_opus_tools_batch_*.json    <-   P2 Opus+tools results (NEW)
│   └── p3_batch_*.json          <-   P3 agent pipeline results
├── comparison/                  <- Cross-participant analysis
├── judge.py
├── prepare_questions.py
├── run_baseline.py              <- P1 runner
├── compare.py                   <- Flexible: --left p1 --right p3 etc.
├── pilot_10/                    <- Legacy pilot data
└── batch_20/                    <- Legacy batch data
```

**Naming convention:**
- `p1_*` = P1 (raw Opus, no tools)
- `p2_opus_tools_*` = P2 (Opus with tools, no D1-D6)
- `p3_*` = P3 (Opus with tools + D1-D6 agents)
