import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_WS = re.compile(r"\s+")
_SEED_PATH = Path(__file__).resolve().parent / "data" / "petition_wiki_seed.json"
_seed_cache: tuple[float, list[dict[str, Any]]] | None = None


def _norm(s: str) -> str:
    return _WS.sub("", (s or "").lower())


def _load_seed_file() -> list[dict[str, Any]]:
    global _seed_cache
    if not _SEED_PATH.is_file():
        return []
    try:
        mtime = _SEED_PATH.stat().st_mtime
    except OSError:
        return []
    if _seed_cache is not None and _seed_cache[0] == mtime:
        return _seed_cache[1]
    with open(_SEED_PATH, encoding="utf-8") as f:
        data = json.load(f)
    rows = data if isinstance(data, list) else []
    _seed_cache = (mtime, rows)
    return rows


async def _load_table_rows() -> list[dict[str, Any]]:
    from law_finder.db_pool import get_shared_pg

    try:
        pg = await get_shared_pg()
    except Exception as e:
        logger.debug("petition_wiki: no pg %s", e)
        return []
    try:
        return await pg.execute_query(
            """
            SELECT slug, title, triggers, actor, action, context, consequence,
                   linked_document_ids, body, repealed
            FROM petition_wiki_entry
            ORDER BY id
            """,
            [],
        ) or []
    except Exception as e:
        logger.debug("petition_wiki table skip: %s", e)
        return []


def _row_matches(qn: str, r: dict[str, Any]) -> bool:
    tr = r.get("triggers") or ""
    for t in re.split(r"[,，;；\s]+", tr):
        tn = _norm(t)
        if len(tn) >= 2 and tn in qn:
            return True
    ti = _norm(r.get("title") or "")
    for seg in re.split(r"[、，,/]+", ti):
        sn = _norm(seg)
        if len(sn) >= 4 and sn in qn:
            return True
    if len(ti) >= 4 and ti in qn:
        return True
    return False


async def search_petition_wiki(user_text: str, limit: int = 8) -> list[dict[str, Any]]:
    qn = _norm(user_text)
    if not qn:
        return []
    rows = await _load_table_rows()
    if not rows:
        rows = _load_seed_file()
    out: list[dict[str, Any]] = []
    for r in rows:
        if r.get("repealed") is True:
            continue
        if _row_matches(qn, r):
            out.append(dict(r))
        if len(out) >= limit:
            break
    return out[:limit]


async def petition_wiki_scan(user_text: str, limit: int = 8) -> tuple[list[dict[str, Any]], list[int]]:
    hits = await search_petition_wiki(user_text, limit=limit)
    ids: list[int] = []
    for r in hits:
        raw = r.get("linked_document_ids")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                raw = []
        for x in raw or []:
            try:
                ids.append(int(x))
            except (TypeError, ValueError):
                continue
    return hits, list(dict.fromkeys(ids))


async def collect_petition_wiki_document_ids(user_text: str) -> list[int]:
    _, ids = await petition_wiki_scan(user_text)
    return ids


def format_petition_wiki_for_prompt(rows: list[dict[str, Any]], max_chars: int = 2800) -> str:
    if not rows:
        return ""
    chunks = []
    n = 0
    for r in rows:
        line = (
            f"【{r.get('title', '')}】\n"
            f"主体:{r.get('actor') or '-'} 行为:{r.get('action') or '-'} "
            f"情景:{r.get('context') or '-'} 后果:{r.get('consequence') or '-'}\n"
            f"{(r.get('body') or '').strip()}"
        )
        if n + len(line) > max_chars:
            break
        chunks.append(line)
        n += len(line)
    return "\n\n".join(chunks)
