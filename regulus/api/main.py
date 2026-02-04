"""
Regulus AI API — FastAPI backend for LLM reasoning verification.

Endpoints:
    POST /api/verify  — Run verification on a query
    GET  /api/health  — Health check
"""

import os
import time
from dotenv import load_dotenv

load_dotenv()
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from regulus.orchestrator import Orchestrator
from regulus.core.types import Policy
from regulus.llm.claude import ClaudeClient
from regulus.llm.openai import OpenAIClient

# ============================================================================
# Pydantic Models
# ============================================================================

class VerifyRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    provider: str = Field(default="claude", pattern="^(claude|openai)$")

class StepModel(BaseModel):
    domain: str
    level: int
    content: str
    status: str
    weight: float
    gate: int
    is_primary: bool

class VerifyResponse(BaseModel):
    query: str
    valid: bool
    primary_max: StepModel | None
    corrections: int
    violations: list[str]
    steps: list[StepModel]
    time_seconds: float

class HealthResponse(BaseModel):
    status: str
    version: str

class BattleResponse(BaseModel):
    query: str
    raw_answer: str
    raw_time: float
    guarded_answer: str | None
    guarded_valid: bool
    guarded_corrections: int
    guarded_violations: list[str]
    guarded_time: float
    comparison: str  # "MATCH", "CORRECTED", "BLOCKED"

# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Regulus AI API",
    description="Structural Guardrail for LLM Reasoning Verification",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Endpoints
# ============================================================================

@app.get("/api/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(status="ok", version="1.0.0")

@app.get("/api/debug")
async def debug():
    import os
    key = os.environ.get("ANTHROPIC_API_KEY", "NOT_SET")
    return {
        "key_exists": key != "NOT_SET" and len(key) > 0,
        "key_length": len(key) if key != "NOT_SET" else 0,
        "key_prefix": key[:12] + "..." if len(key) > 12 else "TOO_SHORT"
    }

@app.post("/api/verify", response_model=VerifyResponse)
async def verify(request: VerifyRequest):
    """Run verification on a query."""
    start_time = time.time()

    try:
        if request.provider == "claude":
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            client = ClaudeClient(api_key=api_key)
        else:
            api_key = os.environ.get("OPENAI_API_KEY", "")
            client = OpenAIClient(api_key=api_key)

        orch = Orchestrator(llm_client=client, policy=Policy.LEGACY_PRIORITY)
        result = await orch.process_query(request.query)

        # Convert nodes to response format
        nodes = result.result.nodes
        pm = result.result.primary_max

        steps = []
        for node in nodes:
            gate_val = 1 if (node.gate and node.gate.is_valid) else 0
            steps.append(StepModel(
                domain=node.entity_id,
                level=node.legacy_idx,
                content=node.content[:2000],
                status=node.status.name,
                weight=float(node.final_weight),
                gate=gate_val,
                is_primary=(pm is not None and node.node_id == pm.node_id)
            ))

        # Build primary_max
        primary = None
        if pm:
            primary = StepModel(
                domain=pm.entity_id,
                level=pm.legacy_idx,
                content=pm.content[:2000],
                status=pm.status.name,
                weight=float(pm.final_weight),
                gate=1 if (pm.gate and pm.gate.is_valid) else 0,
                is_primary=True
            )

        # Violations from diagnostics
        violations = [
            d.diagnostic_code or d.status.name
            for d in result.result.diagnostics
            if d.status.name == "INVALID"
        ]

        return VerifyResponse(
            query=request.query,
            valid=result.is_valid,
            primary_max=primary,
            corrections=result.total_corrections,
            violations=violations,
            steps=steps,
            time_seconds=time.time() - start_time
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/battle", response_model=BattleResponse)
async def battle(request: VerifyRequest):
    """Battle mode: compare raw LLM vs Regulus-guarded response."""

    try:
        # Create LLM client
        if request.provider == "claude":
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            client = ClaudeClient(api_key=api_key)
        else:
            api_key = os.environ.get("OPENAI_API_KEY", "")
            client = OpenAIClient(api_key=api_key)

        # 1. Raw LLM response
        raw_start = time.time()
        raw_response = await client.generate(request.query)
        raw_time = time.time() - raw_start

        # 2. Guarded response via Orchestrator
        guarded_start = time.time()
        orch = Orchestrator(llm_client=client, policy=Policy.LEGACY_PRIORITY)
        result = await orch.process_query(request.query)
        guarded_time = time.time() - guarded_start

        # 3. Determine comparison result
        pm = result.result.primary_max
        guarded_answer = pm.content[:2000] if pm else None

        if not pm:
            comparison = "BLOCKED"
        elif result.total_corrections > 0:
            comparison = "CORRECTED"
        else:
            comparison = "MATCH"

        # Violations from diagnostics
        violations = [
            d.diagnostic_code or d.status.name
            for d in result.result.diagnostics
            if d.status.name == "INVALID"
        ]

        return BattleResponse(
            query=request.query,
            raw_answer=raw_response[:2000],
            raw_time=raw_time,
            guarded_answer=guarded_answer,
            guarded_valid=pm is not None,
            guarded_corrections=result.total_corrections,
            guarded_violations=violations,
            guarded_time=guarded_time,
            comparison=comparison,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
