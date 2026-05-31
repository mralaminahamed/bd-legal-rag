"""Act registry: declarative bootstrap and lookup helpers.

Reads ``config/acts/*.yaml`` from the repository root (two levels above
``apps/api/``) and upserts the five v1.0 Acts into the database. Bootstrap is
idempotent: re-running it picks up new YAML files and updates changed fields
without touching ingestion history.

Source URLs in the YAML are persisted on the Act row so the crawler can resolve
them without parsing the YAML at runtime.

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Act

logger = logging.getLogger(__name__)

# config/acts/ lives two directories above apps/api/ (repo root → config/acts/).
_CONFIG_DIR = Path(__file__).parents[4] / "config" / "acts"


@dataclass(frozen=True)
class ActConfig:
    """Parsed representation of one config/acts/*.yaml file.

    Attributes:
        slug: Unique registry key (e.g. ``labour-act-2006``).
        short_name: Display name.
        full_name_en: Official English title.
        full_name_bn: Official Bengali title (authoritative).
        act_number: Roman-numeral act number.
        act_year: Year of enactment.
        ministry: Responsible ministry, if present.
        status: Lifecycle status (``in_force`` etc.).
        sources: List of per-language source descriptors from the YAML.
    """

    slug: str
    short_name: str
    full_name_en: str
    full_name_bn: str
    act_number: str
    act_year: int
    ministry: str | None
    status: str
    sources: list[dict[str, str]]


def _load_act_configs() -> list[ActConfig]:
    """Read all ``*.yaml`` files from the acts config directory.

    Returns:
        list[ActConfig]: Parsed Act configurations, one per YAML file.

    Raises:
        ValueError: If a YAML file is missing a required field.
    """
    configs: list[ActConfig] = []
    for path in sorted(_CONFIG_DIR.glob("*.yaml")):
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
        try:
            configs.append(
                ActConfig(
                    slug=raw["slug"],
                    short_name=raw["short_name"],
                    full_name_en=raw["full_name_en"],
                    full_name_bn=raw["full_name_bn"],
                    act_number=raw["act_number"],
                    act_year=int(raw["act_year"]),
                    ministry=raw.get("ministry"),
                    status=raw.get("status", "in_force"),
                    sources=raw.get("sources", []),
                )
            )
        except KeyError as exc:
            raise ValueError(f"required field {exc} missing in {path.name}") from exc
    return configs


async def bootstrap(session: AsyncSession) -> dict[str, str]:
    """Upsert the five v1.0 Acts from ``config/acts/*.yaml`` into the database.

    The operation is idempotent: Acts that already exist are updated if any
    field has changed; Acts not in any YAML file are left untouched.

    Args:
        session: An active async database session.

    Returns:
        dict[str, str]: Mapping of slug → ``"inserted"`` or ``"updated"`` for
        each Act processed.
    """
    configs = _load_act_configs()
    results: dict[str, str] = {}

    for cfg in configs:
        stmt = (
            pg_insert(Act)
            .values(
                slug=cfg.slug,
                short_name=cfg.short_name,
                full_name_en=cfg.full_name_en,
                full_name_bn=cfg.full_name_bn,
                act_number=cfg.act_number,
                act_year=cfg.act_year,
                ministry=cfg.ministry,
                status=cfg.status,
            )
            .on_conflict_do_update(
                index_elements=["slug"],
                set_={
                    "short_name": cfg.short_name,
                    "full_name_en": cfg.full_name_en,
                    "full_name_bn": cfg.full_name_bn,
                    "act_number": cfg.act_number,
                    "act_year": cfg.act_year,
                    "ministry": cfg.ministry,
                    "status": cfg.status,
                },
            )
            .returning(Act.id)
        )
        result = await session.execute(stmt)
        row = result.fetchone()
        action = "inserted" if row else "updated"
        results[cfg.slug] = action
        logger.info("bootstrapped act", extra={"slug": cfg.slug, "action": action})

    await session.commit()
    logger.info("bootstrap complete", extra={"acts": len(results)})
    return results


async def get_act_by_slug(session: AsyncSession, slug: str) -> Act | None:
    """Return the Act with the given slug, or ``None`` if absent.

    Args:
        session: An active async database session.
        slug: The unique Act slug (e.g. ``labour-act-2006``).

    Returns:
        Act | None: The matching Act row, or ``None``.
    """
    result = await session.execute(select(Act).where(Act.slug == slug))
    return result.scalar_one_or_none()


async def list_acts(session: AsyncSession) -> list[Act]:
    """Return all registered Acts ordered by act_year then act_number.

    Args:
        session: An active async database session.

    Returns:
        list[Act]: All Act rows in ascending year order.
    """
    result = await session.execute(select(Act).order_by(Act.act_year, Act.act_number))
    return list(result.scalars().all())


async def get_source_urls(slug: str) -> list[dict[str, str]]:
    """Return the source descriptors from the YAML for the named Act.

    This reads the YAML on each call (no DB query); it is only used by the
    crawler at ingestion time when the config directory is guaranteed present.

    Args:
        slug: The Act slug to look up.

    Returns:
        list[dict[str, str]]: Source descriptors with ``language`` and
        ``source_url`` keys, or an empty list if the Act is not declared.
    """
    for cfg in _load_act_configs():
        if cfg.slug == slug:
            return cfg.sources
    return []
