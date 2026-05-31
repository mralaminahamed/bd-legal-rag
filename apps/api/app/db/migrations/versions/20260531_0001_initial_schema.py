"""Initial schema: extensions, tables, and indexes.

Creates the full data model from docs/02-Architecture.md §3.2: the ``vector``
and ``pg_trgm`` extensions; all seven tables with their constraints and uniques;
and the chunk indexes (HNSW on the embedding with ``vector_cosine_ops``, GIN on
the lexical vector, btree on ``(act_id, language)``).

The lexical vector uses the ``simple`` configuration (ADR-007) because Postgres
ships no Bengali dictionary.

Revision ID: 0001
Revises:
Create Date: 2026-05-31

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from app.db.models import EMBED_DIMENSIONS, HNSW_OPS
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create extensions, tables, and indexes."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "acts",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("short_name", sa.Text(), nullable=False),
        sa.Column("full_name_en", sa.Text(), nullable=False),
        sa.Column("full_name_bn", sa.Text(), nullable=False),
        sa.Column("act_number", sa.Text(), nullable=False),
        sa.Column("act_year", sa.Integer(), nullable=False),
        sa.Column("ministry", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'in_force'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("slug", name="acts_slug_key"),
        sa.CheckConstraint(
            "status IN ('in_force','partially_repealed','repealed')",
            name="acts_status_check",
        ),
    )

    op.create_table(
        "provisions",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("act_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("parent_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("number", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("sort_path", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["act_id"], ["acts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["provisions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("act_id", "sort_path", name="provisions_act_id_sort_path_key"),
        sa.CheckConstraint(
            "kind IN ('part','chapter','section','subsection','clause')",
            name="provisions_kind_check",
        ),
    )
    op.create_index("provisions_act_id", "provisions", ["act_id"])

    op.create_table(
        "provision_revisions",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("provision_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("translation_status", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("amending_act_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["provision_id"], ["provisions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["amending_act_id"], ["acts.id"]),
        sa.CheckConstraint("language IN ('bn','en')", name="provision_revisions_language_check"),
        sa.CheckConstraint(
            "translation_status IN ('authoritative','reference_translation')",
            name="provision_revisions_translation_status_check",
        ),
    )
    op.create_index(
        "provision_revisions_effective",
        "provision_revisions",
        ["provision_id", "language", "effective_from", "effective_to"],
    )

    op.create_table(
        "chunks",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("revision_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("provision_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("act_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("hierarchy_path", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "content_tsv",
            postgresql.TSVECTOR(),
            # 'simple' config — Bengali has no Postgres dictionary (ADR-007).
            sa.Computed("to_tsvector('simple', content)", persisted=True),
            nullable=False,
        ),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(EMBED_DIMENSIONS), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["revision_id"], ["provision_revisions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provision_id"], ["provisions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["act_id"], ["acts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "revision_id", "chunk_index", name="chunks_revision_id_chunk_index_key"
        ),
        sa.CheckConstraint("language IN ('bn','en')", name="chunks_language_check"),
    )
    op.create_index(
        "chunks_embedding_hnsw",
        "chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": HNSW_OPS},
    )
    op.create_index("chunks_content_tsv_gin", "chunks", ["content_tsv"], postgresql_using="gin")
    op.create_index("chunks_act_language", "chunks", ["act_id", "language"])

    op.create_table(
        "ingestion_runs",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("act_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "provisions_processed", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("chunks_created", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["act_id"], ["acts.id"], ondelete="CASCADE"),
        sa.CheckConstraint("language IN ('bn','en')", name="ingestion_runs_language_check"),
        sa.CheckConstraint(
            "status IN ('running','succeeded','failed')",
            name="ingestion_runs_status_check",
        ),
    )

    op.create_table(
        "queries",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("correlation_id", sa.Text(), nullable=False),
        sa.Column("detected_language", sa.Text(), nullable=True),
        sa.Column("selected_language", sa.Text(), nullable=True),
        sa.Column(
            "act_ids",
            postgresql.ARRAY(sa.Uuid(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'::uuid[]"),
        ),
        sa.Column("as_of_date", sa.Date(), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column(
            "retrieved_chunk_ids",
            postgresql.ARRAY(sa.Uuid(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'::uuid[]"),
        ),
        sa.Column("rerank_top_score", sa.Numeric(6, 4), nullable=True),
        sa.Column("declined", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("decline_reason", sa.Text(), nullable=True),
        sa.Column("confidence_tier", sa.Text(), nullable=True),
        sa.Column("degraded", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("disclaimer_version", sa.Text(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("cached", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("ip_hash", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "detected_language IN ('bn','en')", name="queries_detected_language_check"
        ),
        sa.CheckConstraint(
            "selected_language IN ('bn','en')", name="queries_selected_language_check"
        ),
        sa.CheckConstraint(
            "confidence_tier IN ('HIGH','MEDIUM','LOW')",
            name="queries_confidence_tier_check",
        ),
    )

    op.create_table(
        "feedback",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("query_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("rating", sa.Text(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["query_id"], ["queries.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "rating IN ('helpful','not_helpful','wrong_citation','out_of_scope')",
            name="feedback_rating_check",
        ),
    )


def downgrade() -> None:
    """Drop tables in reverse dependency order.

    Extensions are left in place; dropping them may affect other schemas.
    """
    op.drop_table("feedback")
    op.drop_table("queries")
    op.drop_table("ingestion_runs")
    op.drop_index("chunks_act_language", table_name="chunks")
    op.drop_index("chunks_content_tsv_gin", table_name="chunks")
    op.drop_index("chunks_embedding_hnsw", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("provision_revisions_effective", table_name="provision_revisions")
    op.drop_table("provision_revisions")
    op.drop_index("provisions_act_id", table_name="provisions")
    op.drop_table("provisions")
    op.drop_table("acts")
