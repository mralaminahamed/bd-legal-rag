"""Change embedding column from vector(1024) to halfvec(2560) for Ollama qwen3-embedding:4b.

Drops all existing chunks (fake seeded data), changes the embedding column type
to halfvec (half-precision, pgvector 0.7+), and rebuilds the HNSW cosine index.
halfvec supports HNSW up to 4000 dims (vector is capped at 2000). Cohere
embed-multilingual-v3.0 (1024-dim vector) is replaced by qwen3-embedding:4b
(2560-dim halfvec) as the local-first multilingual embedding model.

Revision ID: f7bdf0070aad
Revises: 0001
Create Date: 2026-06-02

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa  # noqa: F401
from alembic import op

revision: str = "f7bdf0070aad"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_DIMS = 2560
_OLD_DIMS = 1024
_NEW_OPS = "halfvec_cosine_ops"
_OLD_OPS = "vector_cosine_ops"


def upgrade() -> None:
    """Truncate chunks, change embedding to halfvec(2560), rebuild HNSW index."""
    op.execute("TRUNCATE TABLE chunks CASCADE")
    op.drop_index("chunks_embedding_hnsw", table_name="chunks")
    # halfvec supports HNSW up to 4000 dims; vector is capped at 2000.
    op.execute(f"ALTER TABLE chunks ALTER COLUMN embedding TYPE halfvec({_NEW_DIMS})")
    op.create_index(
        "chunks_embedding_hnsw",
        "chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": _NEW_OPS},
    )


def downgrade() -> None:
    """Revert to vector(1024) — also truncates chunks."""
    op.execute("TRUNCATE TABLE chunks CASCADE")
    op.drop_index("chunks_embedding_hnsw", table_name="chunks")
    op.execute(f"ALTER TABLE chunks ALTER COLUMN embedding TYPE vector({_OLD_DIMS})")
    op.create_index(
        "chunks_embedding_hnsw",
        "chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": _OLD_OPS},
    )
