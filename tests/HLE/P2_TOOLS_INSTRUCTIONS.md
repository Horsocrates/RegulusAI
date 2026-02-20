# P2 Instructions: Opus 4.6 with Tools (No D1-D6 Structure)

## Purpose

This is the ABLATION CONTROL. We need to separate two effects:
- Effect of TOOLS (code execution, extended thinking, multiple attempts)
- Effect of STRUCTURE (D1-D6 domain decomposition, verification gates)

P2 gets the same tools as P3 (code execution, file I/O, extended thinking)
but NO domain decomposition, NO sub-agents, NO Theory of Systems framework.

## Comparison Design

```
P1: Raw Opus API call, no tools, single response       -> baseline
P2: Opus in Claude Code, tools available, free-form     -> tools effect
P3: Opus in Claude Code, tools + D1-D6 agent pipeline   -> tools + structure

If P3 >> P2 >> P1  -> structure adds value on top of tools
If P3 ~ P2 >> P1   -> tools are enough, structure is overhead
If P3 >> P2 ~ P1   -> tools alone don't help, structure is key
```

## P2 Protocol

For EACH question:
1. Read the question from tests/HLE/questions/
2. Think carefully about the problem
3. Use ANY tools you want: Python code, calculations, web concepts, etc.
4. Take your time — there is no rush
5. Write your final answer in EXACT_ANSWER: {value} format

## What P2 CAN do:
- Write and execute Python code to verify calculations
- Use multiple attempts / approaches to solve a problem
- Think step by step in natural language
- Use any libraries (sympy, numpy, scipy, etc.)
- Spend as much time as needed per question

## What P2 CANNOT do:
- Use D1-D6 domain decomposition
- Create sub-agents
- Follow Theory of Systems framework
- Read .claude/commands/ files
- Read any answer files or verdict files

## Answer Format

For each question, output:
```json
{
  "question_id": "...",
  "participant": "p2_opus_tools",
  "answer": "...",
  "explanation": "Brief reasoning (2-3 sentences)",
  "confidence": 0-100,
  "tools_used": ["python", "sympy", ...],
  "time_seconds": ...,
  "timestamp": "..."
}
```

Final answer line must be: EXACT_ANSWER: {value}

## Contamination Rules (same as all participants)
- Read ONLY from tests/HLE/questions/
- NEVER read tests/HLE/answers/, tests/HLE/verdicts/, tests/HLE/.judge_only/
- NEVER read P1 or P3 results
