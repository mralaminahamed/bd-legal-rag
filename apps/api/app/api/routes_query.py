"""Public query and feedback endpoints (FR-DL-1..3, FR-FB-1..2).

Exposes POST /api/v1/query, POST /api/v1/query/stream, and POST /api/v1/feedback.
Per-hashed-IP rate limiting and CORS are applied at the application layer;
these routes handle the request/response contract only.

Implemented in Phase 6. Router registered in Phase 0 so the application
factory can reference it without stubbing main.py.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["query"])
