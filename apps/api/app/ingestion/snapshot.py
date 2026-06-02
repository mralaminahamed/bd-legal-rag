"""CLI command: crawl all Acts and save HTML snapshots to disk.

Two-phase crawl:
  Phase 1 — main act page  (``data/raw/{slug}/{lang}.html``)
  Phase 2 — per-section pages (``data/raw/{slug}/sections/{lang}/{sectionId}.html``)

Usage (from apps/api/):
    uv run python -m app.ingestion.snapshot                   # all acts, main page only
    uv run python -m app.ingestion.snapshot --sections        # main + all section sub-pages
    uv run python -m app.ingestion.snapshot --slug digital-security-act-2018 --sections
    uv run python -m app.ingestion.snapshot --force           # overwrite existing snapshots

Re-ingesting from snapshots (no network):
    The normal ingest task automatically uses snapshots when they exist.
    Trigger via:
        uv run python -m app.ingestion.registry ingest-all

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
from pathlib import Path

from app.config import get_settings
from app.ingestion.crawler import fetch_act_page
from app.ingestion.registry import get_source_urls

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Extract /act-{actId}/section-{sectionId}.html or /act-{actId}/chapter-{id}.html links
_SECTION_LINK_RE = re.compile(
    r'href="(/act-(\d+)/(section|chapter|sub-section)-(\d+)\.html)"',
    re.IGNORECASE,
)
_BDLAWS_BASE = "https://bdlaws.minlaw.gov.bd"


def _extract_section_links(html: str) -> list[tuple[str, str]]:
    """Extract per-section links from a bdlaws act main page.

    Args:
        html: Main act page HTML.

    Returns:
        list[tuple[str, str]]: List of (section_id, full_url) pairs. section_id
            is the numeric bdlaws ID (e.g. ``"47459"``).
    """
    seen: set[str] = set()
    results: list[tuple[str, str]] = []
    for m in _SECTION_LINK_RE.finditer(html):
        path = m.group(1)
        section_id = m.group(4)
        url = f"{_BDLAWS_BASE}{path}"
        if url not in seen:
            seen.add(url)
            results.append((section_id, url))
    return results


def _write_snapshot(snap_dir: Path, stem: str, html: str, url: str, fetched_at: str) -> Path:
    """Write HTML and meta files to disk (sync, for use in a thread executor).

    Args:
        snap_dir: Target directory.
        stem: Filename stem (e.g. ``"en"`` or ``"47459"``).
        html: Raw HTML content.
        url: Source URL to persist in the meta file.
        fetched_at: ISO-format timestamp to persist in the meta file.

    Returns:
        Path: The html file path that was written.
    """
    snap_dir.mkdir(parents=True, exist_ok=True)
    html_file = snap_dir / f"{stem}.html"
    meta_file = snap_dir / f"{stem}.meta.json"
    html_file.write_text(html, encoding="utf-8")
    meta_file.write_text(
        json.dumps({"url": url, "fetched_at": fetched_at}),
        encoding="utf-8",
    )
    return html_file


async def snapshot_act(slug: str, language: str, snap_dir: Path, force: bool) -> str | None:
    """Fetch one (act, language) main page and save it to *snap_dir*.

    Args:
        slug: Act slug.
        language: ``"bn"`` or ``"en"``.
        snap_dir: Directory for the main-page snapshot.
        force: When True, overwrite an existing snapshot.

    Returns:
        str | None: Raw HTML when a new/updated snapshot was written, else None.
    """
    html_file = snap_dir / f"{language}.html"

    if html_file.exists() and not force:
        logger.info("skip main (exists): %s/%s", slug, language)
        return html_file.read_text(encoding="utf-8")

    sources = await get_source_urls(slug)
    source = next((s for s in sources if s.get("language") == language), None)
    if source is None:
        logger.warning("no source configured: %s/%s", slug, language)
        return None

    logger.info("fetching %s/%s from %s", slug, language, source["source_url"])
    try:
        result = await fetch_act_page(source["source_url"], slug, language)
    except Exception as exc:
        logger.error("fetch failed %s/%s: %s", slug, language, exc)
        return None

    if result.not_modified:
        logger.info("not modified: %s/%s", slug, language)
        return html_file.read_text(encoding="utf-8") if html_file.exists() else None

    await asyncio.to_thread(
        _write_snapshot,
        snap_dir,
        language,
        result.html,
        result.url,
        result.fetched_at.isoformat(),
    )
    logger.info("saved main snapshot: %s/%s (%d bytes)", slug, language, len(result.html))
    return result.html


async def snapshot_sections(
    slug: str,
    language: str,
    main_html: str,
    sections_dir: Path,
    force: bool,
    semaphore: asyncio.Semaphore,
) -> tuple[int, int, int]:
    """Crawl all per-section sub-pages found in *main_html* and save to disk.

    Saves each section to ``{sections_dir}/{sectionId}.html`` with a companion
    ``{sectionId}.meta.json``.  Also writes ``index.json`` mapping section IDs
    to their canonical URLs.

    Args:
        slug: Act slug (used for logging).
        language: ``"bn"`` or ``"en"``.
        main_html: Raw HTML of the main act page.
        sections_dir: Directory to save section snapshots.
        force: Overwrite existing section snapshots when True.
        semaphore: Concurrency limiter shared across all section fetches.

    Returns:
        tuple[int, int, int]: (written, skipped, failed) counts.
    """
    links = _extract_section_links(main_html)
    if not links:
        logger.warning("no section links found in %s/%s main page", slug, language)
        return 0, 0, 0

    await asyncio.to_thread(sections_dir.mkdir, parents=True, exist_ok=True)

    # Save index.json mapping section_id → canonical URL
    index = dict(links)
    await asyncio.to_thread(
        (sections_dir / "index.json").write_text,
        json.dumps(index, ensure_ascii=False, indent=2),
        "utf-8",
    )

    written = skipped = failed = 0

    async def _fetch_one(section_id: str, url: str) -> None:
        nonlocal written, skipped, failed
        html_file = sections_dir / f"{section_id}.html"
        if html_file.exists() and not force:
            skipped += 1
            return
        async with semaphore:
            try:
                result = await fetch_act_page(url, slug, language)
                if not result.not_modified and result.html:
                    await asyncio.to_thread(
                        _write_snapshot,
                        sections_dir,
                        section_id,
                        result.html,
                        result.url,
                        result.fetched_at.isoformat(),
                    )
                    written += 1
                else:
                    skipped += 1
            except Exception as exc:
                logger.error("section fetch failed %s/%s/%s: %s", slug, language, section_id, exc)
                failed += 1

    await asyncio.gather(*[_fetch_one(sid, url) for sid, url in links])

    logger.info(
        "sections %s/%s — written=%d skipped=%d failed=%d (total=%d)",
        slug, language, written, skipped, failed, len(links),
    )
    return written, skipped, failed


async def run(slugs: list[str], force: bool, with_sections: bool) -> None:
    """Snapshot all requested acts in both languages.

    Args:
        slugs: Act slugs to process.
        force: Overwrite existing snapshots when True.
        with_sections: When True, also crawl per-section sub-pages.
    """
    settings = get_settings()
    base_dir = Path(settings.html_snapshot_dir)
    # Rate-limit concurrent section fetches: max 3 parallel requests
    semaphore = asyncio.Semaphore(3)

    main_ok = main_skip = 0
    sec_written = sec_skip = sec_fail = 0

    for slug in slugs:
        for lang in ("bn", "en"):
            snap_dir = base_dir / slug
            html = await snapshot_act(slug, lang, snap_dir, force)
            if html:
                main_ok += 1
            else:
                main_skip += 1
                continue

            if with_sections:
                sections_dir = snap_dir / "sections" / lang
                w, s, f = await snapshot_sections(slug, lang, html, sections_dir, force, semaphore)
                sec_written += w
                sec_skip += s
                sec_fail += f

    logger.info(
        "snapshot complete — main written=%d skipped=%d | sections written=%d skipped=%d failed=%d",
        main_ok, main_skip, sec_written, sec_skip, sec_fail,
    )


def _all_slugs() -> list[str]:
    """Return all Act slugs from config/acts/*.yaml.

    Returns:
        list[str]: Sorted slug list.
    """
    acts_dir = Path(__file__).parents[4] / "config" / "acts"
    slugs: list[str] = []
    for yaml_file in sorted(acts_dir.glob("*.yaml")):
        for line in yaml_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("slug:"):
                slugs.append(line.split(":", 1)[1].strip())
                break
    return slugs


def main() -> None:
    """Entry point for ``python -m app.ingestion.snapshot``.

    Returns:
        None
    """
    parser = argparse.ArgumentParser(
        description="Crawl bdlaws and save raw HTML snapshots to disk."
    )
    parser.add_argument("--slug", help="Single act slug to snapshot (default: all acts)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing snapshots")
    parser.add_argument(
        "--sections",
        action="store_true",
        help="Also crawl per-section sub-pages (act-{id}/section-{id}.html)",
    )
    args = parser.parse_args()

    slugs = [args.slug] if args.slug else _all_slugs()
    if not slugs:
        logger.error("no acts found in config/acts/")
        sys.exit(1)

    logger.info(
        "snapshotting %d act(s)%s ...",
        len(slugs),
        " + section sub-pages" if args.sections else "",
    )
    asyncio.run(run(slugs, force=args.force, with_sections=args.sections))


if __name__ == "__main__":
    main()
