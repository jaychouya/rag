import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_MAP_PATH = Path(__file__).resolve().parent / "data" / "keyword_structural_map.json"
_ALIAS_PATH = Path(__file__).resolve().parent / "data" / "semantic_aliases.json"
_WS = re.compile(r"\s+")
_map_cache: tuple[float, dict[str, Any]] | None = None
_alias_cache: tuple[float, dict[str, Any]] | None = None


def _raw_mapping() -> dict[str, Any]:
    global _map_cache
    if not _MAP_PATH.is_file():
        return {}
    try:
        mtime = _MAP_PATH.stat().st_mtime
    except OSError:
        return {}
    if _map_cache is not None and _map_cache[0] == mtime:
        return _map_cache[1]
    with open(_MAP_PATH, encoding="utf-8") as f:
        data = json.load(f)
    cleaned = {k: v for k, v in data.items() if not k.startswith("_")}
    _map_cache = (mtime, cleaned)
    return cleaned


def _raw_aliases() -> dict[str, Any]:
    global _alias_cache
    if not _ALIAS_PATH.is_file():
        return {}
    try:
        mtime = _ALIAS_PATH.stat().st_mtime
    except OSError:
        return {}
    if _alias_cache is not None and _alias_cache[0] == mtime:
        return _alias_cache[1]
    with open(_ALIAS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    cleaned = {k: v for k, v in data.items() if not k.startswith("_")}
    _alias_cache = (mtime, cleaned)
    return cleaned


def _canon_keys(val: Any) -> list[str]:
    if isinstance(val, str):
        return [val]
    if isinstance(val, list):
        return [x for x in val if isinstance(x, str) and x]
    return []


def _merge_rule(
    cat_scopes: list[str],
    tags: list[str],
    matched: list[str],
    status: list[str],
    rule: dict[str, Any],
    matched_label: str,
) -> None:
    matched.append(matched_label)
    for c in rule.get("category_scope") or []:
        if c and c not in cat_scopes:
            cat_scopes.append(c)
    for t in rule.get("tags") or []:
        if t and t not in tags:
            tags.append(t)
    if rule.get("status") == "repealed":
        status[0] = "repealed"


def extract_structured_filter(user_query: str) -> dict[str, Any]:
    q = _WS.sub("", (user_query or "").strip())
    if not q:
        return {
            "categories": [],
            "category_scope": [],
            "tags": [],
            "status": "effective",
            "active": False,
            "matched_keywords": [],
        }

    mapping = _raw_mapping()
    aliases = _raw_aliases()
    cat_scopes: list[str] = []
    tags: list[str] = []
    matched: list[str] = []
    status_box = ["effective"]

    for alias in sorted(aliases.keys(), key=len, reverse=True):
        if alias not in q:
            continue
        for canon in _canon_keys(aliases[alias]):
            rule = mapping.get(canon)
            if not rule:
                logger.debug("semantic_alias skip unknown target %s (from %s)", canon, alias)
                continue
            _merge_rule(cat_scopes, tags, matched, status_box, rule, f"≈{alias}→{canon}")

    for phrase in sorted(mapping.keys(), key=len, reverse=True):
        if phrase not in q:
            continue
        rule = mapping[phrase] or {}
        _merge_rule(cat_scopes, tags, matched, status_box, rule, phrase)

    st = status_box[0]
    return {
        "categories": list(cat_scopes),
        "category_scope": cat_scopes,
        "tags": tags,
        "status": st,
        "active": bool(matched),
        "matched_keywords": matched,
    }


def _enabled_sql(status: str) -> str:
    if status == "repealed":
        return "ld.enabled = FALSE"
    return "ld.enabled = TRUE"


async def _resolve_category_ids(category_scope: list[str]) -> list[int]:
    if not category_scope:
        return []
    from law_finder.utils import load_categories

    rows = await load_categories(category_scope=category_scope, columns=["id"])
    return [int(r["id"]) for r in rows if r.get("id") is not None]


async def structured_filter_document_ids(
    spec: Optional[dict[str, Any]] = None,
    user_query: Optional[str] = None,
    limit: int = 200,
) -> list[int]:
    if user_query is not None:
        spec = extract_structured_filter(user_query)
    if not spec or not spec.get("active"):
        return []
    cat_ids = await _resolve_category_ids(spec.get("category_scope") or [])
    tags = spec.get("tags") or []
    if not cat_ids and not tags:
        return []

    from law_finder.db_pool import get_shared_pg

    try:
        pg = await get_shared_pg()
    except Exception as e:
        logger.debug("structured_filter: no pg %s", e)
        return []

    conds: list[str] = []
    params: list[Any] = []
    n = 1
    if cat_ids:
        conds.append(f"ld.category_id = ANY(${n}::int[])")
        params.append(cat_ids)
        n += 1
    for tag in tags:
        conds.append(f"ld.tags::text LIKE ${n}")
        params.append(f"%\"{tag}\"%")
        n += 1
    inner = " OR ".join(conds) if len(conds) > 1 else conds[0]
    en = _enabled_sql(spec.get("status") or "effective")
    params.append(limit)
    sql = f"""
        SELECT ld.id
        FROM LegalDocuments ld
        WHERE {en}
          AND ({inner})
        ORDER BY ld.id
        LIMIT ${n}
    """
    try:
        rows = await pg.execute_query(sql, params)
    except Exception as e:
        logger.warning("structured_filter sql: %s", e)
        return []
    return [int(r["id"]) for r in rows or [] if r.get("id") is not None]


async def structured_filter_laws(user_query: str, limit: int = 200) -> list[dict[str, Any]]:
    spec = extract_structured_filter(user_query)
    if not spec.get("active"):
        return []
    cat_ids = await _resolve_category_ids(spec.get("category_scope") or [])
    tags = spec.get("tags") or []
    if not cat_ids and not tags:
        return []

    from law_finder.db_pool import get_shared_pg

    try:
        pg = await get_shared_pg()
    except Exception as e:
        logger.debug("structured_filter_laws: no pg %s", e)
        return []

    conds: list[str] = []
    params: list[Any] = []
    n = 1
    if cat_ids:
        conds.append(f"ld.category_id = ANY(${n}::int[])")
        params.append(cat_ids)
        n += 1
    for tag in tags:
        conds.append(f"ld.tags::text LIKE ${n}")
        params.append(f"%\"{tag}\"%")
        n += 1
    inner = " OR ".join(conds) if len(conds) > 1 else conds[0]
    en = _enabled_sql(spec.get("status") or "effective")
    params.append(limit)
    sql = f"""
        SELECT ld.id, ld.name AS title, ld.summary
        FROM LegalDocuments ld
        WHERE {en}
          AND ({inner})
        ORDER BY ld.id
        LIMIT ${n}
    """
    try:
        rows = await pg.execute_query(sql, params)
    except Exception as e:
        logger.warning("structured_filter_laws: %s", e)
        return []
    out: list[dict[str, Any]] = []
    for r in rows or []:
        out.append({"id": int(r["id"]), "title": r.get("title"), "summary": r.get("summary")})
    return out
