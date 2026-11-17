from __future__ import annotations

import json
import logging
import time
from collections import defaultdict, deque
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .auth import Actor, AuthService
from .config import Settings


logger = logging.getLogger("flowboard.api")


class ApiMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, auth: AuthService, settings: Settings) -> None:
        super().__init__(app)
        self.auth = auth
        self.settings = settings
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        request_id = request.headers.get("x-request-id") or str(uuid4())
        bearer = request.headers.get("authorization", "")
        token = bearer[7:] if bearer.lower().startswith("bearer ") else None
        actor = self.auth.authenticate(token) or Actor.guest()
        request.state.actor = actor
        path = request.url.path
        public = path.endswith("/health") or "/auth/" in path or not path.startswith("/api/")
        if self.settings.auth_required and not public and not actor.authenticated:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        if request.method not in {"GET", "HEAD", "OPTIONS"} and actor.role == "viewer":
            return JSONResponse({"detail": "Viewer role is read-only"}, status_code=403)
        key = actor.id if actor.authenticated else (request.client.host if request.client else "unknown")
        now = time.monotonic()
        bucket = self.hits[key]
        while bucket and bucket[0] < now - 60:
            bucket.popleft()
        if len(bucket) >= self.settings.rate_limit_per_minute:
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        bucket.append(now)
        response = await call_next(request)
        duration = time.perf_counter() - started
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        metrics = request.app.state.metrics
        metrics["requests"] += 1
        metrics["duration"] += duration
        metrics["statuses"][str(response.status_code)] += 1
        logger.info(json.dumps({
            "requestId": request_id, "method": request.method, "path": path,
            "status": response.status_code, "actor": actor.id,
            "durationMs": round(duration * 1000, 2),
        }))
        return response
