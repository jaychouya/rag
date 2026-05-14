import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

_CN = re.compile(r"[\u4e00-\u9fff]+")
_STOP_CHARS = frozenset("的了是在我你他她它们这那个么什怎吗呢吧啊哦呀嘛被把和与及或到从对于为由让给跟向")
_STOP_CHARS_RE = re.compile("[" + re.escape("".join(_STOP_CHARS)) + "]")
_STOP_WORDS = frozenset({
    "如何", "怎样", "什么", "哪些", "可以", "应该", "需要", "能够",
    "问题", "情况", "处理", "办法", "方法", "方式", "标准", "规定",
    "怎么", "进行", "相关", "有关", "一般", "具体", "主要", "其他",
    "属于", "认为", "通过", "根据", "按照", "依据", "关于", "以及",
    "案件", "简述", "之间", "形成", "发生", "损害", "后果",
    "核心", "行为", "涉及", "包括", "明确", "适用", "场景",
    "构成", "确认", "分配", "成立", "存在", "查询", "需求",
})


def _extract_cn_keywords(text: str, min_len: int = 2, max_kw: int = 20) -> list[str]:
    segs = _CN.findall(text or "")
    kws: list[str] = []
    seen: set[str] = set()
    for seg in segs:
        parts = _STOP_CHARS_RE.split(seg)
        for part in parts:
            if len(part) < min_len:
                continue
            for i in range(len(part) - min_len + 1):
                token = part[i:i + min_len]
                if token in _STOP_WORDS or token in seen:
                    continue
                seen.add(token)
                kws.append(token)
        if len(kws) >= max_kw:
            break
    return kws[:max_kw]


async def try_search_document_ids(
    query_text: str,
    category_scope: Optional[list[str]] = None,
    law_tags: Optional[list[str]] = None,
    category_ids: Optional[list[int]] = None,
    limit: int = 30,
    direct_keywords: Optional[list[str]] = None,
) -> Optional[list[int]]:
    _ = category_scope
    from law_finder.db_pool import get_shared_pg

    dk_clean: list[str] = []
    dk_seen: set[str] = set()
    for dkw in (direct_keywords or []):
        term = dkw.strip()
        if len(term) >= 2 and term not in dk_seen and term not in _STOP_WORDS:
            dk_seen.add(term)
            dk_clean.append(term)
    bigram_kws = _extract_cn_keywords(query_text, max_kw=12)
    extra_bigrams = [k for k in bigram_kws if k not in dk_seen]
    keywords = dk_clean + extra_bigrams[:8]
    if not keywords:
        return None

    try:
        pg = await get_shared_pg()
    except Exception as e:
        logger.debug("retrieval: no pg: %s", e)
        return None

    params: list = []
    kw_hit_parts = []
    for kw in keywords:
        n = len(params) + 1
        kw_hit_parts.append(f"MAX(CASE WHEN n.body LIKE ${n} OR n.summary LIKE ${n} THEN 1 ELSE 0 END)")
        params.append(f"%{kw}%")

    extra_sql = ""
    if law_tags:
        ors = []
        for tag in law_tags:
            n = len(params) + 1
            ors.append(f"ld.tags::text LIKE ${n}")
            params.append(f"%\"{tag}\"%")
        extra_sql += " AND (" + " OR ".join(ors) + ")"
    if category_ids:
        clean_cats = [int(x) for x in category_ids if x is not None]
        if clean_cats:
            n = len(params) + 1
            extra_sql += f" AND ld.category_id = ANY(${n}::int[])"
            params.append(clean_cats)
    nlim = len(params) + 1
    params.append(limit)

    or_clauses = " OR ".join(
        f"n.body LIKE ${i+1} OR n.summary LIKE ${i+1}" for i in range(len(keywords))
    )
    kw_coverage = " + ".join(kw_hit_parts)
    n_direct = len(dk_clean)
    min_coverage = max(1, min(n_direct // 3, 3)) if n_direct > 0 else 1

    sql = f"""
        SELECT t.document_id AS id, t.kw_coverage
        FROM (
            SELECT n.document_id,
                   {kw_coverage} AS kw_coverage
            FROM legal_document_node n
            INNER JOIN LegalDocuments ld ON ld.id = n.document_id
            WHERE ld.enabled = TRUE
              AND ({or_clauses})
              {extra_sql}
            GROUP BY n.document_id
            HAVING {kw_coverage} >= {min_coverage}
        ) t
        ORDER BY t.kw_coverage DESC, t.document_id
        LIMIT ${nlim}
    """
    try:
        rows = await pg.execute_query(sql, params)
    except Exception as e:
        logger.debug("retrieval skip (table or query): %s", e)
        return None

    logger.info("retrieval_sql keywords=%s matched=%s", keywords, len(rows))
    if not rows:
        return []
    return [int(r["id"]) for r in rows if r.get("id") is not None]
