"""Idempotent database, media, and catalog sanitization script.

Removes mock/demo/corrupt videos, legacy proxy URLs, HTML wrapper links,
and fake Telegram file_ids across data/videos/, data/video_sources.json,
data/catalog.json, PostgreSQL, and SQLite databases, and reconciles code 101
against live Asilmedia metadata (17638, 8 real episodes).
"""

import asyncio
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import BASE_DIR  # noqa: E402
from database.session import get_session  # noqa: E402
from services.asilmedia_service import asilmedia_service  # noqa: E402

MIN_DATA_VIDEO_BYTES = 500 * 1024
MIN_SOURCE_LOCAL_VIDEO_BYTES = 1024 * 1024

BAD_URL_MARKERS = (
    "samplelib",
    "sample-",
    "mov_bbb",
    "flower.mp4",
    "oceans.mp4",
    "default.mp4",
    "161-97-" + "96-58",
    "sslip.io",
    "server.asilmedia.org",
    ".html",
    "sayt.php",
)


def is_bad_media_ref(value: Any) -> bool:
    """Return True if a URL/path/reference points to mock, proxy, or HTML wrapper."""
    if not isinstance(value, str):
        return True
    s = value.strip()
    if not s:
        return True
    low = s.lower()
    return any(marker in low for marker in BAD_URL_MARKERS)


def is_bad_telegram_file_id(value: Any) -> bool:
    """Return True if a stored Telegram file_id is fake, raw am:, URL, or mock."""
    if not isinstance(value, str):
        return False
    s = value.strip()
    if not s:
        return False
    if s.startswith("BAACAgIAAxkBAAIB_"):
        return True
    low = s.lower()
    if low.startswith(("http://", "https://", "am:")):
        return True
    if any(marker in low for marker in BAD_URL_MARKERS):
        return True
    return len(s) < 15


def _is_valid_local_file(raw_path: Any, min_bytes: int) -> bool:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return False
    if is_bad_media_ref(raw_path):
        return False
    candidate = Path(raw_path.strip())
    if not candidate.is_absolute():
        candidate = BASE_DIR / candidate
    try:
        if not candidate.exists() or not candidate.is_file():
            return False
        if candidate.stat().st_size < min_bytes:
            return False
        with open(candidate, "rb") as fh:
            head = fh.read(64)
        return asilmedia_service.is_valid_video_header(head)
    except OSError:
        return False


def clean_data_videos_dir(videos_dir: Path) -> Dict[str, Any]:
    """Delete default.mp4, corrupt 101_10.mp4, .tmp files, <500KB or header-invalid files."""
    stats: Dict[str, Any] = {"checked": 0, "deleted": [], "kept": []}
    if not videos_dir.exists():
        return stats

    explicit_delete = {"default.mp4", "101_10.mp4"}

    for item in sorted(videos_dir.iterdir()):
        if not item.is_file():
            continue
        if item.name == ".gitkeep":
            continue

        stats["checked"] += 1
        reason: Optional[str] = None

        if item.name in explicit_delete:
            reason = f"explicit_bad:{item.name}"
        elif item.suffix.lower() == ".tmp" or ".tmp" in item.name.lower():
            reason = "temp_file"
        else:
            try:
                size = item.stat().st_size
                if size < MIN_DATA_VIDEO_BYTES:
                    reason = f"too_small:{size}"
                else:
                    with open(item, "rb") as fh:
                        head = fh.read(64)
                    if not asilmedia_service.is_valid_video_header(head):
                        reason = "invalid_header"
            except OSError as exc:
                reason = f"stat_error:{exc}"

        if reason:
            item.unlink(missing_ok=True)
            stats["deleted"].append({"file": item.name, "reason": reason})
        else:
            stats["kept"].append(item.name)

    return stats


def _clean_source_entry(key: str, entry: Any) -> Optional[Any]:
    """Sanitize one data/video_sources.json entry; return None if nothing valid remains."""
    if isinstance(entry, str):
        s = entry.strip()
        if not s or is_bad_media_ref(s):
            return None
        if s.lower().startswith(("http://", "https://", "am:")):
            return s
        return s if _is_valid_local_file(s, MIN_SOURCE_LOCAL_VIDEO_BYTES) else None

    if not isinstance(entry, dict):
        return None

    cleaned = dict(entry)

    for url_key in ("url", "download_url", "stream_url", "video_url", "src", "watch_url"):
        if url_key in cleaned:
            val = cleaned[url_key]
            if not isinstance(val, str) or is_bad_media_ref(val):
                cleaned.pop(url_key, None)
            elif not val.strip().lower().startswith(("http://", "https://", "am:")):
                cleaned.pop(url_key, None)

    if "file_id" in cleaned:
        fid = cleaned["file_id"]
        if not isinstance(fid, str) or not fid.strip() or is_bad_telegram_file_id(fid):
            cleaned.pop("file_id", None)

    for path_key in ("file_path", "local_path"):
        if path_key in cleaned:
            if not _is_valid_local_file(cleaned[path_key], MIN_SOURCE_LOCAL_VIDEO_BYTES):
                cleaned.pop(path_key, None)

    if "quality_urls" in cleaned:
        qurls = cleaned["quality_urls"]
        if isinstance(qurls, dict):
            valid_q = {
                str(q): str(u).strip()
                for q, u in qurls.items()
                if isinstance(u, str)
                and not is_bad_media_ref(u)
                and u.strip().lower().startswith(("http://", "https://", "am:"))
            }
            if valid_q:
                cleaned["quality_urls"] = valid_q
            else:
                cleaned.pop("quality_urls", None)
        else:
            cleaned.pop("quality_urls", None)

    has_media = any(
        cleaned.get(k)
        for k in ("url", "download_url", "stream_url", "video_url", "src", "file_id", "file_path", "local_path", "quality_urls")
    )
    return cleaned if has_media else None


def clean_video_sources_json(sources_path: Path) -> Dict[str, int]:
    """Remove polluted entries and invalid local paths from data/video_sources.json."""
    stats = {"before": 0, "after": 0, "removed": 0}
    if not sources_path.exists():
        return stats

    raw = json.loads(sources_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return stats

    items_map = raw.get("items") if isinstance(raw.get("items"), dict) else raw
    stats["before"] = len(items_map)
    cleaned: Dict[str, Any] = {}
    for k, v in items_map.items():
        if re.match(r"^101_(\d+)$", str(k)):
            if int(str(k).split("_", 1)[1]) > 8:
                continue
        new_v = _clean_source_entry(str(k), v)
        if new_v is not None:
            cleaned[str(k)] = new_v

    stats["after"] = len(cleaned)
    stats["removed"] = stats["before"] - stats["after"]

    payload = {"items": cleaned}
    tmp_path = sources_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(sources_path)
    return stats


def _extra_part_over_limit(code: str, base_code: str, max_part: int) -> bool:
    prefix = f"{base_code}_"
    if not code.startswith(prefix):
        return False
    suffix = code[len(prefix) :]
    return suffix.isdigit() and int(suffix) > max_part


async def clean_postgres(confirm_101_eight_parts: bool) -> Dict[str, int]:
    """Clear polluted file_ids and remove bogus 101_9+ rows in PostgreSQL."""
    stats = {
        "movies_fid_cleared": 0,
        "movie_files_cleaned": 0,
        "movies_101_extra_deleted": 0,
        "movie_files_101_extra_deleted": 0,
    }

    async with get_session() as session:
        rows = (await session.execute(text("SELECT id, code, file_id FROM movies WHERE file_id IS NOT NULL AND file_id <> ''"))).all()
        bad_movie_ids = [r[0] for r in rows if is_bad_telegram_file_id(r[2])]
        if bad_movie_ids:
            m_nullable_row = (
                await session.execute(
                    text(
                        "SELECT is_nullable FROM information_schema.columns "
                        "WHERE table_name = 'movies' AND column_name = 'file_id'"
                    )
                )
            ).first()
            m_is_nullable = bool(m_nullable_row and str(m_nullable_row[0]).upper() == "YES")
            if m_is_nullable:
                await session.execute(
                    text("UPDATE movies SET file_id = NULL WHERE id = ANY(:ids)"),
                    {"ids": bad_movie_ids},
                )
            else:
                await session.execute(
                    text("UPDATE movies SET file_id = '' WHERE id = ANY(:ids)"),
                    {"ids": bad_movie_ids},
                )
            stats["movies_fid_cleared"] = len(bad_movie_ids)

        mf_nullable_row = (
            await session.execute(
                text(
                    "SELECT is_nullable FROM information_schema.columns "
                    "WHERE table_name = 'movie_files' AND column_name = 'file_id'"
                )
            )
        ).first()
        mf_is_nullable = bool(mf_nullable_row and str(mf_nullable_row[0]).upper() == "YES")

        mf_rows = (await session.execute(text("SELECT id, file_id FROM movie_files WHERE file_id IS NOT NULL"))).all()
        bad_mf_ids = [r[0] for r in mf_rows if is_bad_telegram_file_id(r[1])]
        if bad_mf_ids:
            if mf_is_nullable:
                await session.execute(
                    text("UPDATE movie_files SET file_id = NULL WHERE id = ANY(:ids)"),
                    {"ids": bad_mf_ids},
                )
            else:
                await session.execute(
                    text("DELETE FROM movie_files WHERE id = ANY(:ids)"),
                    {"ids": bad_mf_ids},
                )
            stats["movie_files_cleaned"] = len(bad_mf_ids)

        if confirm_101_eight_parts:
            rows_101 = (await session.execute(text("SELECT code FROM movies WHERE code LIKE '101_%'"))).all()
            extra_codes = [r[0] for r in rows_101 if _extra_part_over_limit(str(r[0]), "101", 8)]
            if extra_codes:
                res = await session.execute(
                    text("DELETE FROM movies WHERE code = ANY(:codes)"),
                    {"codes": extra_codes},
                )
                stats["movies_101_extra_deleted"] = res.rowcount or len(extra_codes)

            res_mf = await session.execute(
                text("DELETE FROM movie_files WHERE movie_code = '101' AND part > 8")
            )
            stats["movie_files_101_extra_deleted"] = res_mf.rowcount or 0

        await session.commit()

    return stats


def clean_sqlite_db(db_path: Path, confirm_101_eight_parts: bool) -> Dict[str, Any]:
    """Clean bad file_ids and extra 101 parts in a SQLite DB if present and non-empty."""
    stats: Dict[str, Any] = {
        "path": str(db_path),
        "skipped": False,
        "movies_fid_cleared": 0,
        "movie_files_cleaned": 0,
        "movies_101_extra_deleted": 0,
        "movie_files_101_extra_deleted": 0,
    }
    if not db_path.exists() or db_path.stat().st_size == 0:
        stats["skipped"] = True
        return stats

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        tables = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

        if "movies" in tables:
            cols = {row[1]: row for row in cur.execute("PRAGMA table_info(movies)").fetchall()}
            if "file_id" in cols and "code" in cols:
                notnull_m = bool(cols["file_id"][3])
                rows = cur.execute(
                    "SELECT rowid, code, file_id FROM movies WHERE file_id IS NOT NULL AND file_id <> ''"
                ).fetchall()
                bad_rowids = [(r[0],) for r in rows if is_bad_telegram_file_id(r[2])]
                if bad_rowids:
                    if notnull_m:
                        cur.executemany("UPDATE movies SET file_id = '' WHERE rowid = ?", bad_rowids)
                    else:
                        cur.executemany("UPDATE movies SET file_id = NULL WHERE rowid = ?", bad_rowids)
                    stats["movies_fid_cleared"] = len(bad_rowids)

                if confirm_101_eight_parts:
                    rows_101 = cur.execute("SELECT code FROM movies WHERE code LIKE '101_%'").fetchall()
                    extra_codes = [(r[0],) for r in rows_101 if _extra_part_over_limit(str(r[0]), "101", 8)]
                    if extra_codes:
                        cur.executemany("DELETE FROM movies WHERE code = ?", extra_codes)
                        stats["movies_101_extra_deleted"] = len(extra_codes)

        if "movie_files" in tables:
            cols = {row[1]: row for row in cur.execute("PRAGMA table_info(movie_files)").fetchall()}
            if "file_id" in cols:
                # PRAGMA table_info: (cid, name, type, notnull, dflt_value, pk)
                notnull = bool(cols["file_id"][3])
                rows = cur.execute("SELECT rowid, file_id FROM movie_files WHERE file_id IS NOT NULL").fetchall()
                bad_rowids = [(r[0],) for r in rows if is_bad_telegram_file_id(r[1])]
                if bad_rowids:
                    if notnull:
                        cur.executemany("DELETE FROM movie_files WHERE rowid = ?", bad_rowids)
                    else:
                        cur.executemany("UPDATE movie_files SET file_id = NULL WHERE rowid = ?", bad_rowids)
                    stats["movie_files_cleaned"] = len(bad_rowids)

                if confirm_101_eight_parts and "movie_code" in cols and "part" in cols:
                    cur.execute("DELETE FROM movie_files WHERE movie_code = '101' AND part > 8")
                    stats["movie_files_101_extra_deleted"] = cur.rowcount

        conn.commit()
    finally:
        conn.close()

    return stats


def reconcile_catalog_and_sources_101(
    catalog_path: Path,
    sources_path: Path,
    details_101: Any,
) -> Dict[str, Any]:
    """Ensure catalog.json item 101 has p=8 and asil_id=17638, and update video_sources.json."""
    result: Dict[str, Any] = {"catalog_updated": False, "sources_101_parts": 0}
    raw_eps = getattr(details_101, "episodes", None) or {}
    eps_iter = raw_eps.values() if isinstance(raw_eps, dict) else raw_eps
    episodes = sorted(eps_iter, key=lambda ep: int(getattr(ep, "part", 0) or 0))
    if len(episodes) != 8:
        return result

    if catalog_path.exists():
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        items = catalog.get("items") if isinstance(catalog, dict) else catalog
        if isinstance(items, list):
            changed = False
            for item in items:
                if isinstance(item, dict) and str(item.get("c")) == "101":
                    if item.get("p") != 8:
                        item["p"] = 8
                        changed = True
                    if item.get("asil_id") != 17638:
                        item["asil_id"] = 17638
                        changed = True
                    result["catalog_updated"] = True
                    break
            if changed:
                tmp_cat = catalog_path.with_suffix(".json.tmp")
                tmp_cat.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
                tmp_cat.replace(catalog_path)

    if sources_path.exists():
        loaded_src = json.loads(sources_path.read_text(encoding="utf-8"))
    else:
        loaded_src = {"items": {}}

    if isinstance(loaded_src, dict):
        if isinstance(loaded_src.get("items"), dict):
            sources_wrap = loaded_src
            sources_items = loaded_src["items"]
        else:
            sources_items = dict(loaded_src)
            sources_wrap = {"items": sources_items}

        for k in list(sources_items.keys()):
            if re.match(r"^101_(\d+)$", str(k)) and int(str(k).split("_", 1)[1]) > 8:
                sources_items.pop(k, None)

        for ep in episodes:
            stream_url = getattr(ep, "url", None) or getattr(ep, "download_url", None) or ""
            if not stream_url or is_bad_media_ref(stream_url):
                continue
            qurls = {
                str(q): str(u)
                for q, u in (getattr(ep, "quality_urls", None) or {}).items()
                if isinstance(u, str) and not is_bad_media_ref(u)
            }
            sources_items[f"101_{ep.part}"] = {
                "title": getattr(details_101, "title", None) or "Derriga xush kelibsiz",
                "part": ep.part,
                "asil_id": "17638",
                "url": stream_url,
                "quality_urls": qurls,
            }
            if ep.part == 1:
                sources_items["101"] = dict(sources_items[f"101_{ep.part}"])
            result["sources_101_parts"] += 1

        tmp_src = sources_path.with_suffix(".json.tmp")
        tmp_src.write_text(json.dumps(sources_wrap, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_src.replace(sources_path)

    return result


async def run_cleanup() -> Dict[str, Any]:
    """Execute all sanitization steps idempotently and return a summary dict."""
    videos_dir = BASE_DIR / "data" / "videos"
    sources_path = BASE_DIR / "data" / "video_sources.json"
    catalog_path = BASE_DIR / "data" / "catalog.json"

    video_stats = clean_data_videos_dir(videos_dir)
    sources_stats = clean_video_sources_json(sources_path)

    try:
        details_101 = await asilmedia_service.get_movie_details(17638)
        confirm_101_eight = bool(details_101 and len(getattr(details_101, "episodes", []) or []) == 8)

        pg_stats = await clean_postgres(confirm_101_eight)
        sqlite_stats = [
            clean_sqlite_db(BASE_DIR / "baunty.db", confirm_101_eight),
            clean_sqlite_db(BASE_DIR / "data" / "bot.db", confirm_101_eight),
        ]

        reconcile_stats = {"catalog_updated": False, "sources_101_parts": 0}
        if confirm_101_eight:
            reconcile_stats = reconcile_catalog_and_sources_101(catalog_path, sources_path, details_101)
    finally:
        close_fn = getattr(asilmedia_service, "close_session", None) or getattr(asilmedia_service, "close", None)
        if callable(close_fn):
            await close_fn()

    return {
        "videos_dir": video_stats,
        "video_sources": sources_stats,
        "asilmedia_17638_parts": len(getattr(details_101, "episodes", []) or []) if details_101 else 0,
        "confirm_101_eight": confirm_101_eight,
        "postgres": pg_stats,
        "sqlite": sqlite_stats,
        "reconcile_101": reconcile_stats,
    }


def main() -> None:
    report = asyncio.run(run_cleanup())
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
