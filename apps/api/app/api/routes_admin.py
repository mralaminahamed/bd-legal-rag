"""Admin endpoints (bearer-authenticated, NFR-SC-2).

Exposes ingestion triggers, Acts registry management, LLM provider override
(GET/PUT/DELETE /api/v1/admin/llm), metrics, and the queries activity feed.

Implemented in Phase 6. Router registered in Phase 0.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
