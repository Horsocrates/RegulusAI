# HLE Evaluation — Run Instructions

## Directory Structure

```
tests/HLE/
  questions/           # SAFE — question files only, no answers
    batch_001.json
    batch_002.json
    batch_003.json
  .judge_only/         # RESTRICTED — contains answers, results, verdicts
    answers/           #   ground truth (NEVER read by test agent)
    verdicts/          #   o3-mini judge output
    p1_batch_*.json    #   P1 raw Opus results
    p2_opus_tools_batch_*.json  #  P2 Opus+tools results (NEW)
    p3_batch_*.json    #   P3 agent pipeline results
  comparison/          # comparison tables (no answers, safe to read)
  run_baseline.py      # P1 runner
  run_regulus.py       # OLD P2 runner (DEPRECATED — was Regulus v2 prompt-based)
  judge.py             # o3-mini judge (reads from .judge_only/)
  compare.py           # comparison generator (--left p1 --right p2_opus_tools)
  prepare_questions.py # HF dataset downloader
  P2_TOOLS_INSTRUCTIONS.md  # NEW P2 instructions
```

## Contamination Rules

1. **NEVER read** `.judge_only/` or any file inside it during P1/P2 runs
2. **NEVER read** answer files in any session that runs P1 or P2
3. Questions files (`questions/*.json`) are safe — no `answer` field
4. Results are written directly to `.judge_only/` by runners
5. Judge and compare scripts are the ONLY tools that read `.judge_only/`
6. Run judge/compare in a SEPARATE session or as standalone scripts

## Step 1: Prepare Questions (one-time)

Already done for seed=100. To prepare new batches:

```bash
cd C:\Users\aleks\Desktop\regulusai
.venv\Scripts\python.exe tests/HLE/prepare_questions.py --seed 200 --n-batches 3 --batch-size 10
```

## Step 2: Run P1 Baseline (raw Opus)

Can run all batches in parallel. Each batch is independent.

```bash
cd C:\Users\aleks\Desktop\regulusai

# All 3 batches in parallel:
.venv\Scripts\python.exe tests/HLE/run_baseline.py --batch batch_001 &
.venv\Scripts\python.exe tests/HLE/run_baseline.py --batch batch_002 &
.venv\Scripts\python.exe tests/HLE/run_baseline.py --batch batch_003 &
```

Output: `.judge_only/p1_batch_001.json` etc.
Time: ~5 min per batch (10 questions, ~20-40s each).

## Step 3: Run P2 — Opus 4.6 with Tools (Ablation Control)

P2 uses Claude Code with full tool access but NO D1-D6 structure.
See `P2_TOOLS_INSTRUCTIONS.md` for detailed instructions.

Run manually via Claude Code sessions (5-10 questions per session):

```bash
cd C:\Users\aleks\Desktop\regulusai

# For each question, start a Claude Code session:
claude --resume no -p "Read tests/HLE/P2_TOOLS_INSTRUCTIONS.md, then answer questions from tests/HLE/questions/batch_001.json (Q01-Q05). Save results to tests/HLE/.judge_only/p2_opus_tools_batch_001.json"
```

Output: `.judge_only/p2_opus_tools_batch_001.json` etc.
Participant ID: `p2_opus_tools`

> **Note:** Old P2 (`run_regulus.py`, Regulus v2 prompt-based) is DEPRECATED.
> Old `p2_batch_*.json` files have been deleted.

## Step 4: Judge with o3-mini

Run AFTER participants are done. This is the ONLY step that reads answers.

```bash
cd C:\Users\aleks\Desktop\regulusai

# Judge P1:
.venv\Scripts\python.exe tests/HLE/judge.py --batch batch_001 --participant p1

# Judge P2 (new: Opus + tools):
.venv\Scripts\python.exe tests/HLE/judge.py --batch batch_001 --participant p2_opus_tools

# Judge P3 (agents):
.venv\Scripts\python.exe tests/HLE/judge.py --batch batch_001 --participant p3
```

Output: `.judge_only/verdicts/{participant}_{batch}_verdict.json`

## Step 5: Compare

```bash
cd C:\Users\aleks\Desktop\regulusai

# P1 vs P2 (tools effect):
.venv\Scripts\python.exe tests/HLE/compare.py --all --left p1 --right p2_opus_tools

# P2 vs P3 (structure effect):
.venv\Scripts\python.exe tests/HLE/compare.py --all --left p2_opus_tools --right p3

# P1 vs P3 (total effect):
.venv\Scripts\python.exe tests/HLE/compare.py --all --left p1 --right p3
```

Output: `comparison/` with LIFT/BOTH/HURT/NEITHER tables for each pair.

## P3: Agent-Based Pipeline (Sub-Agent / Slash Commands)

P3 uses the Theory of Systems D1-D6 pipeline per question. One **Team Lead** orchestrates **5 separate domain worker subagents** (D1-D5), then performs D6 itself.

### STRICT PROTOCOL RULES

> **These rules are mandatory. Violating them invalidates the batch.**

#### Rule 1: ONE question per pipeline run
- NEVER bundle multiple questions into one subagent prompt.
- Each question gets its own complete D1→D2→D3→D4→D5→D6 pipeline.
- Multiple questions can run in parallel, but each must be a separate pipeline.

#### Rule 2: ONE domain per subagent call (SEQUENTIAL)
- D1 = separate subagent call
- D2 = separate subagent call (receives D1 output)
- D3 = separate subagent call (receives D1+D2 output)
- D4 = separate subagent call (receives D1+D2+D3 output)
- D5 = separate subagent call (receives D1+D2+D3+D4 output)
- D6 = Team Lead performs directly (receives all D1-D5 output)
- **NEVER combine domains** (e.g. "D3-D5 in one call" is FORBIDDEN).
- **NEVER send all D1-D5 to one subagent** — this defeats the pipeline.

#### Rule 3: Team Lead does NOT pre-solve
- The Team Lead reads the question and creates a plan, but **MUST NOT reason toward an answer** before delegating to domain workers.
- The subagent prompt must contain ONLY: the domain instructions, the question text, and the output from prior domains.
- **NEVER embed your own reasoning, analysis, or candidate answers** in the subagent prompt. The subagent must think independently.
- If the Team Lead has opinions, they go into D6 Reflection only.

#### Rule 4: Sequential dependency — wait for output
- D2 subagent MUST receive D1's actual output before starting.
- D3 MUST receive D1+D2 output. D4 MUST receive D1+D2+D3 output. Etc.
- **NEVER launch D2 before D1 completes** — domains are causally dependent.
- Multiple QUESTIONS can run in parallel. Domains within one question CANNOT.

#### Rule 5: Gate verification between domains
- After each domain subagent returns, Team Lead MUST verify quality:
  - **PASS**: output meets domain criteria → proceed to next domain
  - **RETRY**: output is inadequate → re-run the same domain with feedback
  - **FAIL**: domain cannot be completed → mark LOW_CONFIDENCE, proceed
- Gate verification is a 2-sentence assessment, not a full re-analysis.

#### Rule 6: Contamination — absolute prohibition
- **NEVER read** `.judge_only/` or any file inside it.
- **NEVER read** answer files in any session that runs P3.
- Subagent prompts must include explicit instruction: "Do NOT read any files in .judge_only/ or answers/"
- If a subagent returns content that appears to come from an answer file, discard the result and re-run.

### How It Works

```
Question → Team Lead
              │
              ├─ [Subagent 1] D1 Recognition  → d1_output
              │       ↓ (Team Lead verifies gate)
              ├─ [Subagent 2] D2 Clarification → d2_output  (receives d1_output)
              │       ↓ (Team Lead verifies gate)
              ├─ [Subagent 3] D3 Framework     → d3_output  (receives d1+d2)
              │       ↓ (Team Lead verifies gate)
              ├─ [Subagent 4] D4 Comparison    → d4_output  (receives d1+d2+d3)
              │       ↓ (Team Lead verifies gate)
              ├─ [Subagent 5] D5 Inference     → d5_output  (receives d1+d2+d3+d4)
              │       ↓ (Team Lead verifies gate)
              └─ [Team Lead]  D6 Reflection    → d6_output  (receives all)
           → final answer + confidence
```

**Key**: arrows are SEQUENTIAL. Each subagent waits for the previous one to finish.

### Anti-Patterns (FORBIDDEN)

These patterns were observed in failed runs and MUST NOT be repeated:

```
BAD: "You are a D1-D6 domain worker. Answer each question..."
     → Combines all domains into one call. FORBIDDEN by Rule 2.

BAD: "Q01: ...\n Q02: ...\n Q03: ..."
     → Bundles multiple questions. FORBIDDEN by Rule 1.

BAD: prompt contains "ANSWER: X\nCONFIDENCE: 30"
     → Team Lead pre-solved the question. FORBIDDEN by Rule 3.

BAD: "You are performing the full Regulus D1-D5 pipeline..."
     → All domains in one subagent. FORBIDDEN by Rule 2.

BAD: Launching D1, D2, D3 for same question in parallel
     → Domains are sequential. FORBIDDEN by Rule 4.
```

### Correct Subagent Prompt Templates

**D1 subagent prompt:**
```
You are Domain 1 (Recognition) in the Theory of Systems pipeline.

YOUR FUNCTION: Identify what is PRESENT in the query. Decompose into typed
components (entity, relation, constraint, assumption). Identify the KEY
CHALLENGE. Do NOT define, evaluate, or answer.

CONTAMINATION RULE: Do NOT read any files in .judge_only/ or answers/.

QUESTION:
{question_text}

Return your D1 analysis as structured output.
```

**D2 subagent prompt:**
```
You are Domain 2 (Clarification) in the Theory of Systems pipeline.

YOUR FUNCTION: Define every D1 component precisely. Resolve ambiguities.
Identify hidden assumptions and domain conventions.

CONTAMINATION RULE: Do NOT read any files in .judge_only/ or answers/.

QUESTION:
{question_text}

D1 OUTPUT (from previous domain worker):
{d1_output}

Return your D2 analysis.
```

**D3-D5 follow the same pattern**: question + all prior domain outputs.

### Slash Commands

Source files live in `.claude/commands/` relative to project root (`C:\Users\aleks\Desktop\regulusai\.claude\commands\`):

| Command | File | Role | Input | Output |
|---------|------|------|-------|--------|
| `/analyze` | `analyze.md` | Team Lead (L3 meta-operator) | question text | state.json, result.json |
| `/d1-recognize` | `d1-recognize.md` | Identify what's PRESENT | state.json | d1_output.json |
| `/d2-clarify` | `d2-clarify.md` | Define every D1 component | d1_output.json | d2_output.json |
| `/d3-framework` | `d3-framework.md` | Choose evaluation framework BEFORE evaluating | d2_output.json | d3_output.json |
| `/d4-compare` | `d4-compare.md` | Apply D3 criteria to D1/D2 components | d2+d3_output.json | d4_output.json |
| `/d5-infer` | `d5-infer.md` | Draw conclusions earned by D4 evidence | d4_output.json | d5_output.json |
| `/d6-reflect` | `d6-reflect.md` | Analyze limits, return assessment for D1-D5 | d1-d5_output.json | d6_output.json |

**To read a command's full prompt**: `cat .claude/commands/{file}` (e.g. `cat .claude/commands/analyze.md`)

### Domain Summaries

**D1 Recognition** — Decomposes question into typed components (entity, relation, constraint, assumption) at depth levels 1-5. Identifies the KEY CHALLENGE. Does NOT define or evaluate.

**D2 Clarification** — Defines every D1 component precisely. Resolves ambiguities, identifies hidden assumptions and domain conventions. Critical for HLE where terms have multiple technical meanings.

**D3 Framework Selection** — Chooses evaluation criteria BEFORE evaluating (P2 Criterion Precedence). Must consider at least one alternative and explain rejection. Framework must PERMIT all possible answers (objectivity).

**D4 Comparison** — Applies EVERY D3 criterion to EVERY relevant component. Collects evidence for AND against. Enforces Aristotle's rules (same relation, same criterion, same state). This is where actual analytical work happens.

**D5 Inference** — Draws conclusions that follow from D4 evidence only. Classifies certainty (necessary/probabilistic/evaluative). Checks for overreach and avoidance.

**D6 Reflection** — Analyzes the reasoning process itself. Must ADD something specific, not restate D5. Return assessment checks D1-D5 for errors. Generic disclaimers don't count.

### Team Lead Role

The Team Lead:
1. Reads the question, creates a plan (goal, complexity, task_type). **Does NOT attempt to answer.**
2. Launches D1 subagent with question text only. Waits for result. Verifies gate.
3. Launches D2 subagent with question + D1 output. Waits. Verifies gate.
4. Launches D3 subagent with question + D1 + D2 output. Waits. Verifies gate.
5. Launches D4 subagent with question + D1 + D2 + D3 output. Waits. Verifies gate.
6. Launches D5 subagent with question + D1-D4 output. Waits. Verifies gate.
7. Performs D6 Reflection itself (receives all D1-D5 output).
8. Assembles final answer with confidence score.

**The Team Lead is an ORCHESTRATOR, not a solver.** Its job is to delegate, verify gates, and reflect. The analytical work happens in domain subagents.

### Parallelism Rules

```
ALLOWED: Run Q01 pipeline and Q02 pipeline in parallel
         (different questions, independent pipelines)

           Q01: D1 → D2 → D3 → D4 → D5 → D6
           Q02: D1 → D2 → D3 → D4 → D5 → D6
           (both running simultaneously, each internally sequential)

FORBIDDEN: Run D1 and D2 for same question in parallel
           (D2 needs D1 output)

FORBIDDEN: Run D1 for Q01 and Q02 in same subagent call
           (one question per subagent)
```

When running a batch of 10 questions, the Team Lead MAY run up to 3-5 question
pipelines concurrently. Each pipeline is internally sequential (D1→D2→D3→D4→D5→D6).
Team Lead manages multiple concurrent pipelines by tracking state for each question.

### Session Sizing

**MAX 3 questions per session.** This is a hard limit based on context analysis:

| Questions/session | Context usage | Risk | Verdict |
|-------------------|---------------|------|---------|
| 1 | ~25K / 200K | None | Too slow (10 sessions/batch) |
| **3** | **~75-90K / 200K** | **Low** | **Optimal (3-4 sessions/batch)** |
| 5 | ~125-150K / 200K | Medium — compaction starts | Only for simple questions |
| 10 | >200K | **High — protocol breaks** | FORBIDDEN |

Each question consumes ~20-30K tokens (5 subagent round-trips + gate checks + D6).
At 5+ questions, context compaction summarizes earlier messages and Team Lead
loses the protocol rules. This was observed in practice: batch 002/003 failed because
the session processed 10 questions and the Team Lead progressively cut corners.

The critical P3 rules are also in `CLAUDE.md` (always loaded in system prompt,
never compressed), providing a safety net even if `RUN_INSTRUCTIONS.md` gets compacted.

A 10-question batch requires 3-4 sessions:
- Session 1: Q01, Q02, Q03
- Session 2: Q04, Q05, Q06
- Session 3: Q07, Q08, Q09
- Session 4: Q10

### Running P3 on HLE

P3 is run manually via Claude Code chat sessions. For each session (max 3 questions):

1. Open a **fresh** Claude Code session in `C:\Users\aleks\Desktop\regulusai`
2. Read the questions file: `tests/HLE/questions/batch_XXX.json`
3. For each question (max 3), run the full D1→D2→D3→D4→D5→D6 pipeline:
   - Launch D1 subagent (question text only, no pre-analysis)
   - Wait for D1 → verify gate → launch D2 with D1 output
   - Wait for D2 → verify gate → launch D3 with D1+D2 output
   - Continue through D5
   - Team Lead performs D6
4. Assemble results into `.judge_only/p3_batch_XXX.json`

**Contamination rules apply**: the agent session must NEVER read `.judge_only/` or any answer files. Include contamination warning in EVERY subagent prompt.

### Validation Checklist (post-run audit)

After completing a batch, verify:
- [ ] Each question had exactly 5 subagent calls (D1, D2, D3, D4, D5)
- [ ] Each subagent prompt contained only question + prior domain outputs (no pre-baked answers)
- [ ] Domains ran sequentially (D2 received D1 output, D3 received D1+D2, etc.)
- [ ] No subagent prompt contained multiple questions
- [ ] No subagent accessed `.judge_only/` or answer files
- [ ] Team Lead performed D6 (not delegated)
- [ ] Gate verification occurred between each domain

### P3 Runner Script (TODO)

A `run_p3_agent.py` script is needed to automate:
- Reading questions from `questions/{batch}.json`
- Spawning a Claude Code sub-process per question with `/analyze`
- Collecting `result.json` outputs
- Writing `.judge_only/p3_{batch}.json`

## Scaling to 100 Questions

```bash
# Prepare 10 batches of 10 questions each:
.venv\Scripts\python.exe tests/HLE/prepare_questions.py --seed 300 --n-batches 10 --batch-size 10

# Then run Steps 2-5 for batch_001 through batch_010
```

## Environment Requirements

- `.env` with ANTHROPIC_API_KEY and OPENAI_API_KEY
- Python venv at `.venv/` with: anthropic, openai, python-dotenv, datasets
- For DeepSeek: DEEPSEEK_API_KEY in .env

## Current Results (seed=100, 60 questions)

| Participant | Correct | Total | Accuracy | Status |
|-------------|---------|-------|----------|--------|
| P1 (raw Opus 4.6, no tools) | 6 | 30 | 20.0% | batch 001-003 done |
| P2 (Opus + tools, no D1-D6) | — | — | — | TODO — new definition |
| P3 (Opus + tools + D1-D6 agents) | — | 60 | — | batch 004-006 done, 002-003 re-running |

> **Note:** Old P2 (Regulus v2 prompt-based) results deleted. New P2 = Opus with tools, no structure.
> P1 vs old-P2 comparison (LIFT=4, BOTH=4, HURT=2, NEITHER=20) is no longer valid.
