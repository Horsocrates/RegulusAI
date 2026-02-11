"""Simple in-memory rate limiter for Lab API endpoints.

Uses a sliding window counter per IP. Configurable via environment:
    LAB_RATE_LIMIT_RPM=60       (requests per minute, default 60)
    LAB_RATE_LIMIT_BURST=10     (burst allowance, default 10)
"""

from __future__ import annotations

import os
import time
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP rate limiter using sliding window counters.

    Only applies to /api/lab/ endpoints. Health checks and non-lab
    endpoints are always allowed through.
    """

    def __init__(self, app, rpm: int | None = None, burst: int | None = None):
        super().__init__(app)
        self.rpm = rpm if rpm is not None else int(os.environ.get("LAB_RATE_LIMIT_RPM", "60"))
        self.burst = burst if burst is not None else int(os.environ.get("LAB_RATE_LIMIT_BURST", "10"))
        self.enabled = self.rpm > 0
        self.window = 60.0  # 1 minute
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next) -> Response:
        # Disabled if rpm=0 or env var set to 0 (check at request time for testing)
        if not self.enabled or os.environ.get("LAB_RATE_LIMIT_RPM") == "0":
            return await call_next(request)

        path = request.url.path

        # Only rate-limit lab API endpoints
        if not path.startswith("/api/lab/"):
            return await call_next(request)

        # Skip SSE streams (long-lived connections)
        if path.endswith("/stream"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()

        # Clean old entries outside window
        hits = self._hits[client_ip]
        cutoff = now - self.window
        self._hits[client_ip] = hits = [t for t in hits if t > cutoff]

        if len(hits) >= self.rpm + self.burst:
            retry_after = int(self.window - (now - hits[0])) + 1
            return JSONResponse(
                status_code=429,
                content={
                    "detail": {
                        "code": "LAB_009",
                        "message": f"Rate limit exceeded ({self.rpm}/min). Retry after {retry_after}s.",
                    }
                },
                headers={"Retry-After": str(retry_after)},
            )

        hits.append(now)
        return await call_next(request)
