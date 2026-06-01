# Author: Al Amin Ahamed
"""Seed the five v1.0 Acts from config/acts/*.yaml.

Idempotent: uses ``ON CONFLICT (slug) DO UPDATE`` so re-running updates any
changed YAML fields without duplicating rows.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import yaml
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Act
from app.seeders.base import Seeder

# Mirrors the path resolution in app.ingestion.registry.
_CONFIG_DIR = Path(
    os.environ.get("BDRAG_ACTS_CONFIG_DIR")
    or (Path(__file__).parents[4] / "config" / "acts")
)


class ActsSeeder(Seeder):
    """Upsert all YAML-registered Acts into the ``acts`` table.

    Uses ``ON CONFLICT (slug) DO UPDATE`` so metadata changes in YAML files
    are propagated on re-run without duplicating rows or dropping ingestion
    history.
    """

    name = "acts"
    depends_on: list[str] = []
    truncate_sql = [
        "TRUNCATE TABLE feedback CASCADE",
        "TRUNCATE TABLE queries CASCADE",
        "TRUNCATE TABLE ingestion_runs CASCADE",
        "TRUNCATE TABLE chunks CASCADE",
        "TRUNCATE TABLE provision_revisions CASCADE",
        "TRUNCATE TABLE provisions CASCADE",
        "TRUNCATE TABLE acts CASCADE",
    ]

    async def run(self, db: AsyncSession, *, count: int) -> int:  # noqa: ARG002
        """Upsert Acts from every YAML file found in the config directory.

        Args:
            db: Active async database session.
            count: Unused — all YAMLs are always loaded.

        Returns:
            int: Number of rows upserted.
        """
        yaml_files = sorted(_CONFIG_DIR.glob("*.yaml"))  # noqa: ASYNC240
        if not yaml_files:
            raise FileNotFoundError(f"No YAML files found in {_CONFIG_DIR}")

        inserted = 0
        for path in yaml_files:
            with path.open(encoding="utf-8") as fh:  # noqa: ASYNC240
                data: dict[str, object] = yaml.safe_load(fh)

            stmt = (
                pg_insert(Act)
                .values(
                    id=uuid.uuid4(),
                    slug=data["slug"],
                    short_name=data["short_name"],
                    full_name_en=data["full_name_en"],
                    full_name_bn=data["full_name_bn"],
                    act_number=data["act_number"],
                    act_year=int(str(data["act_year"])),
                    ministry=data.get("ministry"),
                    status=data.get("status", "in_force"),
                )
                .on_conflict_do_update(
                    index_elements=["slug"],
                    set_={
                        "short_name": data["short_name"],
                        "full_name_en": data["full_name_en"],
                        "full_name_bn": data["full_name_bn"],
                        "act_number": data["act_number"],
                        "act_year": int(str(data["act_year"])),
                        "ministry": data.get("ministry"),
                        "status": data.get("status", "in_force"),
                    },
                )
            )
            await db.execute(stmt)
            inserted += 1

        await db.flush()
        return inserted
