"""Faceted browse endpoints (FR-FB-3..5).

Exposes GET /api/v1/acts, GET /api/v1/acts/{slug}/structure, and
GET /api/v1/acts/{slug}/sections/{section} for navigating the statutory corpus
without issuing a query.

Implemented in Phase 6. Router registered in Phase 0.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["browse"])
