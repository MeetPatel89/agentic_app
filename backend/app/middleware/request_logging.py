from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("llm_router")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        start = time.perf_counter()
        logger.info("[%s] %s %s", request_id, request.method, request.url.path)
        try:
            response = await call_next(request)
            elapsed = (time.perf_counter() - start) * 1000
            logger.info("[%s] %s %dms", request_id, response.status_code, elapsed)
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            logger.exception("[%s] Unhandled exception", request_id)
            raise
