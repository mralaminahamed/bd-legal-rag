"""Migrations describe the schema as it was, so they must not read it from the models.

Migration 0001 imported ``EMBED_DIMENSIONS`` and ``HNSW_OPS`` from ``app.db.models``.
Those constants moved on (1024 to 2560, ``vector_cosine_ops`` to ``halfvec_cosine_ops``)
and migration f7bdf0070aad exists to make that change, so on an empty database 0001
built a ``vector(2560)`` column and asked for a ``halfvec`` index over it. PostgreSQL
answered ``operator class "halfvec_cosine_ops" does not accept data type vector`` and
``alembic upgrade head`` failed from scratch. It only ever worked on a database that
had been migrated before the constants changed, which is why nobody saw it.

A migration that needs a number writes the number.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

VERSIONS = Path(__file__).resolve().parents[1] / "app" / "db" / "migrations" / "versions"
MIGRATIONS = sorted(VERSIONS.glob("*.py"))


def test_migrations_are_found() -> None:
    """The glob must find the migrations, or the check below passes over nothing."""
    assert len(MIGRATIONS) >= 2


@pytest.mark.parametrize("path", MIGRATIONS, ids=lambda p: p.name)
def test_migration_does_not_import_the_models(path: Path) -> None:
    """No migration imports ``app.db.models``, directly or by name."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("app.db.models"):
            offenders.append(f"from {node.module} import ...")
        if isinstance(node, ast.Import):
            offenders.extend(a.name for a in node.names if a.name.startswith("app.db.models"))
    assert not offenders, f"{path.name} reads the live models: {offenders}"


def test_initial_schema_is_the_original_1024_wide_vector() -> None:
    """0001 is the schema as first written; f7bdf0070aad is what widens it."""
    source = (VERSIONS / "20260531_0001_initial_schema.py").read_text(encoding="utf-8")
    assert "_EMBED_DIMENSIONS = 1024" in source
    assert '_HNSW_OPS = "vector_cosine_ops"' in source
