"""
Regulus AI - Source Verifier
==============================

Retrieves and verifies factual information from external sources.

Workflow:
1. D1 detects [FACTUAL DATA REQUIRED] tag
2. D2 triggers SourceVerifier to find and verify facts
3. SourceVerifier searches web, retrieves authoritative sources
4. Facts are verified or marked as uncertain

Supported sources:
- Brave Search API (primary - best quality, free tier available)
- Google Custom Search API (if configured)
- Wikipedia API (direct lookup for known topics)
- DuckDuckGo Instant Answer (fallback)

To enable Brave Search, set BRAVE_API_KEY in .env
To enable Google Search, set GOOGLE_API_KEY and GOOGLE_CSE_ID in .env
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional
from urllib.parse import quote_plus


# ============================================================
# Persistent File Cache
# ============================================================

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "source_cache"
CACHE_TTL = 7 * 24 * 60 * 60  # 7 days in seconds


def _get_cache_path(query: str) -> Path:
    """Get cache file path for a query."""
    query_hash = hashlib.md5(query.lower().strip().encode()).hexdigest()
    return CACHE_DIR / f"{query_hash}.json"


def _load_from_cache(query: str) -> Optional[dict]:
    """Load cached result if exists and not expired."""
    cache_path = _get_cache_path(query)
    if not cache_path.exists():
        return None

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Check TTL
        cached_time = data.get("_cached_at", 0)
        if time.time() - cached_time > CACHE_TTL:
            cache_path.unlink()  # Delete expired
            return None

        return data
    except Exception:
        return None


def _save_to_cache(query: str, data: dict):
    """Save result to cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _get_cache_path(query)

    data["_cached_at"] = time.time()
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # Cache write failures are not critical

# Load .env before reading API keys
from dotenv import load_dotenv
load_dotenv()

if TYPE_CHECKING:
    from .client import LLMClient


# API Keys from environment (loaded after dotenv)
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")
SERP_API_KEY = os.getenv("SERP_API_KEY", "")


@dataclass
class SourceResult:
    """Result from a single source lookup."""
    source_name: str
    source_url: str
    content: str
    relevance_score: float = 0.0
    is_authoritative: bool = False


@dataclass
class VerificationResult:
    """Result of verifying a factual claim."""
    claim: str
    verified: bool
    confidence: float  # 0.0 - 1.0
    sources: List[SourceResult] = field(default_factory=list)
    corrected_claim: Optional[str] = None
    reasoning: str = ""


# ============================================================
# Web Search via DuckDuckGo Instant Answer API
# ============================================================

async def search_web(query: str, num_results: int = 5) -> List[SourceResult]:
    """
    Search the web for information using DuckDuckGo.

    Args:
        query: Search query
        num_results: Maximum number of results to return

    Returns:
        List of SourceResult objects
    """
    import httpx

    results: List[SourceResult] = []
    headers = {
        "User-Agent": "RegulusAI/1.0 (https://github.com/regulus-ai) httpx/0.27"
    }

    # DuckDuckGo Instant Answer API
    ddg_url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1"

    try:
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            response = await client.get(ddg_url)
            if response.status_code == 200:
                data = response.json()

                # Abstract (main answer)
                if data.get("Abstract"):
                    results.append(SourceResult(
                        source_name=data.get("AbstractSource", "Wikipedia"),
                        source_url=data.get("AbstractURL", ""),
                        content=data.get("Abstract", ""),
                        relevance_score=0.9,
                        is_authoritative=True,
                    ))

                # Related topics
                for topic in data.get("RelatedTopics", [])[:num_results-1]:
                    if isinstance(topic, dict) and "Text" in topic:
                        results.append(SourceResult(
                            source_name="DuckDuckGo",
                            source_url=topic.get("FirstURL", ""),
                            content=topic.get("Text", ""),
                            relevance_score=0.6,
                            is_authoritative=False,
                        ))
    except Exception as e:
        # Log error but continue - we'll try other sources
        pass

    return results


# ============================================================
# SerpAPI (Easiest Setup - 100 free searches/month)
# ============================================================

async def search_serpapi(query: str, num_results: int = 5) -> List[SourceResult]:
    """
    Search using SerpAPI (Google Search Results).

    Get API key at: https://serpapi.com/ (100 free searches/month)

    Args:
        query: Search query
        num_results: Maximum number of results

    Returns:
        List of SourceResult objects
    """
    if not SERP_API_KEY:
        return []

    import httpx

    results: List[SourceResult] = []
    url = (
        f"https://serpapi.com/search.json"
        f"?q={quote_plus(query)}&api_key={SERP_API_KEY}"
        f"&num={num_results}&engine=google"
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                for item in data.get("organic_results", [])[:num_results]:
                    results.append(SourceResult(
                        source_name=item.get("title", "SerpAPI Result"),
                        source_url=item.get("link", ""),
                        content=item.get("snippet", ""),
                        relevance_score=0.9,
                        is_authoritative=".gov" in item.get("link", "") or ".edu" in item.get("link", ""),
                    ))
    except Exception:
        pass

    return results


# ============================================================
# Brave Search API (Primary - Best Quality)
# ============================================================

async def search_brave(query: str, num_results: int = 5) -> List[SourceResult]:
    """
    Search using Brave Search API.

    Brave Search provides high-quality results with a free tier (2000/month).
    Get API key at: https://brave.com/search/api/

    Args:
        query: Search query
        num_results: Maximum number of results

    Returns:
        List of SourceResult objects
    """
    if not BRAVE_API_KEY:
        return []

    import httpx

    results: List[SourceResult] = []
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": BRAVE_API_KEY,
    }

    url = f"https://api.search.brave.com/res/v1/web/search?q={quote_plus(query)}&count={num_results}"

    try:
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                for item in data.get("web", {}).get("results", [])[:num_results]:
                    results.append(SourceResult(
                        source_name=item.get("title", "Brave Search"),
                        source_url=item.get("url", ""),
                        content=item.get("description", ""),
                        relevance_score=0.85,
                        is_authoritative=".gov" in item.get("url", "") or ".edu" in item.get("url", ""),
                    ))
    except Exception as e:
        pass

    return results


# ============================================================
# Google Custom Search API
# ============================================================

async def search_google(query: str, num_results: int = 5) -> List[SourceResult]:
    """
    Search using Google Custom Search API.

    Requires GOOGLE_API_KEY and GOOGLE_CSE_ID environment variables.
    Get credentials at: https://developers.google.com/custom-search/v1/introduction

    Args:
        query: Search query
        num_results: Maximum number of results

    Returns:
        List of SourceResult objects
    """
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return []

    import httpx

    results: List[SourceResult] = []
    url = (
        f"https://www.googleapis.com/customsearch/v1"
        f"?key={GOOGLE_API_KEY}&cx={GOOGLE_CSE_ID}"
        f"&q={quote_plus(query)}&num={min(num_results, 10)}"
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                for item in data.get("items", [])[:num_results]:
                    results.append(SourceResult(
                        source_name=item.get("title", "Google Search"),
                        source_url=item.get("link", ""),
                        content=item.get("snippet", ""),
                        relevance_score=0.9,
                        is_authoritative=".gov" in item.get("link", "") or ".edu" in item.get("link", ""),
                    ))
    except Exception:
        pass

    return results


# ============================================================
# Wikipedia API (for known topics)
# ============================================================

async def search_wikipedia(query: str) -> Optional[SourceResult]:
    """
    Direct Wikipedia API lookup for factual information.
    Uses persistent file cache.

    Args:
        query: Topic to search

    Returns:
        SourceResult if found, None otherwise
    """
    # Check cache first
    cached = _load_from_cache(f"wiki:{query}")
    if cached and "result" in cached:
        r = cached["result"]
        if r:
            print(f"[SourceVerifier] Wiki cache hit for: {query[:50]}...")
            return SourceResult(
                source_name=r["source_name"],
                source_url=r["source_url"],
                content=r["content"],
                relevance_score=r.get("relevance_score", 0.95),
                is_authoritative=r.get("is_authoritative", True),
            )
        return None

    import httpx

    wiki_api = "https://en.wikipedia.org/api/rest_v1/page/summary/"
    headers = {
        "User-Agent": "RegulusAI/1.0 (https://github.com/regulus-ai; contact@regulus.ai) httpx/0.27"
    }

    result = None
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            # Try direct title match
            url = wiki_api + quote_plus(query.replace(" ", "_"))
            response = await client.get(url)

            if response.status_code == 200:
                data = response.json()
                result = SourceResult(
                    source_name="Wikipedia",
                    source_url=data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                    content=data.get("extract", ""),
                    relevance_score=0.95,
                    is_authoritative=True,
                )
    except Exception:
        pass

    # Cache the result (even if None, to avoid repeated failed lookups)
    _save_to_cache(f"wiki:{query}", {
        "result": {
            "source_name": result.source_name,
            "source_url": result.source_url,
            "content": result.content,
            "relevance_score": result.relevance_score,
            "is_authoritative": result.is_authoritative,
        } if result else None
    })

    return result


# ============================================================
# Unified Search (tries best sources first)
# ============================================================

async def search_all_sources(query: str, num_results: int = 5) -> List[SourceResult]:
    """
    Search all available sources, prioritizing by quality.
    Uses persistent file cache to avoid repeated API calls.

    Priority order:
    1. SerpAPI (easiest setup, if API key set)
    2. Brave Search (best quality, if API key set)
    3. Google Custom Search (if configured)
    4. Wikipedia (for known topics)
    5. DuckDuckGo (fallback)

    Args:
        query: Search query
        num_results: Maximum results per source

    Returns:
        Combined list of SourceResult objects, deduplicated
    """
    # Check persistent cache first
    cached = _load_from_cache(f"search:{query}")
    if cached and "results" in cached:
        print(f"[SourceVerifier] Cache hit for: {query[:50]}...")
        return [
            SourceResult(
                source_name=r["source_name"],
                source_url=r["source_url"],
                content=r["content"],
                relevance_score=r.get("relevance_score", 0.5),
                is_authoritative=r.get("is_authoritative", False),
            )
            for r in cached["results"]
        ]

    all_results: List[SourceResult] = []
    seen_urls: set = set()

    # 1. Try SerpAPI first (easiest to set up)
    if SERP_API_KEY:
        serp_results = await search_serpapi(query, num_results)
        for r in serp_results:
            if r.source_url not in seen_urls:
                all_results.append(r)
                seen_urls.add(r.source_url)

    # 2. Try Brave Search (best quality)
    if BRAVE_API_KEY and len(all_results) < num_results:
        brave_results = await search_brave(query, num_results - len(all_results))
        for r in brave_results:
            if r.source_url not in seen_urls:
                all_results.append(r)
                seen_urls.add(r.source_url)

    # 3. Try Google if configured and need more results
    if GOOGLE_API_KEY and GOOGLE_CSE_ID and len(all_results) < num_results:
        google_results = await search_google(query, num_results - len(all_results))
        for r in google_results:
            if r.source_url not in seen_urls:
                all_results.append(r)
                seen_urls.add(r.source_url)

    # 3. Try Wikipedia for the topic
    wiki_result = await search_wikipedia(query)
    if wiki_result and wiki_result.source_url not in seen_urls:
        all_results.append(wiki_result)
        seen_urls.add(wiki_result.source_url)

    # 4. Fallback to DuckDuckGo if still no results
    if len(all_results) < 2:
        ddg_results = await search_web(query, num_results)
        for r in ddg_results:
            if r.source_url and r.source_url not in seen_urls:
                all_results.append(r)
                seen_urls.add(r.source_url)

    final_results = all_results[:num_results]

    # Save to persistent cache
    if final_results:
        _save_to_cache(f"search:{query}", {
            "results": [
                {
                    "source_name": r.source_name,
                    "source_url": r.source_url,
                    "content": r.content,
                    "relevance_score": r.relevance_score,
                    "is_authoritative": r.is_authoritative,
                }
                for r in final_results
            ]
        })
        print(f"[SourceVerifier] Cached {len(final_results)} results for: {query[:50]}...")

    return final_results


def format_source_citation(result: SourceResult) -> str:
    """
    Format a source result as a citation.

    Returns format: "According to [Source Name](URL), ..."
    """
    if result.source_url:
        return f"According to [{result.source_name}]({result.source_url})"
    return f"According to {result.source_name}"


def format_answer_with_sources(
    answer: str,
    sources: List[SourceResult],
    verified_claims: List[str] = None,
) -> str:
    """
    Format an answer with proper source citations.

    Args:
        answer: The answer text
        sources: List of sources used
        verified_claims: Specific claims that were verified

    Returns:
        Answer formatted with "According to [source]..." citations
    """
    if not sources:
        return answer + "\n\n[UNCERTAIN] No sources found for verification."

    # Build source citation section
    citations = []
    for i, source in enumerate(sources[:3], 1):
        if source.source_url:
            citations.append(f"{i}. [{source.source_name}]({source.source_url})")
        else:
            citations.append(f"{i}. {source.source_name}")

    source_section = "\n\n**Sources:**\n" + "\n".join(citations)

    return answer + source_section


# ============================================================
# Claim Extraction
# ============================================================

CLAIM_EXTRACTION_PROMPT = """\
Extract specific factual claims from this text that need verification.

TEXT:
{text}

For each factual claim (numbers, statistics, rankings, dates, specific facts), extract:
1. The exact claim
2. What type of fact it is (statistic, ranking, date, name, location, etc.)
3. What source would be authoritative for this claim

Respond with JSON:
{{
    "claims": [
        {{
            "claim": "exact factual claim",
            "fact_type": "statistic|ranking|date|name|location|other",
            "authority": "type of source that would be authoritative (e.g., USDA, Census, Wikipedia)"
        }}
    ]
}}

If no factual claims need verification, return: {{"claims": []}}"""


async def extract_claims(llm: "LLMClient", text: str) -> List[dict]:
    """
    Extract factual claims that need verification from text.

    Args:
        llm: LLM client for extraction
        text: Text to analyze

    Returns:
        List of claim dictionaries
    """
    prompt = CLAIM_EXTRACTION_PROMPT.format(text=text)

    try:
        response = await llm.generate(prompt)

        # Parse JSON
        text_clean = response.strip()
        if text_clean.startswith("```"):
            lines = text_clean.split("\n")
            text_clean = "\n".join(lines[1:-1])

        data = json.loads(text_clean)
        return data.get("claims", [])
    except Exception:
        return []


# ============================================================
# Source Verifier Class
# ============================================================

VERIFICATION_PROMPT = """\
You are a fact-checker. Compare the CLAIM against the SOURCE INFORMATION.

CLAIM: {claim}

SOURCE INFORMATION:
{source_info}

Determine:
1. Is the claim VERIFIED, REFUTED, or UNCERTAIN based on this source?
2. If refuted, what is the correct information?
3. Confidence level (0.0 - 1.0)

Respond with JSON only:
{{
    "status": "verified|refuted|uncertain",
    "confidence": 0.0-1.0,
    "corrected_claim": "correct information if refuted, null otherwise",
    "reasoning": "brief explanation"
}}"""


class SourceVerifier:
    """
    Verifies factual claims using external sources.

    Workflow:
    1. Extract factual claims from domain output
    2. Search web/Wikipedia for authoritative sources
    3. Compare claims against found sources
    4. Return verification results with sources
    """

    def __init__(self, llm_client: "LLMClient") -> None:
        self.llm = llm_client
        self._cache: dict = {}  # Simple cache for repeated queries

    async def verify_claim(
        self,
        claim: str,
        search_query: Optional[str] = None,
    ) -> VerificationResult:
        """
        Verify a single factual claim.

        Args:
            claim: The factual claim to verify
            search_query: Optional custom search query (defaults to claim)

        Returns:
            VerificationResult with sources and verification status
        """
        query = search_query or claim

        # Check cache
        cache_key = query.lower().strip()
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Gather sources
        sources: List[SourceResult] = []

        # Try Wikipedia first (most authoritative for general facts)
        wiki_result = await search_wikipedia(query)
        if wiki_result:
            sources.append(wiki_result)

        # Web search for additional sources
        web_results = await search_web(query)
        sources.extend(web_results)

        if not sources:
            # No sources found
            result = VerificationResult(
                claim=claim,
                verified=False,
                confidence=0.0,
                sources=[],
                reasoning="No authoritative sources found for verification.",
            )
            self._cache[cache_key] = result
            return result

        # Combine source content
        source_info = "\n\n".join([
            f"[{s.source_name}] ({s.source_url})\n{s.content}"
            for s in sources[:3]  # Top 3 sources
        ])

        # Use LLM to compare claim against sources
        prompt = VERIFICATION_PROMPT.format(
            claim=claim,
            source_info=source_info,
        )

        try:
            response = await self.llm.generate(prompt)

            # Parse response
            text = response.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])

            data = json.loads(text)

            result = VerificationResult(
                claim=claim,
                verified=data.get("status") == "verified",
                confidence=float(data.get("confidence", 0.5)),
                sources=sources,
                corrected_claim=data.get("corrected_claim"),
                reasoning=data.get("reasoning", ""),
            )
        except Exception:
            # Fallback: uncertain
            result = VerificationResult(
                claim=claim,
                verified=False,
                confidence=0.3,
                sources=sources,
                reasoning="Verification parsing failed, marked as uncertain.",
            )

        self._cache[cache_key] = result
        return result

    async def verify_domain_output(
        self,
        domain_output: str,
        original_question: str,
    ) -> tuple[List[VerificationResult], str]:
        """
        Verify all factual claims in a domain output.

        Args:
            domain_output: The domain's text output
            original_question: The user's original question

        Returns:
            (verification_results, enhanced_output)
            - verification_results: List of VerificationResult for each claim
            - enhanced_output: Domain output with source annotations
        """
        # Extract claims
        claims = await extract_claims(self.llm, domain_output)

        if not claims:
            return [], domain_output

        # Verify each claim
        results: List[VerificationResult] = []
        annotations: List[str] = []

        for claim_data in claims:
            claim = claim_data.get("claim", "")
            if not claim:
                continue

            # Build search query with context
            authority = claim_data.get("authority", "")
            if authority:
                query = f"{claim} {authority}"
            else:
                query = claim

            result = await self.verify_claim(claim, query)
            results.append(result)

            # Create annotation
            if result.verified:
                status = "[VERIFIED]"
            elif result.corrected_claim:
                status = f"[CORRECTED: {result.corrected_claim}]"
            else:
                status = "[UNCERTAIN]"

            source_urls = ", ".join([s.source_url for s in result.sources[:2] if s.source_url])
            if source_urls:
                annotations.append(f"- {claim}: {status} (Sources: {source_urls})")
            else:
                annotations.append(f"- {claim}: {status}")

        # Enhance output with verification section
        if annotations:
            enhanced = domain_output + "\n\n[SOURCE VERIFICATION]\n" + "\n".join(annotations)
        else:
            enhanced = domain_output

        return results, enhanced

    def format_sources_for_probe(
        self,
        results: List[VerificationResult],
    ) -> str:
        """
        Format verification results for inclusion in probe answer.

        Args:
            results: List of VerificationResult objects

        Returns:
            Formatted string with sources and status
        """
        if not results:
            return "[UNCERTAIN] No external sources found for verification."

        lines = []
        for r in results:
            if r.verified:
                lines.append(f"[SOURCE] {r.claim}")
                for s in r.sources[:1]:
                    if s.source_url:
                        lines.append(f"  - Verified via: {s.source_name} ({s.source_url})")
            elif r.corrected_claim:
                lines.append(f"[CORRECTION] Original: {r.claim}")
                lines.append(f"  - Corrected to: {r.corrected_claim}")
                for s in r.sources[:1]:
                    if s.source_url:
                        lines.append(f"  - Source: {s.source_name} ({s.source_url})")
            else:
                lines.append(f"[UNCERTAIN] {r.claim}")
                lines.append(f"  - Could not verify from available sources")

        return "\n".join(lines)


# ============================================================
# Integration Helper
# ============================================================

async def verify_and_enhance(
    llm_client: "LLMClient",
    domain_output: str,
    original_question: str,
) -> tuple[str, List[VerificationResult]]:
    """
    Convenience function to verify and enhance domain output.

    This is called from the prober when source_grounded criterion fails.

    Args:
        llm_client: LLM client for generation
        domain_output: The domain output to verify
        original_question: User's original question

    Returns:
        (enhanced_output, verification_results)
    """
    verifier = SourceVerifier(llm_client)
    results, enhanced = await verifier.verify_domain_output(
        domain_output=domain_output,
        original_question=original_question,
    )
    return enhanced, results
