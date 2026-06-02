"""CLI command: crawl all Acts and save HTML snapshots to disk.

Usage (from apps/api/):
    uv run python -m app.ingestion.snapshot             # all acts, both languages
    uv run python -m app.ingestion.snapshot --slug labour-act-2006
    uv run python -m app.ingestion.snapshot --force     # overwrite existing snapshots

Snapshots are saved to ``settings.html_snapshot_dir/{slug}/{lang}.html``.
A companion ``{lang}.meta.json`` stores the source URL and fetch timestamp.

Re-ingesting from snapshots (no network):
    The normal ingest task automatically uses snapshots when they exist.
    Trigger via the admin API or:
        uv run python -m app.ingestion.registry ingest-all

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from app.config import get_settings
from app.ingestion.crawler import fetch_act_page
from app.ingestion.registry import get_source_urls

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _write_snapshot(snap_dir: Path, language: str, html: str, url: str, fetched_at: str) -> Path:
    """Write HTML and meta files to disk (sync, for use in a thread executor).

    Args:
        snap_dir: Target directory.
        language: Language code used as filename stem.
        html: Raw HTML content.
        url: Source URL to persist in the meta file.
        fetched_at: ISO-format timestamp to persist in the meta file.

    Returns:
        Path: The html file path that was written.
    """
    snap_dir.mkdir(parents=True, exist_ok=True)
    html_file = snap_dir / f"{language}.html"
    meta_file = snap_dir / f"{language}.meta.json"
    html_file.write_text(html, encoding="utf-8")
    meta_file.write_text(
        json.dumps({"url": url, "fetched_at": fetched_at}),
        encoding="utf-8",
    )
    return html_file


async def snapshot_act(slug: str, language: str, snap_dir: Path, force: bool) -> bool:
    """Fetch one (act, language) page and save it to *snap_dir*.

    Args:
        slug: Act slug.
        language: ``"bn"`` or ``"en"``.
        snap_dir: Directory that will hold ``{lang}.html`` and ``{lang}.meta.json``.
        force: When True, overwrite an existing snapshot.

    Returns:
        bool: True when a new/updated snapshot was written, False when skipped.
    """
    html_file = snap_dir / f"{language}.html"

    if html_file.exists() and not force:
        logger.info("skip (exists): %s/%s", slug, language)
        return False

    sources = await get_source_urls(slug)
    source = next((s for s in sources if s.get("language") == language), None)
    if source is None:
        logger.warning("no source configured: %s/%s", slug, language)
        return False

    logger.info("fetching %s/%s from %s", slug, language, source["source_url"])
    try:
        result = await fetch_act_page(source["source_url"], slug, language)
    except Exception as exc:
        logger.error("fetch failed %s/%s: %s", slug, language, exc)
        return False

    if result.not_modified:
        logger.info("not modified: %s/%s", slug, language)
        return False

    written_file = await asyncio.to_thread(
        _write_snapshot,
        snap_dir,
        language,
        result.html,
        result.url,
        result.fetched_at.isoformat(),
    )
    logger.info("saved snapshot: %s (%d bytes)", written_file, len(result.html))
    return True


async def run(slugs: list[str], force: bool) -> None:
    """Snapshot all requested acts in both languages.

    Args:
        slugs: Act slugs to process.
        force: Overwrite existing snapshots when True.
    """
    settings = get_settings()
    base_dir = Path(settings.html_snapshot_dir)

    ok = skipped = failed = 0
    for slug in slugs:
        for lang in ("bn", "en"):
            snap_dir = base_dir / slug
            written = await snapshot_act(slug, lang, snap_dir, force)
            if written:
                ok += 1
            else:
                skipped += 1

    logger.info("snapshot complete — written=%d skipped=%d failed=%d", ok, skipped, failed)


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
    parser.add_argument(
        "--force", action="store_true", help="Overwrite existing snapshots"
    )
    args = parser.parse_args()

    slugs = [args.slug] if args.slug else _all_slugs()
    if not slugs:
        logger.error("no acts found in config/acts/")
        sys.exit(1)

    logger.info("snapshotting %d act(s) ...", len(slugs))
    asyncio.run(run(slugs, force=args.force))


if __name__ == "__main__":
    main()
