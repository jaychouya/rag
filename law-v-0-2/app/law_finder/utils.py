import json
import logging
import os
import time
from typing import Optional

from law_finder.db_pool import get_shared_pg

logger = logging.getLogger(__name__)

_CATEGORY_CACHE_TTL = float(os.getenv("LAW_FINDER_CATEGORY_CACHE_TTL", "60"))
_category_cache: dict[str, tuple[float, list]] = {}


def _category_cache_key(category_scope: Optional[list[str]], columns: Optional[list[str]]) -> str:
    return json.dumps(
        {"cs": category_scope or [], "cols": columns or []},
        sort_keys=True,
        ensure_ascii=False,
    )


async def test_db_connection():
    try:
        pg_helper = await get_shared_pg()
        result = await pg_helper.execute_query("SELECT 1")
        return bool(result)
    except Exception as e:
        logger.warning("数据库连接测试失败: %s", e)
        return False


async def load_categories(category_scope: Optional[list[str]] = None, columns: Optional[list[str]] = None) -> list:
    ck = _category_cache_key(category_scope, columns)
    now = time.monotonic()
    if ck in _category_cache:
        ts, data = _category_cache[ck]
        if now - ts < _CATEGORY_CACHE_TTL:
            return json.loads(json.dumps(data))

    pg_helper = await get_shared_pg()

    if columns:
        select_columns = ", ".join([f"lc.{col}" for col in columns])
    else:
        select_columns = "lc.id, lc.name, lc.type, lc.summary"

    if category_scope:
        json_conditions = []
        for scope in category_scope:
            json_conditions.append(f"lc.type::text LIKE '%\"{scope}\"%'")

        query = f"""
            SELECT DISTINCT {select_columns}
            FROM LegalCategory lc
            INNER JOIN LegalDocuments ld ON lc.id = ld.category_id
            WHERE ld.enabled = TRUE
            AND ({' OR '.join(json_conditions)})
            """
    else:
        query = f"""
            SELECT DISTINCT {select_columns}
            FROM LegalCategory lc
            INNER JOIN LegalDocuments ld ON lc.id = ld.category_id
            WHERE ld.enabled = TRUE
            """

    result = await pg_helper.execute_query(query)
    categories = []

    for row in result:
        if columns:
            category = {}
            for col in columns:
                category[col] = row[col]
        else:
            category = {
                "id": row["id"],
                "name": row["name"],
                "type": row["type"],
                "summary": row["summary"],
            }
        categories.append(category)

    _category_cache[ck] = (now, json.loads(json.dumps(categories)))
    return categories


async def load_laws_by_id(laws_ids: Optional[list[int]] = None, columns: Optional[list[str]] = None) -> list:
    cleaned_ids = []
    for id in laws_ids or []:
        try:
            cleaned_ids.append(int(id))
        except (ValueError, TypeError):
            continue
    laws_ids = cleaned_ids
    if not laws_ids:
        return []

    pg_helper = await get_shared_pg()

    if columns:
        if "id" not in columns:
            columns = list(columns) + ["id"]
        select_columns = ", ".join([f"ld.{col}" for col in columns])
    else:
        select_columns = "ld.id, ld.name, ld.content"

    placeholders = ",".join([f"${i + 1}" for i in range(len(laws_ids))])
    query = f"""SELECT {select_columns} FROM LegalDocuments ld WHERE ld.id IN ({placeholders}) AND ld.enabled = TRUE"""
    result = await pg_helper.execute_query(query, laws_ids)

    laws = []
    for row in result:
        try:
            if columns:
                law = {}
                for col in columns:
                    law[col] = row[col]

                if "content" in law and law["content"]:
                    law["content"] = json.loads(str(law["content"]))
            else:
                law = {
                    "id": row["id"],
                    "name": row["name"],
                    "content": json.loads(str(row["content"])) if row["content"] else None,
                }
            laws.append(law)
        except json.JSONDecodeError as e:
            logger.error("法律条款%s的内容解析失败: %s", row.get("id"), e)

    return laws


async def load_laws_by_category(
    categoriesIds: Optional[list[int]] = None,
    law_tags: Optional[list[str]] = None,
    columns: Optional[list[str]] = None,
    document_id_filter: Optional[list[int]] = None,
) -> list:
    pg_helper = await get_shared_pg()

    if columns:
        if "id" not in columns:
            columns = list(columns) + ["id"]
        select_columns = ", ".join([f"ld.{col}" for col in columns])
    else:
        select_columns = "ld.id, ld.name, ld.content"

    conditions = ["ld.enabled = TRUE"]
    params = []
    param_index = 1

    if categoriesIds:
        placeholders = ",".join([f"${param_index + i}" for i in range(len(categoriesIds))])
        conditions.append(f"ld.category_id IN ({placeholders})")
        params.extend(categoriesIds)
        param_index += len(categoriesIds)

    if law_tags:
        tag_conditions = []
        for tag in law_tags:
            tag_conditions.append(f"ld.tags::text LIKE '%\"{tag}\"%'")
        conditions.append(f"({' OR '.join(tag_conditions)})")

    if document_id_filter:
        clean = [int(x) for x in document_id_filter if x is not None]
        if clean:
            nxt = len(params) + 1
            conditions.append(f"ld.id = ANY(${nxt}::int[])")
            params.append(clean)

    query = f"""SELECT {select_columns} FROM LegalDocuments ld WHERE {' AND '.join(conditions)}"""

    result = await pg_helper.execute_query(query, params)
    laws = []

    for row in result:
        try:
            if columns:
                law = {}
                for col in columns:
                    law[col] = row[col]

                if "content" in law and law["content"]:
                    law["content"] = json.loads(str(law["content"]))
            else:
                law = {
                    "id": row["id"],
                    "name": row["name"],
                    "content": json.loads(str(row["content"])) if row["content"] else None,
                }
            laws.append(law)
        except json.JSONDecodeError as e:
            logger.error("法律条款%s的内容解析失败: %s", row.get("id"), e)

    return laws
