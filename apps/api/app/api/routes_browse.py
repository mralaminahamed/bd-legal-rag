"""Faceted browse endpoints (FR-FB-3..5, FR-DL-3).

GET /api/v1/acts                              — list all Acts.
GET /api/v1/acts/{slug}/structure             — Part → Chapter → Section tree.
GET /api/v1/acts/{slug}/sections/{section}    — full provision detail with disclaimer.

No rate limiting on browse endpoints (read-only, low cost).

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import json as _json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_redis
from app.api.schemas import (
    ActStructure,
    ActSummary,
    ProvisionTreeNode,
    RevisionDetail,
    SectionDetail,
)
from app.config import Settings, get_settings
from app.db.models import Act, Provision
from app.prompts.safety import disclaimer as disclaimer_mod

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["browse"])


def _act_to_summary(act: Act) -> ActSummary:
    """Convert an Act ORM row to an API summary.

    Args:
        act: Act ORM instance.

    Returns:
        ActSummary: Serialisable summary.
    """
    return ActSummary(
        id=str(act.id),
        slug=act.slug,
        short_name=act.short_name,
        full_name_en=act.full_name_en,
        full_name_bn=act.full_name_bn,
        act_number=act.act_number,
        act_year=act.act_year,
        status=act.status,
        ministry=act.ministry,
    )


def _build_tree(provisions: list[Provision]) -> list[ProvisionTreeNode]:
    """Build a recursive tree from a flat list of provisions ordered by sort_path.

    Args:
        provisions: All provisions for an Act, ordered by sort_path.

    Returns:
        list[ProvisionTreeNode]: Root-level tree nodes with children populated.
    """
    nodes: dict[str, ProvisionTreeNode] = {}
    roots: list[ProvisionTreeNode] = []
    children_map: dict[str, list[ProvisionTreeNode]] = {}

    for p in provisions:
        node = ProvisionTreeNode(
            id=str(p.id),
            kind=p.kind,
            number=p.number,
            title=p.title,
            sort_path=p.sort_path,
            children=[],
        )
        nodes[str(p.id)] = node
        parent_id = str(p.parent_id) if p.parent_id else None
        if parent_id is None:
            roots.append(node)
        else:
            children_map.setdefault(parent_id, []).append(node)

    for pid, children in children_map.items():
        if pid in nodes:
            nodes[pid].children.extend(children)

    return roots


@router.get(
    "/acts",
    response_model=list[ActSummary],
    summary="List all registered Acts (FR-FB-3)",
)
async def list_acts(
    session: AsyncSession = Depends(get_db),
) -> list[ActSummary]:
    """Return all Acts ordered by year then English name.

    Args:
        session: Async database session.

    Returns:
        list[ActSummary]: All registered Acts.
    """
    result = await session.execute(
        select(Act).order_by(Act.act_year, Act.full_name_en)
    )
    acts = result.scalars().all()
    return [_act_to_summary(a) for a in acts]


@router.get(
    "/acts/{slug}/structure",
    response_model=ActStructure,
    summary="Statutory tree for an Act (FR-FB-3)",
)
async def act_structure(
    slug: str,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> ActStructure:
    """Return the Act with its full Part → Chapter → Section tree.

    Args:
        slug: Act slug (e.g. ``labour-act-2006``).
        session: Async database session.
        redis: Shared Redis client.
        settings: Application settings.

    Returns:
        ActStructure: Act metadata and provision tree.

    Raises:
        HTTPException: 404 when the slug is unknown.
    """
    _cache_key = f"act:structure:{slug}"
    _cached = await redis.get(_cache_key)
    if _cached:
        return ActStructure.model_validate(_json.loads(_cached))

    result = await session.execute(select(Act).where(Act.slug == slug))
    act = result.scalar_one_or_none()
    if act is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"act not found: {slug!r}",
        )

    provisions_result = await session.execute(
        select(Provision)
        .where(Provision.act_id == act.id)
        .order_by(Provision.sort_path)
    )
    provisions = list(provisions_result.scalars().all())

    _result = ActStructure(act=_act_to_summary(act), tree=_build_tree(provisions))
    await redis.set(_cache_key, _result.model_dump_json(), ex=settings.act_structure_cache_ttl)
    return _result


@router.get(
    "/acts/{slug}/sections/{section}",
    response_model=SectionDetail,
    summary="Provision text and all revisions (FR-FB-4)",
)
async def section_detail(
    slug: str,
    section: str,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SectionDetail:
    """Return full provision detail: text, hierarchy, effective dates, disclaimer.

    The disclaimer is always included (NFR-LS-1).

    Args:
        slug: Act slug.
        section: Provision number within the Act (e.g. ``103``).
        session: Async database session.
        settings: Application settings.

    Returns:
        SectionDetail: Full provision with all revisions and the active disclaimer.

    Raises:
        HTTPException: 404 when the Act or provision is unknown.
    """
    act_result = await session.execute(select(Act).where(Act.slug == slug))
    act = act_result.scalar_one_or_none()
    if act is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"act not found: {slug!r}",
        )

    prov_result = await session.execute(
        select(Provision)
        .where(Provision.act_id == act.id, Provision.number == section)
        .options(selectinload(Provision.revisions))
        .limit(1)
    )
    provision = prov_result.scalar_one_or_none()
    if provision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"section {section!r} not found in act {slug!r}",
        )

    disclaimer_obj = disclaimer_mod.resolve(settings.active_disclaimer_version)
    disc = disclaimer_obj.en

    revisions = [
        RevisionDetail(
            language=rev.language,
            translation_status=rev.translation_status,
            text=rev.text,
            effective_from=rev.effective_from,
            effective_to=rev.effective_to,
            source_url=rev.source_url,
        )
        for rev in sorted(
            provision.revisions,
            key=lambda r: (r.language, r.effective_from),
        )
    ]

    hierarchy_path = f"{act.full_name_en} > {provision.kind.capitalize()} {provision.number}"
    if provision.title:
        hierarchy_path += f" ({provision.title})"

    return SectionDetail(
        provision_id=str(provision.id),
        act_slug=slug,
        kind=provision.kind,
        number=provision.number,
        title=provision.title,
        hierarchy_path=hierarchy_path,
        revisions=revisions,
        disclaimer=disc,
    )


@router.get(
    "/provisions/{provision_id}",
    response_model=SectionDetail,
    summary="Provision detail by UUID (for Act reader navigation)",
)
async def provision_by_id(
    provision_id: str,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis),
) -> SectionDetail:
    """Return full provision detail by UUID.

    Used by the Act reader to load sections identified by their tree node id
    rather than by section number (which is not unique across subsections).

    Args:
        provision_id: Provision UUID from the structure tree.
        session: Async database session.
        settings: Application settings.
        redis: Shared Redis client.

    Returns:
        SectionDetail: Full provision with revisions and the active disclaimer.

    Raises:
        HTTPException: 404 when the provision UUID is unknown.
        HTTPException: 422 when provision_id is not a valid UUID.
    """
    try:
        prov_uuid = uuid.UUID(provision_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid provision id: {provision_id!r}",
        ) from exc

    _cache_key = f"provision:{provision_id}"
    _cached = await redis.get(_cache_key)
    if _cached:
        return SectionDetail.model_validate(_json.loads(_cached))

    prov_result = await session.execute(
        select(Provision)
        .where(Provision.id == prov_uuid)
        .options(selectinload(Provision.revisions))
    )
    provision = prov_result.scalar_one_or_none()
    if provision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"provision {provision_id!r} not found",
        )

    # Load the owning Act for slug and name
    act = await session.get(Act, provision.act_id)
    if act is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="act not found")

    disclaimer_obj = disclaimer_mod.resolve(settings.active_disclaimer_version)
    disc = disclaimer_obj.en

    revisions = [
        RevisionDetail(
            language=rev.language,
            translation_status=rev.translation_status,
            text=rev.text,
            effective_from=rev.effective_from,
            effective_to=rev.effective_to,
            source_url=rev.source_url,
        )
        for rev in sorted(provision.revisions, key=lambda r: (r.language, r.effective_from))
    ]

    hierarchy_path = f"{act.full_name_en} > {provision.kind.capitalize()} {provision.number}"
    if provision.title:
        hierarchy_path += f" ({provision.title})"

    _detail = SectionDetail(
        provision_id=str(provision.id),
        act_slug=act.slug,
        kind=provision.kind,
        number=provision.number,
        title=provision.title,
        hierarchy_path=hierarchy_path,
        revisions=revisions,
        disclaimer=disc,
    )
    await redis.set(_cache_key, _detail.model_dump_json(), ex=settings.provision_cache_ttl)
    return _detail
