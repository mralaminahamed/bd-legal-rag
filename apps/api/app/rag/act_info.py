"""Act information queries that don't need the LLM (section lists, etc.).

Author: Al Amin Ahamed.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Act, Provision


async def section_list_markdown(
    act_id_or_slug: str,
    session: AsyncSession,
    language: str = "en",
) -> str | None:
    """Return a markdown-formatted section list for an Act.

    Queries the provisions table directly — no LLM involved.

    Args:
        act_id_or_slug: Act slug or UUID string.
        session: Async database session.
        language: ``"bn"`` or ``"en"`` — controls the act name used in header.

    Returns:
        str | None: Markdown string, or ``None`` when the act is not found.
    """
    # Resolve act
    import uuid as _uuid  # noqa: PLC0415

    act: Act | None = None
    try:
        uid = _uuid.UUID(act_id_or_slug)
        act = await session.get(Act, uid)
    except ValueError:
        result = await session.execute(select(Act).where(Act.slug == act_id_or_slug))
        act = result.scalar_one_or_none()

    if act is None:
        return None

    provisions_result = await session.execute(
        select(Provision)
        .where(Provision.act_id == act.id)
        .order_by(Provision.sort_path)
    )
    provisions = list(provisions_result.scalars().all())

    act_name = act.full_name_bn if language == "bn" else act.full_name_en
    lines: list[str] = [f"## {act_name}", f"*Act {act.act_number} of {act.act_year}*", ""]

    current_chapter: str | None = None

    for p in provisions:
        if p.kind == "act":
            continue
        if p.kind == "part":
            current_chapter = None
            lines.append(f"\n### Part {p.number}{': ' + p.title if p.title else ''}")
        elif p.kind == "chapter":
            current_chapter = p.number
            lines.append(f"\n#### Chapter {p.number}{': ' + p.title if p.title else ''}")
        elif p.kind == "section":
            indent = "  - " if current_chapter else "- "
            title_part = f" — {p.title}" if p.title else ""
            lines.append(f"{indent}§{p.number}{title_part}")
        elif p.kind in ("subsection", "clause"):
            lines.append(f"    - ({p.number})")

    if len(provisions) <= 1:
        lines.append("\n*Section data not yet indexed. Trigger ingestion to populate.*")

    return "\n".join(lines)
